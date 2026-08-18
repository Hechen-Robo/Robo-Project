from __future__ import annotations

from copy import deepcopy
import logging
from queue import Empty, Queue
import threading
from time import monotonic
from typing import Any

from vda5050_fms.config import Settings
from vda5050_fms.messages import HeaderFactory
from vda5050_fms.mqtt_client import JsonMqttClient
from vda5050_fms.topics import TopicLayout
from vda5050_fms.validation import SchemaRegistry, SchemaValidationError


LOGGER = logging.getLogger(__name__)


class RobotModel:
    """Deterministic single-robot VDA 5050 model without network dependencies."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.registry = SchemaRegistry(settings.vda_version)
        self.headers = HeaderFactory()
        self._route_nodes: dict[int, dict[str, Any]] = {}
        self._route_edges: dict[int, dict[str, Any]] = {}
        self._in_transit_edge: int | None = None
        self._state: dict[str, Any] = {
            "orderId": "",
            "orderUpdateId": 0,
            "lastNodeId": settings.simulation_start_node_id,
            "lastNodeSequenceId": 0,
            "nodeStates": [],
            "edgeStates": [],
            "agvPosition": {
                "x": settings.simulation_start_x,
                "y": settings.simulation_start_y,
                "theta": settings.simulation_start_theta,
                "mapId": settings.simulation_map_id,
                "positionInitialized": True,
                "localizationScore": 1.0,
            },
            "velocity": {"vx": 0.0, "vy": 0.0, "omega": 0.0},
            "driving": False,
            "paused": False,
            "newBaseRequest": False,
            "actionStates": [],
            "batteryState": {
                "batteryCharge": 100.0,
                "batteryVoltage": 48.0,
                "charging": False,
            },
            "operatingMode": "AUTOMATIC",
            "errors": [],
            "information": [],
            "safetyState": {"eStop": "NONE", "fieldViolation": False},
        }

    @property
    def state(self) -> dict[str, Any]:
        return deepcopy(self._state)

    @property
    def is_idle(self) -> bool:
        unfinished_actions = any(
            action["actionStatus"] not in {"FINISHED", "FAILED"}
            for action in self._state["actionStates"]
        )
        return (
            not self._state["nodeStates"]
            and not self._state["edgeStates"]
            and not unfinished_actions
            and not self._state["driving"]
        )

    def handle_order(self, order: dict[str, Any]) -> bool:
        try:
            self.registry.validate("order", order)
            self._verify_identity(order)
        except (SchemaValidationError, ValueError) as exc:
            self._add_error("orderValidation", str(exc))
            return False

        order_id = order["orderId"]
        update_id = order["orderUpdateId"]
        current_order_id = self._state["orderId"]
        current_update_id = self._state["orderUpdateId"]

        if not self.is_idle and current_order_id and order_id != current_order_id:
            self._add_error(
                "orderError",
                f"Order {order_id!r} rejected because {current_order_id!r} is active",
            )
            return False
        if order_id == current_order_id and update_id <= current_update_id:
            LOGGER.info(
                "Ignoring duplicate or outdated order update %s/%s",
                order_id,
                update_id,
            )
            return True
        if order_id != current_order_id and update_id != 0:
            self._add_error(
                "orderUpdateError", "The first message of a new order must use update 0"
            )
            return False

        nodes = sorted(order["nodes"], key=lambda node: node["sequenceId"])
        edges = sorted(order["edges"], key=lambda edge: edge["sequenceId"])
        if not nodes:
            self._add_error("orderError", "An order must contain at least one node")
            return False

        is_new_order = order_id != current_order_id
        if is_new_order:
            start_node = nodes[0]
            self._state["lastNodeId"] = start_node["nodeId"]
            self._state["lastNodeSequenceId"] = start_node["sequenceId"]
            self._apply_position(start_node.get("nodePosition"))
            self._state["actionStates"] = []
            self._in_transit_edge = None

        last_sequence = self._state["lastNodeSequenceId"]
        self._route_nodes = {node["sequenceId"]: deepcopy(node) for node in nodes}
        self._route_edges = {edge["sequenceId"]: deepcopy(edge) for edge in edges}
        self._state["orderId"] = order_id
        self._state["orderUpdateId"] = update_id
        self._state["nodeStates"] = [
            self._node_state(node)
            for node in nodes
            if node["sequenceId"] > last_sequence
        ]
        self._state["edgeStates"] = [
            self._edge_state(edge)
            for edge in edges
            if edge["sequenceId"] > last_sequence
        ]
        self._merge_order_actions(nodes, edges, last_sequence)
        self._state["errors"] = []
        self._update_base_request()
        LOGGER.info("Accepted order %s update %s", order_id, update_id)
        return True

    def handle_instant_actions(self, message: dict[str, Any]) -> bool:
        try:
            self.registry.validate("instantActions", message)
            self._verify_identity(message)
        except (SchemaValidationError, ValueError) as exc:
            self._add_error("instantActionValidation", str(exc))
            return False

        factsheet_requested = False
        for action in message["actions"]:
            action_type = action["actionType"]
            action_id = action["actionId"]
            status = "FINISHED"
            result = ""

            if action_type == "startPause":
                self._state["paused"] = True
                self._state["driving"] = False
                self._state["velocity"] = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
            elif action_type == "stopPause":
                self._state["paused"] = False
            elif action_type == "cancelOrder":
                self._cancel_order()
            elif action_type == "factsheetRequest":
                factsheet_requested = True
            else:
                status = "FAILED"
                result = f"Unsupported instant action: {action_type}"
                self._add_error("instantActionError", result)

            self._upsert_action_state(
                action_id=action_id,
                action_type=action_type,
                status=status,
                result=result,
            )
        return factsheet_requested

    def tick(self) -> None:
        """Advance one deterministic simulation phase."""
        if self._state["paused"]:
            self._state["driving"] = False
            self._state["velocity"] = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
            return

        if self._in_transit_edge is not None:
            self._finish_current_edge()
            return

        remaining_edges = sorted(
            self._state["edgeStates"], key=lambda edge: edge["sequenceId"]
        )
        if not remaining_edges:
            self._state["driving"] = False
            self._state["velocity"] = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
            self._state["newBaseRequest"] = False
            return

        edge = remaining_edges[0]
        destination = self._find_node_state(edge["sequenceId"] + 1)
        if not edge["released"] or destination is None or not destination["released"]:
            self._state["driving"] = False
            self._state["velocity"] = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
            self._state["newBaseRequest"] = True
            return

        self._in_transit_edge = edge["sequenceId"]
        self._state["driving"] = True
        self._state["velocity"] = {"vx": 0.5, "vy": 0.0, "omega": 0.0}
        self._set_element_actions(edge["sequenceId"], "RUNNING")

    def state_message(self) -> dict[str, Any]:
        message = self.headers.next(
            "state",
            self.settings.vda_version,
            self.settings.manufacturer,
            self.settings.serial_number,
        )
        message.update(deepcopy(self._state))
        return message

    def visualization_message(self) -> dict[str, Any]:
        message = self.headers.next(
            "visualization",
            self.settings.vda_version,
            self.settings.manufacturer,
            self.settings.serial_number,
        )
        message.update(
            {
                "agvPosition": deepcopy(self._state["agvPosition"]),
                "velocity": deepcopy(self._state["velocity"]),
            }
        )
        return message

    def connection_message(self, connection_state: str) -> dict[str, Any]:
        message = self.headers.next(
            "connection",
            self.settings.vda_version,
            self.settings.manufacturer,
            self.settings.serial_number,
        )
        message["connectionState"] = connection_state
        return message

    def factsheet_message(self) -> dict[str, Any]:
        message = self.headers.next(
            "factsheet",
            self.settings.vda_version,
            self.settings.manufacturer,
            self.settings.serial_number,
        )
        message.update(
            {
                "typeSpecification": {
                    "seriesName": "Python VDA5050 Simulator",
                    "seriesDescription": "Single-robot simulator for FMS development",
                    "agvKinematic": "DIFF",
                    "agvClass": "CARRIER",
                    "maxLoadMass": 1000.0,
                    "localizationTypes": ["NATURAL"],
                    "navigationTypes": ["VIRTUAL_LINE_GUIDED"],
                },
                "physicalParameters": {
                    "speedMin": 0.0,
                    "speedMax": 1.5,
                    "accelerationMax": 0.5,
                    "decelerationMax": 0.8,
                    "heightMax": 1.0,
                    "width": 0.8,
                    "length": 1.2,
                },
                "protocolLimits": {
                    "maxStringLens": {},
                    "maxArrayLens": {},
                    "timing": {
                        "minOrderInterval": 0.1,
                        "minStateInterval": 0.1,
                        "defaultStateInterval": self.settings.state_interval_seconds,
                        "visualizationInterval": self.settings.visualization_interval_seconds,
                    },
                },
                "protocolFeatures": {
                    "optionalParameters": [],
                    "agvActions": [
                        {
                            "actionType": action_type,
                            "actionScopes": ["INSTANT"],
                        }
                        for action_type in (
                            "startPause",
                            "stopPause",
                            "cancelOrder",
                            "factsheetRequest",
                        )
                    ],
                },
                "agvGeometry": {},
                "loadSpecification": {},
            }
        )
        return message

    def _finish_current_edge(self) -> None:
        edge_sequence = self._in_transit_edge
        if edge_sequence is None:
            return
        destination_sequence = edge_sequence + 1
        destination = self._route_nodes.get(destination_sequence)

        self._state["edgeStates"] = [
            edge
            for edge in self._state["edgeStates"]
            if edge["sequenceId"] != edge_sequence
        ]
        self._state["nodeStates"] = [
            node
            for node in self._state["nodeStates"]
            if node["sequenceId"] != destination_sequence
        ]
        self._set_element_actions(edge_sequence, "FINISHED")
        self._set_element_actions(destination_sequence, "FINISHED")

        if destination is not None:
            self._state["lastNodeId"] = destination["nodeId"]
            self._state["lastNodeSequenceId"] = destination_sequence
            self._apply_position(destination.get("nodePosition"))
        self._in_transit_edge = None
        self._state["driving"] = False
        self._state["velocity"] = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
        self._update_base_request()

    def _cancel_order(self) -> None:
        self._state["nodeStates"] = []
        self._state["edgeStates"] = []
        self._state["driving"] = False
        self._state["newBaseRequest"] = False
        self._state["velocity"] = {"vx": 0.0, "vy": 0.0, "omega": 0.0}
        self._in_transit_edge = None
        for action in self._state["actionStates"]:
            if action["actionStatus"] not in {"FINISHED", "FAILED"}:
                action["actionStatus"] = "FAILED"
                action["resultDescription"] = "Order cancelled"

    def _merge_order_actions(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        last_sequence: int,
    ) -> None:
        existing = {
            action["actionId"]: action for action in self._state["actionStates"]
        }
        for element in [*nodes, *edges]:
            for action in element["actions"]:
                previous = existing.get(action["actionId"])
                status = (
                    previous["actionStatus"]
                    if previous is not None
                    else (
                        "FINISHED"
                        if element["sequenceId"] <= last_sequence
                        else "WAITING"
                    )
                )
                self._upsert_action_state(
                    action_id=action["actionId"],
                    action_type=action["actionType"],
                    status=status,
                )

    def _set_element_actions(self, sequence_id: int, status: str) -> None:
        element = self._route_nodes.get(sequence_id) or self._route_edges.get(
            sequence_id
        )
        if element is None:
            return
        for action in element.get("actions", []):
            self._upsert_action_state(
                action_id=action["actionId"],
                action_type=action["actionType"],
                status=status,
            )

    def _upsert_action_state(
        self,
        *,
        action_id: str,
        action_type: str,
        status: str,
        result: str = "",
    ) -> None:
        found = next(
            (
                action
                for action in self._state["actionStates"]
                if action["actionId"] == action_id
            ),
            None,
        )
        if found is None:
            found = {
                "actionId": action_id,
                "actionType": action_type,
                "actionStatus": status,
            }
            self._state["actionStates"].append(found)
        else:
            found["actionType"] = action_type
            found["actionStatus"] = status
        if result:
            found["resultDescription"] = result

    def _find_node_state(self, sequence_id: int) -> dict[str, Any] | None:
        return next(
            (
                node
                for node in self._state["nodeStates"]
                if node["sequenceId"] == sequence_id
            ),
            None,
        )

    def _update_base_request(self) -> None:
        edge_states = self._state["edgeStates"]
        self._state["newBaseRequest"] = bool(edge_states) and not any(
            edge["released"] for edge in edge_states
        )

    def _apply_position(self, position: dict[str, Any] | None) -> None:
        if not position:
            return
        self._state["agvPosition"].update(
            {
                "x": position["x"],
                "y": position["y"],
                "theta": position.get("theta", self._state["agvPosition"]["theta"]),
                "mapId": position["mapId"],
            }
        )

    @staticmethod
    def _node_state(node: dict[str, Any]) -> dict[str, Any]:
        state = {
            "nodeId": node["nodeId"],
            "sequenceId": node["sequenceId"],
            "released": node["released"],
        }
        if "nodeDescription" in node:
            state["nodeDescription"] = node["nodeDescription"]
        if "nodePosition" in node:
            state["nodePosition"] = deepcopy(node["nodePosition"])
        return state

    @staticmethod
    def _edge_state(edge: dict[str, Any]) -> dict[str, Any]:
        state = {
            "edgeId": edge["edgeId"],
            "sequenceId": edge["sequenceId"],
            "released": edge["released"],
        }
        if "edgeDescription" in edge:
            state["edgeDescription"] = edge["edgeDescription"]
        if "trajectory" in edge:
            state["trajectory"] = deepcopy(edge["trajectory"])
        return state

    def _verify_identity(self, payload: dict[str, Any]) -> None:
        if payload["manufacturer"] != self.settings.manufacturer:
            raise ValueError("manufacturer does not address this simulated robot")
        if payload["serialNumber"] != self.settings.serial_number:
            raise ValueError("serialNumber does not address this simulated robot")
        if payload["version"] != self.settings.vda_version:
            raise ValueError("VDA version does not match the simulated robot")

    def _add_error(self, error_type: str, description: str) -> None:
        self._state["errors"].append(
            {
                "errorType": error_type,
                "errorDescription": description[:500],
                "errorLevel": "WARNING",
            }
        )
        self._state["errors"] = self._state["errors"][-20:]


class RobotSimulator:
    """MQTT adapter around :class:`RobotModel`."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.registry = SchemaRegistry(settings.vda_version)
        self.layout = TopicLayout(
            settings.interface_name,
            settings.vda_version,
            settings.manufacturer,
            settings.serial_number,
        )
        self.model = RobotModel(settings)
        self.client = JsonMqttClient(settings)
        self._incoming: Queue[tuple[str, dict[str, Any]]] = Queue()
        self._stopped = threading.Event()

        self.client.add_subscription(
            self.layout.robot_topic("order"), 0, self._enqueue_order
        )
        self.client.add_subscription(
            self.layout.robot_topic("instantActions"),
            0,
            self._enqueue_instant_actions,
        )
        self.client.set_will(
            self.layout.robot_topic("connection"),
            self.model.connection_message("CONNECTIONBROKEN"),
            qos=1,
            retain=True,
        )

    def run(self) -> None:
        connected = False
        try:
            self.client.connect()
            connected = True
            self._publish("connection", self.model.connection_message("ONLINE"), 1, True)
            self._publish("factsheet", self.model.factsheet_message(), 0, False)
            self._publish_state()
            LOGGER.info(
                "Simulator %s/%s started; press Ctrl+C to stop",
                self.settings.manufacturer,
                self.settings.serial_number,
            )

            next_step = monotonic() + self.settings.simulation_step_seconds
            next_state = monotonic() + self.settings.state_interval_seconds
            next_visualization = (
                monotonic() + self.settings.visualization_interval_seconds
            )

            while not self._stopped.is_set():
                now = monotonic()
                deadline = min(next_step, next_state, next_visualization)
                timeout = max(0.0, deadline - now)
                try:
                    kind, message = self._incoming.get(timeout=timeout)
                    if kind == "order":
                        self.model.handle_order(message)
                    else:
                        if self.model.handle_instant_actions(message):
                            self._publish(
                                "factsheet", self.model.factsheet_message(), 0, False
                            )
                    self._publish_state()
                except Empty:
                    pass

                now = monotonic()
                if now >= next_step:
                    self.model.tick()
                    next_step = now + self.settings.simulation_step_seconds
                if now >= next_state:
                    self._publish_state()
                    next_state = now + self.settings.state_interval_seconds
                if now >= next_visualization:
                    self._publish(
                        "visualization",
                        self.model.visualization_message(),
                        0,
                        False,
                    )
                    next_visualization = (
                        now + self.settings.visualization_interval_seconds
                    )
        except KeyboardInterrupt:
            LOGGER.info("Stopping simulator")
        finally:
            if connected:
                try:
                    self._publish(
                        "connection",
                        self.model.connection_message("OFFLINE"),
                        1,
                        True,
                        wait=True,
                    )
                finally:
                    self.client.disconnect()

    def stop(self) -> None:
        self._stopped.set()

    def _enqueue_order(
        self, topic: str, payload: dict[str, Any], retained: bool
    ) -> None:
        self._incoming.put(("order", payload))

    def _enqueue_instant_actions(
        self, topic: str, payload: dict[str, Any], retained: bool
    ) -> None:
        self._incoming.put(("instantActions", payload))

    def _publish_state(self) -> None:
        self._publish("state", self.model.state_message(), 0, False)

    def _publish(
        self,
        topic_name: str,
        payload: dict[str, Any],
        qos: int,
        retain: bool,
        *,
        wait: bool = False,
    ) -> None:
        self.registry.validate(topic_name, payload)
        self.client.publish_json(
            self.layout.robot_topic(topic_name),
            payload,
            qos=qos,
            retain=retain,
            wait=wait,
        )

from vda5050_fms.messages import build_demo_order, utc_timestamp
from vda5050_fms.simulator import RobotModel
from vda5050_fms.validation import SchemaRegistry


def _order(settings):
    return build_demo_order(
        version=settings.vda_version,
        manufacturer=settings.manufacturer,
        serial_number=settings.serial_number,
        map_id=settings.simulation_map_id,
    )


def test_robot_accepts_and_completes_demo_order(settings) -> None:
    model = RobotModel(settings)

    assert model.handle_order(_order(settings))
    assert model.state["orderId"].startswith("demo-")
    assert len(model.state["edgeStates"]) == 1
    assert not model.is_idle

    model.tick()
    assert model.state["driving"] is True

    model.tick()
    assert model.state["driving"] is False
    assert model.state["lastNodeId"] == "N1"
    assert model.state["lastNodeSequenceId"] == 2
    assert model.is_idle
    SchemaRegistry("2.1.0").validate("state", model.state_message())


def test_unreleased_horizon_requests_new_base(settings) -> None:
    model = RobotModel(settings)
    order = _order(settings)
    order["edges"][0]["released"] = False
    order["nodes"][1]["released"] = False

    assert model.handle_order(order)
    model.tick()

    assert model.state["driving"] is False
    assert model.state["newBaseRequest"] is True


def test_pause_resume_and_cancel(settings) -> None:
    model = RobotModel(settings)
    assert model.handle_order(_order(settings))

    pause = {
        "headerId": 0,
        "timestamp": utc_timestamp(),
        "version": settings.vda_version,
        "manufacturer": settings.manufacturer,
        "serialNumber": settings.serial_number,
        "actions": [
            {
                "actionId": "pause-1",
                "actionType": "startPause",
                "blockingType": "HARD",
            }
        ],
    }
    assert model.handle_instant_actions(pause) is False
    assert model.state["paused"] is True

    resume = {
        **pause,
        "headerId": 1,
        "actions": [
            {
                "actionId": "resume-1",
                "actionType": "stopPause",
                "blockingType": "HARD",
            }
        ],
    }
    model.handle_instant_actions(resume)
    assert model.state["paused"] is False

    cancel = {
        **pause,
        "headerId": 2,
        "actions": [
            {
                "actionId": "cancel-1",
                "actionType": "cancelOrder",
                "blockingType": "HARD",
            }
        ],
    }
    model.handle_instant_actions(cancel)
    assert model.state["nodeStates"] == []
    assert model.state["edgeStates"] == []


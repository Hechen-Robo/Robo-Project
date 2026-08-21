const ROBOT_MANUFACTURER = "TEST";
const ROBOT_SERIAL_NUMBER = "AGV-001";

const ROBOT_ANIMATION_MS = 450;
const WEBSOCKET_RECONNECT_MS = 2000;

const MAP_ORIGIN_X = 70;
const MAP_ORIGIN_Y = 700;
const MAP_SCALE_X = 90;
const MAP_SCALE_Y = 80;


const elements = {
    serviceStatus: document.querySelector(
        "#service-status"
    ),
    serviceStatusText: document.querySelector(
        "#service-status-text"
    ),
    serviceName: document.querySelector(
        "#service-name"
    ),
    vdaVersion: document.querySelector(
        "#vda-version"
    ),
    dataSource: document.querySelector(
        "#data-source"
    ),
    lastUpdate: document.querySelector(
        "#last-update"
    ),

    connectionState: document.querySelector(
        "#connection-state"
    ),
    operatingMode: document.querySelector(
        "#operating-mode"
    ),
    drivingState: document.querySelector(
        "#driving-state"
    ),
    estopState: document.querySelector(
        "#estop-state"
    ),
    fieldViolation: document.querySelector(
        "#field-violation"
    ),

    positionX: document.querySelector(
        "#position-x"
    ),
    positionY: document.querySelector(
        "#position-y"
    ),
    positionTheta: document.querySelector(
        "#position-theta"
    ),
    velocityX: document.querySelector(
        "#velocity-x"
    ),

    batteryCharge: document.querySelector(
        "#battery-charge"
    ),
    batteryProgress: document.querySelector(
        "#battery-progress"
    ),
    chargingState: document.querySelector(
        "#charging-state"
    ),

    orderId: document.querySelector(
        "#order-id"
    ),
    lastNode: document.querySelector(
        "#last-node"
    ),
    remainingNodes: document.querySelector(
        "#remaining-nodes"
    ),
    remainingEdges: document.querySelector(
        "#remaining-edges"
    ),
    orderUpdateId: document.querySelector(
        "#order-update-id"
    ),

    localizationScore: document.querySelector(
        "#localization-score"
    ),
    mapId: document.querySelector(
        "#map-id"
    ),
    positionInitialized: document.querySelector(
        "#position-initialized"
    ),

    errorCount: document.querySelector(
        "#error-count"
    ),
    errorMessage: document.querySelector(
        "#error-message"
    ),
    liveBadge: document.querySelector(
        "#live-badge"
    ),
    streamStatus: document.querySelector(
        "#stream-status"
    ),
    robotMarker: document.querySelector(
        "#robot-marker"
    ),
    robotLabel: document.querySelector(
        "#robot-label"
    ),
};


let robotSocket = null;
let reconnectTimer = null;
let pageIsClosing = false;
let robotAnimationFrame = null;

let renderedRobotPose = {
    x: 205,
    y: 580,
    angle: 0,
};


function setText(element, value) {
    if (element !== null) {
        element.textContent = value;
    }
}


function setValueClass(element, className) {
    if (element === null) {
        return;
    }

    element.classList.remove(
        "value-pending",
        "value-online",
        "value-info",
        "value-warning",
        "value-error"
    );

    element.classList.add(className);
}


function setServiceStatus(state, text) {
    elements.serviceStatus.classList.remove(
        "status-loading",
        "status-online",
        "status-error"
    );

    elements.serviceStatus.classList.add(state);

    setText(
        elements.serviceStatusText,
        text
    );
}

function worldToMap(x, y) {
    const lifMapPosition = (
        window.lifMapController
            ?.worldToMap(x, y)
    );

    if (
        lifMapPosition !== null
        && lifMapPosition !== undefined
    ) {
        return lifMapPosition;
    }

    return {
        x: MAP_ORIGIN_X + x * MAP_SCALE_X,
        y: MAP_ORIGIN_Y - y * MAP_SCALE_Y,
    };
}


function shortestAngleDifference(
    startAngle,
    targetAngle
) {
    return (
        (targetAngle - startAngle + 540) % 360
    ) - 180;
}


function applyRobotTransform(x, y, angle) {
    elements.robotMarker.setAttribute(
        "transform",
        `translate(${x} ${y}) rotate(${angle})`
    );

    elements.robotLabel.setAttribute(
        "transform",
        `translate(${x} ${y})`
    );
}


function animateRobotTo(
    targetX,
    targetY,
    targetAngle
) {
    if (robotAnimationFrame !== null) {
        window.cancelAnimationFrame(
            robotAnimationFrame
        );
    }

    const startPose = {
        ...renderedRobotPose,
    };

    const angleDifference =
        shortestAngleDifference(
            startPose.angle,
            targetAngle
        );

    const animationStart = performance.now();

    function animationStep(currentTime) {
        const elapsed = currentTime - animationStart;

        const progress = Math.min(
            elapsed / ROBOT_ANIMATION_MS,
            1
        );

        const x = startPose.x
            + (targetX - startPose.x) * progress;

        const y = startPose.y
            + (targetY - startPose.y) * progress;

        const angle = startPose.angle
            + angleDifference * progress;

        renderedRobotPose = {
            x,
            y,
            angle,
        };

        applyRobotTransform(x, y, angle);

        if (progress < 1) {
            robotAnimationFrame =
                window.requestAnimationFrame(
                    animationStep
                );
        } else {
            robotAnimationFrame = null;
        }
    }

    robotAnimationFrame =
        window.requestAnimationFrame(
            animationStep
        );
}


function updateActiveNode(lastNodeId) {
    const routeNodes = document.querySelectorAll(
        ".route-node"
    );

    for (const routeNode of routeNodes) {
        const nodeText = routeNode.querySelector(
            "text"
        );

        const nodeId = (
            routeNode.dataset.nodeId
            ?? (
                nodeText?.textContent ?? ""
            ).trim()
        );

        routeNode.classList.toggle(
            "active-node",
            nodeId === lastNodeId
        );
    }
}


function updateConnection(connection) {
    const connectionState =
        connection.connectionState;

    setText(
        elements.connectionState,
        connectionState
    );

    if (connectionState === "ONLINE") {
        setValueClass(
            elements.connectionState,
            "value-online"
        );
    } else if (connectionState === "OFFLINE") {
        setValueClass(
            elements.connectionState,
            "value-warning"
        );
    } else {
        setValueClass(
            elements.connectionState,
            "value-error"
        );
    }
}


function updateState(state) {
    setText(
        elements.operatingMode,
        state.operatingMode
    );

    setValueClass(
        elements.operatingMode,
        "value-info"
    );

    setText(
        elements.drivingState,
        state.driving ? "DRIVING" : "STOPPED"
    );

    setValueClass(
        elements.drivingState,
        state.driving
            ? "value-online"
            : "value-warning"
    );

    const safetyState = state.safetyState;

    setText(
        elements.estopState,
        safetyState.eStop
    );

    setValueClass(
        elements.estopState,
        safetyState.eStop === "NONE"
            ? "value-online"
            : "value-error"
    );

    setText(
        elements.fieldViolation,
        safetyState.fieldViolation
            ? "TRUE"
            : "FALSE"
    );

    setValueClass(
        elements.fieldViolation,
        safetyState.fieldViolation
            ? "value-error"
            : "value-online"
    );

    const batteryCharge =
        state.batteryState.batteryCharge;

    setText(
        elements.batteryCharge,
        batteryCharge.toFixed(1)
    );

    elements.batteryProgress.style.width =
        `${Math.min(
            Math.max(batteryCharge, 0),
            100
        )}%`;

    setText(
        elements.chargingState,
        state.batteryState.charging
            ? "CHARGING"
            : "NOT CHARGING"
    );

    setText(
        elements.orderId,
        state.orderId || "NO ACTIVE ORDER"
    );

    setText(
        elements.lastNode,
        state.lastNodeId || "--"
    );

    setText(
        elements.remainingNodes,
        String(state.nodeStates.length)
    );

    setText(
        elements.remainingEdges,
        String(state.edgeStates.length)
    );

    setText(
        elements.orderUpdateId,
        String(state.orderUpdateId)
    );

    updateActiveNode(state.lastNodeId);

    const errors = state.errors ?? [];

    setText(
        elements.errorCount,
        String(errors.length)
    );

    if (errors.length === 0) {
        setText(
            elements.errorMessage,
            "当前没有活动错误。"
        );

        elements.errorMessage.classList.remove(
            "error-active"
        );
    } else {
        const firstError = errors[0];

        setText(
            elements.errorMessage,
            firstError.errorDescription
                ?? firstError.errorType
                ?? "机器人报告了活动错误。"
        );

        elements.errorMessage.classList.add(
            "error-active"
        );
    }
}


function updateVisualization(visualization) {
    const position = visualization.agvPosition;
    const velocity = visualization.velocity;

    setText(
        elements.positionX,
        `${position.x.toFixed(2)} m`
    );

    setText(
        elements.positionY,
        `${position.y.toFixed(2)} m`
    );

    setText(
        elements.positionTheta,
        `${position.theta.toFixed(2)} rad`
    );

    setText(
        elements.velocityX,
        `${(velocity?.vx ?? 0).toFixed(2)} m/s`
    );

    setText(
        elements.localizationScore,
        (
            (position.localizationScore ?? 0)
            * 100
        ).toFixed(1)
    );

    setText(
        elements.mapId,
        position.mapId
    );

    setText(
        elements.positionInitialized,
        position.positionInitialized
            ? "TRUE"
            : "FALSE"
    );

    const lifMapController =
        window.lifMapController;

    if (
        lifMapController?.hasActiveLayout()
        && !lifMapController.acceptsRobotMapId(
            position.mapId
        )
    ) {
        return;
    }

    const mapPosition = worldToMap(
        position.x,
        position.y
    );

    const svgAngle = (
        -position.theta * 180 / Math.PI
    );

    animateRobotTo(
        mapPosition.x,
        mapPosition.y,
        svgAngle
    );
}


async function loadHealth() {
    try {
        const response = await fetch(
            "/api/health",
            {
                cache: "no-store",
            }
        );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        const health = await response.json();

        setText(
            elements.serviceName,
            health.service
        );

        setText(
            elements.vdaVersion,
            health.vda5050Version
        );

        setText(
            elements.dataSource,
            health.dataSource.toUpperCase()
        );

        setText(
            elements.lastUpdate,
            new Date(
                health.timestamp
            ).toLocaleTimeString(
                "zh-CN",
                {
                    hour12: false,
                }
            )
        );

        setServiceStatus(
            "status-online",
            "HMI SERVICE READY"
        );
    } catch (error) {
        console.error(
            "HMI health check failed:",
            error
        );

        setServiceStatus(
            "status-error",
            "HMI SERVICE UNAVAILABLE"
        );
    }
}

function setStreamStatus(state, text) {
    elements.liveBadge.classList.remove(
        "stream-connecting",
        "stream-online",
        "stream-error"
    );

    elements.liveBadge.classList.add(state);

    setText(
        elements.streamStatus,
        text
    );
}


function handleRobotSnapshot(snapshot) {
    updateConnection(snapshot.connection);
    updateState(snapshot.state);
    updateVisualization(
        snapshot.visualization
    );
}


function buildRobotWebSocketUrl() {
    const protocol = (
        window.location.protocol === "https:"
            ? "wss:"
            : "ws:"
    );

    const manufacturer = encodeURIComponent(
        ROBOT_MANUFACTURER
    );

    const serialNumber = encodeURIComponent(
        ROBOT_SERIAL_NUMBER
    );

    return (
        `${protocol}//${window.location.host}`
        + `/ws/robots/${manufacturer}`
        + `/${serialNumber}/snapshot`
    );
}


function scheduleWebSocketReconnect() {
    if (
        pageIsClosing
        || reconnectTimer !== null
    ) {
        return;
    }

    setStreamStatus(
        "stream-error",
        "RECONNECTING..."
    );

    reconnectTimer = window.setTimeout(
        () => {
            reconnectTimer = null;
            connectRobotWebSocket();
        },
        WEBSOCKET_RECONNECT_MS
    );
}


function connectRobotWebSocket() {
    if (
        robotSocket !== null
        && (
            robotSocket.readyState
                === WebSocket.OPEN
            || robotSocket.readyState
                === WebSocket.CONNECTING
        )
    ) {
        return;
    }

    setStreamStatus(
        "stream-connecting",
        "CONNECTING..."
    );

    const socket = new WebSocket(
        buildRobotWebSocketUrl()
    );

    robotSocket = socket;

    socket.addEventListener(
        "open",
        () => {
            if (reconnectTimer !== null) {
                window.clearTimeout(
                    reconnectTimer
                );
                reconnectTimer = null;
            }

            setStreamStatus(
                "stream-online",
                "LIVE · WEBSOCKET"
            );
        }
    );

    socket.addEventListener(
        "message",
        (event) => {
            try {
                const snapshot = JSON.parse(
                    event.data
                );

                handleRobotSnapshot(snapshot);
            } catch (error) {
                console.error(
                    "Invalid WebSocket snapshot:",
                    error
                );
            }
        }
    );

    socket.addEventListener(
        "error",
        (error) => {
            console.error(
                "Robot WebSocket error:",
                error
            );
        }
    );

    socket.addEventListener(
        "close",
        () => {
            if (robotSocket === socket) {
                robotSocket = null;
            }

            if (pageIsClosing) {
                return;
            }

            setText(
                elements.errorMessage,
                "实时数据连接中断，正在重连……"
            );

            elements.errorMessage.classList.add(
                "error-active"
            );

            scheduleWebSocketReconnect();
        }
    );
}


function closeRobotWebSocket() {
    pageIsClosing = true;

    if (reconnectTimer !== null) {
        window.clearTimeout(
            reconnectTimer
        );
        reconnectTimer = null;
    }

    if (robotSocket !== null) {
        robotSocket.close(
            1000,
            "HMI page closed."
        );
    }
}

loadHealth();
connectRobotWebSocket();

window.setInterval(
    loadHealth,
    5000
);

window.addEventListener(
    "beforeunload",
    closeRobotWebSocket
);
(() => {
    "use strict";

    const SVG_NAMESPACE =
        "http://www.w3.org/2000/svg";

    const VIEWBOX_WIDTH = 1000;
    const VIEWBOX_HEIGHT = 720;
    const MAP_PADDING = 80;

    const STATUS_CLASSES = [
        "map-status-idle",
        "map-status-loading",
        "map-status-success",
        "map-status-error",
    ];

    const elements = {
        fileInput: document.querySelector(
            "#lif-file-input"
        ),
        layoutSelect: document.querySelector(
            "#lif-layout-select"
        ),
        importStatus: document.querySelector(
            "#lif-import-status"
        ),
        mapLayer: document.querySelector(
            "#lif-map-layer"
        ),
        layoutName: document.querySelector(
            "#map-layout-name"
        ),
        layoutMeta: document.querySelector(
            "#map-layout-meta"
        ),
    };

    let activeLayout = null;
    let activeTransform = null;
    let mapMismatchActive = false;


    function setImportStatus(
        text,
        state = "idle"
    ) {
        elements.importStatus.classList.remove(
            ...STATUS_CLASSES
        );

        elements.importStatus.classList.add(
            `map-status-${state}`
        );

        elements.importStatus.textContent = text;
    }


    function createSvgElement(
        elementName,
        attributes = {}
    ) {
        const element = document.createElementNS(
            SVG_NAMESPACE,
            elementName
        );

        for (
            const [attributeName, value]
            of Object.entries(attributes)
        ) {
            element.setAttribute(
                attributeName,
                String(value)
            );
        }

        return element;
    }


    function calculateMapTransform(bounds) {
        const worldWidth = Math.max(
            bounds.maxX - bounds.minX,
            0
        );

        const worldHeight = Math.max(
            bounds.maxY - bounds.minY,
            0
        );

        const availableWidth =
            VIEWBOX_WIDTH - 2 * MAP_PADDING;

        const availableHeight =
            VIEWBOX_HEIGHT - 2 * MAP_PADDING;

        const scale = Math.min(
            availableWidth
                / Math.max(worldWidth, 1),
            availableHeight
                / Math.max(worldHeight, 1)
        );

        const renderedWidth = worldWidth * scale;
        const renderedHeight = worldHeight * scale;

        return {
            minX: bounds.minX,
            maxY: bounds.maxY,
            scale,
            offsetX: (
                VIEWBOX_WIDTH - renderedWidth
            ) / 2,
            offsetY: (
                VIEWBOX_HEIGHT - renderedHeight
            ) / 2,
        };
    }


    function worldToMap(x, y) {
        if (activeTransform === null) {
            return null;
        }

        return {
            x: (
                activeTransform.offsetX
                + (
                    x - activeTransform.minX
                ) * activeTransform.scale
            ),
            y: (
                activeTransform.offsetY
                + (
                    activeTransform.maxY - y
                ) * activeTransform.scale
            ),
        };
    }


    function renderEdges(
        edges,
        nodePositions
    ) {
        for (const edge of edges) {
            const startPosition =
                nodePositions.get(
                    edge.startNodeId
                );

            const endPosition =
                nodePositions.get(
                    edge.endNodeId
                );

            if (
                startPosition === undefined
                || endPosition === undefined
            ) {
                console.warn(
                    "LIF edge cannot be rendered:",
                    edge.edgeId
                );
                continue;
            }

            const edgeGroup = createSvgElement(
                "g",
                {
                    class: "lif-edge",
                    "data-edge-id": edge.edgeId,
                }
            );

            edgeGroup.append(
                createSvgElement(
                    "line",
                    {
                        class: "route-background",
                        x1: startPosition.x,
                        y1: startPosition.y,
                        x2: endPosition.x,
                        y2: endPosition.y,
                    }
                ),
                createSvgElement(
                    "line",
                    {
                        class: "route-line",
                        x1: startPosition.x,
                        y1: startPosition.y,
                        x2: endPosition.x,
                        y2: endPosition.y,
                    }
                )
            );

            elements.mapLayer.append(edgeGroup);
        }
    }


    function renderStations(
        stations,
        nodePositions
    ) {
        for (const station of stations) {
            let position = null;

            if (station.position !== null) {
                position = worldToMap(
                    station.position.x,
                    station.position.y
                );
            }

            if (
                position === null
                && station.interactionNodeIds.length
                    > 0
            ) {
                position = nodePositions.get(
                    station.interactionNodeIds[0]
                ) ?? null;
            }

            if (position === null) {
                continue;
            }

            const stationGroup = createSvgElement(
                "g",
                {
                    class: "lif-station",
                    transform: (
                        `translate(`
                        + `${position.x} `
                        + `${position.y})`
                    ),
                    "data-station-id":
                        station.stationId,
                }
            );

            const stationBox = createSvgElement(
                "rect",
                {
                    x: -15,
                    y: -15,
                    width: 30,
                    height: 30,
                    rx: 4,
                }
            );

            const stationLabel = createSvgElement(
                "text",
                {
                    x: 21,
                    y: -19,
                }
            );

            stationLabel.textContent = (
                station.stationName
                || station.stationId
            );

            stationGroup.append(
                stationBox,
                stationLabel
            );

            elements.mapLayer.append(
                stationGroup
            );
        }
    }


    function renderNodes(
        nodes,
        nodePositions
    ) {
        for (const node of nodes) {
            const position = nodePositions.get(
                node.nodeId
            );

            if (position === undefined) {
                continue;
            }

            const nodeGroup = createSvgElement(
                "g",
                {
                    class: "route-node",
                    "data-node-id": node.nodeId,
                }
            );

            const nodeCircle = createSvgElement(
                "circle",
                {
                    cx: position.x,
                    cy: position.y,
                    r: 10,
                }
            );

            const nodeLabel = createSvgElement(
                "text",
                {
                    x: position.x + 15,
                    y: position.y - 13,
                }
            );

            nodeLabel.textContent = (
                node.nodeName
                    ? (
                        `${node.nodeId} · `
                        + node.nodeName
                    )
                    : node.nodeId
            );

            nodeGroup.append(
                nodeCircle,
                nodeLabel
            );

            elements.mapLayer.append(nodeGroup);
        }
    }


    function renderLifLayout(layout) {
        activeLayout = layout;
        activeTransform = calculateMapTransform(
            layout.bounds
        );
        mapMismatchActive = false;

        elements.mapLayer.replaceChildren();

        const nodePositions = new Map();

        for (const node of layout.nodes) {
            nodePositions.set(
                node.nodeId,
                worldToMap(
                    node.position.x,
                    node.position.y
                )
            );
        }

        renderEdges(
            layout.edges,
            nodePositions
        );

        renderStations(
            layout.stations,
            nodePositions
        );

        renderNodes(
            layout.nodes,
            nodePositions
        );

        elements.layoutName.textContent = (
            layout.layoutName
            || layout.layoutId
        );

        elements.layoutMeta.textContent = (
            `/ ${layout.layoutId}`
            + ` · v${layout.layoutVersion}`
        );
    }


    async function requestJson(
        url,
        options = {}
    ) {
        const response = await fetch(
            url,
            {
                cache: "no-store",
                ...options,
            }
        );

        let payload = null;

        try {
            payload = await response.json();
        } catch {
            payload = null;
        }

        if (!response.ok) {
            const detail = (
                typeof payload?.detail === "string"
                    ? payload.detail
                    : `HTTP ${response.status}`
            );

            throw new Error(detail);
        }

        return payload;
    }


    function populateLayoutSelect(layouts) {
        elements.layoutSelect.replaceChildren();

        if (layouts.length === 0) {
            const option = document.createElement(
                "option"
            );

            option.value = "";
            option.textContent = "NO LIF LAYOUT";

            elements.layoutSelect.append(option);
            elements.layoutSelect.disabled = true;
            return;
        }

        for (const layout of layouts) {
            const option = document.createElement(
                "option"
            );

            option.value = layout.layoutId;
            option.textContent = (
                layout.layoutName
                    ? (
                        `${layout.layoutName} · `
                        + layout.layoutId
                    )
                    : layout.layoutId
            );

            elements.layoutSelect.append(option);
        }

        elements.layoutSelect.disabled = false;
    }


    async function loadLayout(layoutId) {
        setImportStatus(
            "LOADING MAP...",
            "loading"
        );

        try {
            const layout = await requestJson(
                `/api/maps/${
                    encodeURIComponent(layoutId)
                }`
            );

            renderLifLayout(layout);
            elements.layoutSelect.value =
                layout.layoutId;

            setImportStatus(
                `ACTIVE · ${layout.layoutId}`,
                "success"
            );
        } catch (error) {
            console.error(
                "LIF layout loading failed:",
                error
            );

            setImportStatus(
                error.message,
                "error"
            );

            throw error;
        }
    }


    async function uploadLifFile(file) {
        const formData = new FormData();
        formData.append("file", file, file.name);

        setImportStatus(
            "UPLOADING...",
            "loading"
        );

        const result = await requestJson(
            "/api/maps/lif",
            {
                method: "POST",
                body: formData,
            }
        );

        const layouts = result.layouts ?? [];

        populateLayoutSelect(layouts);

        if (layouts.length === 0) {
            throw new Error(
                "Imported LIF contains no layouts."
            );
        }

        await loadLayout(layouts[0].layoutId);
    }


    async function handleFileSelection(event) {
        const file = event.target.files?.[0];

        if (file === undefined) {
            return;
        }

        try {
            await uploadLifFile(file);
        } catch (error) {
            console.error(
                "LIF upload failed:",
                error
            );

            setImportStatus(
                error.message,
                "error"
            );
        } finally {
            elements.fileInput.value = "";
        }
    }


    async function loadAvailableLayouts() {
        try {
            const result = await requestJson(
                "/api/maps"
            );

            const layouts = result.layouts ?? [];

            populateLayoutSelect(layouts);

            if (layouts.length === 0) {
                setImportStatus(
                    "DEMO MAP",
                    "idle"
                );
                return;
            }

            await loadLayout(layouts[0].layoutId);
        } catch (error) {
            console.error(
                "LIF map list loading failed:",
                error
            );

            setImportStatus(
                "MAP API ERROR",
                "error"
            );
        }
    }


    function hasActiveLayout() {
        return activeLayout !== null;
    }


    function acceptsRobotMapId(mapId) {
        if (activeLayout === null) {
            return true;
        }

        const mapIds = activeLayout.mapIds ?? [];

        if (mapIds.length === 0) {
            return true;
        }

        const accepted = mapIds.includes(mapId);

        if (!accepted) {
            mapMismatchActive = true;

            setImportStatus(
                `MAP ID MISMATCH · ${mapId}`,
                "error"
            );
        } else if (mapMismatchActive) {
            mapMismatchActive = false;

            setImportStatus(
                `ACTIVE · ${activeLayout.layoutId}`,
                "success"
            );
        }

        return accepted;
    }


    if (
        Object.values(elements).some(
            (element) => element === null
        )
    ) {
        console.error(
            "Required LIF map elements are missing."
        );
        return;
    }

    window.lifMapController = Object.freeze({
        worldToMap,
        hasActiveLayout,
        acceptsRobotMapId,
    });

    elements.fileInput.addEventListener(
        "change",
        handleFileSelection
    );

    elements.layoutSelect.addEventListener(
        "change",
        (event) => {
            if (event.target.value !== "") {
                void loadLayout(
                    event.target.value
                );
            }
        }
    );

    void loadAvailableLayouts();
})();
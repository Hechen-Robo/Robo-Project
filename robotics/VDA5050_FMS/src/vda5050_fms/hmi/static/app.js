const serviceStatus = document.querySelector("#service-status");
const serviceStatusText = document.querySelector(
    "#service-status-text"
);
const serviceName = document.querySelector("#service-name");
const vdaVersion = document.querySelector("#vda-version");
const dataSource = document.querySelector("#data-source");
const lastUpdate = document.querySelector("#last-update");


function setServiceStatus(state, text) {
    serviceStatus.classList.remove(
        "status-loading",
        "status-online",
        "status-error"
    );

    serviceStatus.classList.add(state);
    serviceStatusText.textContent = text;
}


async function loadHealth() {
    try {
        const response = await fetch("/api/health", {
            cache: "no-store",
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const health = await response.json();

        serviceName.textContent = health.service;
        vdaVersion.textContent = health.vda5050Version;
        dataSource.textContent = health.dataSource.toUpperCase();

        lastUpdate.textContent = new Date(
            health.timestamp
        ).toLocaleTimeString("zh-CN", {
            hour12: false,
        });

        setServiceStatus(
            "status-online",
            "HMI SERVICE READY"
        );
    } catch (error) {
        console.error("HMI health check failed:", error);

        setServiceStatus(
            "status-error",
            "HMI SERVICE UNAVAILABLE"
        );
    }
}


loadHealth();
window.setInterval(loadHealth, 5000);
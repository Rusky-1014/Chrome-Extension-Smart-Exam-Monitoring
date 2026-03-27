import { SERVER_BASE, API_KEY } from "./config.js";

chrome.storage.local.get(["deviceID"]).then((result) => {
    if (!result.deviceID) {
        const newID = "PC-" + Math.ceil(Math.random() * 50); // Matches the new 50-capacity HUD
        chrome.storage.local.set({ deviceID: newID });
    }
});

// Send heartbeat every 5 seconds (faster for live updates)
setInterval(async () => {
    const result = await chrome.storage.local.get(["deviceID"]);
    if (!result.deviceID) return;

    fetch(`${SERVER_BASE}/heartbeat`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            device: result.deviceID
        })
    }).catch(e => console.error(e));
}, 5000);

const suspiciousUrlKeywords = ["chatgpt", "answer", "solution", "pdf", "cheat"];

// Ensure deviceID exists (PC-1 to PC-50 for this demo)
chrome.runtime.onInstalled.addListener(async () => {
    const res = await chrome.storage.local.get(["deviceID"]);
    if (!res.deviceID) {
        let randomID = `PC-${Math.floor(Math.random() * 50) + 1}`;
        await chrome.storage.local.set({ deviceID: randomID });
    }
});

let liveMonitorInterval = null;

async function sendHeartbeat() {
    const res = await chrome.storage.local.get(["deviceID", "studentName"]);
    if (!res.deviceID) return;

    fetch(`${SERVER_BASE}/heartbeat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
            device: res.deviceID,
            student_name: res.studentName || "Unknown" 
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.monitoring === "ON" && !liveMonitorInterval) {
            startLiveMonitoring(res.deviceID);
        } else if (data.monitoring === "OFF" && liveMonitorInterval) {
            stopLiveMonitoring();
        }
    })
    .catch(e => console.error("Heartbeat sync failed:", e));
}

function startLiveMonitoring(deviceID) {
    liveMonitorInterval = setInterval(() => {
        chrome.tabs.query({active: true, lastFocusedWindow: true}, function(tabs) {
            let activeTab = tabs[0];
            // Skip capture on internal chrome pages
            if (activeTab && activeTab.url && !activeTab.url.startsWith("chrome://")) {
                chrome.tabs.captureVisibleTab(activeTab.windowId, { format: "jpeg", quality: 50 }, (dataUrl) => {
                    if (!chrome.runtime.lastError && dataUrl) {
                        fetch(`${SERVER_BASE}/live_monitoring`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ device: deviceID, screenshot: dataUrl })
                        });
                    }
                });
            }
        });
    }, 3000);
}

function stopLiveMonitoring() {
    if (liveMonitorInterval) {
        clearInterval(liveMonitorInterval);
        liveMonitorInterval = null;
    }
}

setInterval(sendHeartbeat, 5000);

async function reportViolation(url, deviceID, reason) {
    const res = await chrome.storage.local.get(["studentName"]);
    const studentName = res.studentName || "Unknown";
    
    // Safety check: Cannot capture chrome:// pages
    if (url.startsWith("chrome://")) return;

    try {
        setTimeout(() => {
            chrome.tabs.query({active: true, lastFocusedWindow: true}, function(tabs) {
                let activeTab = tabs.length > 0 ? tabs[0] : null;
                if (activeTab && activeTab.url && activeTab.url.includes(url) && !activeTab.url.startsWith("chrome://")) {
                    chrome.tabs.captureVisibleTab(activeTab.windowId, { format: "png" }, (dataUrl) => {
                        sendViolation(url, deviceID, studentName, reason, dataUrl || null);
                    });
                } else {
                    sendViolation(url, deviceID, studentName, reason, null);
                }
            });
        }, 500);
    } catch (e) {
        sendViolation(url, deviceID, studentName, reason, null);
    }
}

function sendViolation(url, deviceID, studentName, reason, screenshot) {
    fetch(`${SERVER_BASE}/alert`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            api_key: API_KEY,
            device: deviceID,
            student_name: studentName,
            url: url,
            reason: reason,
            time: new Date().toISOString(),
            screenshot: screenshot
        })
    }).catch(e => console.error("Violation sync failed:", e));
}

chrome.runtime.onMessage.addListener(async (msg, sender, sendResponse) => {
    if (msg.action === "violation") {
        const result = await chrome.storage.local.get(["deviceID"]);
        if (result.deviceID) {
            reportViolation(msg.url, result.deviceID, msg.reason);
        }
    }
});

// Blacklist Logic
async function getBlacklist() {
    try {
        const res = await fetch(`${SERVER_BASE}/get_blacklist`);
        return await res.json();
    } catch (e) {
        return ["youtube.com", "netflix.com"];
    }
}

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
    if (changeInfo.status !== "complete" || !tab.url || tab.url.startsWith("chrome://")) return;
    const result = await chrome.storage.local.get(["deviceID"]);
    if (!result.deviceID) return;

    if (suspiciousUrlKeywords.some(keyword => tab.url.toLowerCase().includes(keyword))) {
        reportViolation(tab.url, result.deviceID, "Suspicious keyword in URL");
        return;
    }

    const BLACKLIST = await getBlacklist();
    if (BLACKLIST.some(site => tab.url.toLowerCase().includes(site.toLowerCase()))) {
        reportViolation(tab.url, result.deviceID, "Blocked website accessed");
    }
});
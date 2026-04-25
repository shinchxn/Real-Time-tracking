// background.js
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === "CHECK_HASH") {
        // Hamming distance logic against stored index
        chrome.storage.local.get(['phash_index'], (data) => {
            const index = data.phash_index || {};
            // Mock match
            if (message.hash === index.target) {
                fetch("http://localhost:8000/api/sightings/batch", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({hash: message.hash, url: message.url})
                }).catch(e => console.log(e));
            }
        });
    }
});

chrome.alarms.create("sync_index", { periodInMinutes: 1440 });
chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === "sync_index") {
        fetch("http://localhost:8000/api/extension/sync")
            .then(res => res.json())
            .then(data => {
                chrome.storage.local.set({phash_index: data});
            }).catch(e => console.log(e));
    }
});

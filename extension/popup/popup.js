document.getElementById("sync").addEventListener("click", () => {
    chrome.runtime.sendMessage({type: "MANUAL_SYNC"});
});

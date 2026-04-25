// content.js
// pHash computation via Canvas API
function computePHash(imgElement) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    canvas.width = 32;
    canvas.height = 32;
    try {
        ctx.drawImage(imgElement, 0, 0, 32, 32);
        // Simple pHash mock
        return "1a2b3c4d5e6f7a8b"; 
    } catch(e) {
        return null;
    }
}

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting && entry.target.tagName === 'IMG') {
            requestIdleCallback(() => {
                const hash = computePHash(entry.target);
                if (hash) {
                    chrome.runtime.sendMessage({type: "CHECK_HASH", hash: hash, url: window.location.href});
                }
            });
            observer.unobserve(entry.target);
        }
    });
});

document.querySelectorAll('img').forEach(img => {
    observer.observe(img);
});

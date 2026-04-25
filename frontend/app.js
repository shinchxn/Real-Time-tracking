/* ═══════════════════════════════════════════════════════════
   Content DNA — Frontend Application Logic
   ═══════════════════════════════════════════════════════════ */

const API = window.location.hostname === 'localhost'
    ? 'http://localhost:8000'
    : (window.VITE_API_URL || 'http://localhost:8000');

// ── State ─────────────────────────────────────────────────────
let currentMode = 'upload'; // upload | detect | watermark
let selectedFile = null;

// ── DOM refs ──────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dropZone       = $('#dropZone');
const fileInput      = $('#fileInput');
const previewArea    = $('#previewArea');
const previewImage   = $('#previewImage');
const btnClear       = $('#btnClear');
const btnSubmit      = $('#btnSubmit');
const btnText        = btnSubmit.querySelector('.btn-text');
const btnLoader      = btnSubmit.querySelector('.btn-loader');
const resultCard     = $('#resultCard');
const systemStatus   = $('#systemStatus');
const statusText     = systemStatus.querySelector('.status-text');
const alertsList     = $('#alertsList');
const fingerprintPanel = $('#fingerprintPanel');
const fingerprintGrid  = $('#fingerprintGrid');

// Stats
const totalAssets    = $('#totalAssets');
const criticalCount  = $('#criticalCount');
const totalViolations = $('#totalViolations');
const modelName      = $('#modelName');

// ── Mode Toggle ──────────────────────────────────────────────
$$('.mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        $$('.mode-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentMode = btn.dataset.mode;
        updateUI();
    });
});

function updateUI() {
    const assetIdGroup = $('#assetIdGroup');
    if (currentMode === 'watermark') {
        assetIdGroup.style.display = 'flex';
        btnText.textContent = 'Embed Watermark';
    } else if (currentMode === 'detect') {
        assetIdGroup.style.display = 'none';
        btnText.textContent = 'Detect Violations';
    } else {
        assetIdGroup.style.display = 'none';
        btnText.textContent = 'Upload & Register';
    }
}

// ── File Handling ────────────────────────────────────────────
dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', () => {
    if (fileInput.files.length) handleFile(fileInput.files[0]);
});

function handleFile(file) {
    selectedFile = file;
    const reader = new FileReader();
    reader.onload = (e) => {
        previewImage.src = e.target.result;
        previewArea.style.display = 'block';
        dropZone.style.display = 'none';
        btnSubmit.disabled = false;
    };
    reader.readAsDataURL(file);
}

btnClear.addEventListener('click', () => {
    selectedFile = null;
    previewArea.style.display = 'none';
    dropZone.style.display = 'block';
    btnSubmit.disabled = true;
    resultCard.style.display = 'none';
    fingerprintPanel.style.display = 'none';
    fileInput.value = '';
});

// ── Submit ───────────────────────────────────────────────────
btnSubmit.addEventListener('click', async () => {
    if (!selectedFile) return;

    setLoading(true);
    resultCard.style.display = 'none';
    fingerprintPanel.style.display = 'none';

    const formData = new FormData();
    formData.append('file', selectedFile);

    const ownerId = $('#inputOwner').value || 'default-owner';

    try {
        let url, extras = {};

        if (currentMode === 'upload') {
            url = `${API}/upload?owner_id=${encodeURIComponent(ownerId)}`;
        } else if (currentMode === 'detect') {
            url = `${API}/detect?owner_id=${encodeURIComponent(ownerId)}`;
        } else if (currentMode === 'watermark') {
            const assetId = $('#inputAssetId').value || 'auto';
            url = `${API}/watermark/embed?asset_id=${encodeURIComponent(assetId)}&owner_id=${encodeURIComponent(ownerId)}`;
        }

        const resp = await fetch(url, { method: 'POST', body: formData });

        if (resp.ok) {
            if (currentMode === 'watermark') {
                // Watermark endpoint returns binary PNG
                const blob = await resp.blob();
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = `watermarked_${Date.now()}.png`;
                a.click();
                showResult({ status: 'success', message: 'Watermark embedded — file downloaded.' }, 'success');
            } else {
                // Upload & Detect both return JSON
                const data = await resp.json();
                if (currentMode === 'upload') {
                    // Auto-download watermarked image if present
                    if (data.watermarked_image) {
                        const a = document.createElement('a');
                        a.href = data.watermarked_image;
                        a.download = `dna_${data.filename || 'asset.png'}`;
                        a.click();
                    }
                    showUploadResult(data);
                } else {
                    showDetectResult(data);
                }
            }
        } else {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            showResult({ status: 'error', message: err.detail || 'Request failed' }, 'error');
        }

    } catch (err) {
        showResult({ status: 'error', message: err.message }, 'error');
    } finally {
        setLoading(false);
        refreshHealth();
        refreshAlerts();
    }
});

function setLoading(on) {
    btnSubmit.disabled = on;
    btnText.style.display = on ? 'none' : 'inline';
    btnLoader.style.display = on ? 'inline-block' : 'none';
}

// ── Results Display ──────────────────────────────────────────
function showUploadResult(data) {
    resultCard.className = 'result-card severity-success';
    resultCard.innerHTML = `
        <div class="result-header">
            <span class="result-severity">✓ REGISTERED</span>
        </div>
        <div class="result-meta">
            <strong>Asset ID:</strong> ${data.asset_id}<br>
            <strong>File:</strong> ${data.filename}<br>
            <strong>Fingerprints:</strong> CLIP(${data.fingerprints?.clip_dim || 768}d) · pHash · dHash · aHash · HOG(${data.fingerprints?.hog_dim || 128}d) · Color(${data.fingerprints?.color_dim || 9}d)
        </div>
    `;
    resultCard.style.display = 'block';
}

function showDetectResult(data) {
    const sev = data.severity || 'MISS';
    const sevClass = sev === 'MISS' ? 'severity-success' : `severity-${sev}`;

    let matchHTML = '';
    if (data.best_match) {
        const bm = data.best_match;
        matchHTML = `
            <div class="result-header">
                <span class="result-severity">${sev}</span>
                <span class="result-score">${(bm.fusion_score * 100).toFixed(1)}%</span>
            </div>
            <div class="result-meta">
                <strong>Matched Asset:</strong> ${bm.asset_id}<br>
                <strong>CLIP:</strong> ${(bm.clip_score * 100).toFixed(1)}% · 
                <strong>pHash:</strong> ${(bm.phash_score * 100).toFixed(1)}% · 
                <strong>Color:</strong> ${(bm.color_score * 100).toFixed(1)}% · 
                <strong>HOG:</strong> ${(bm.hog_score * 100).toFixed(1)}%
                ${bm.watermark_match !== null ? `<br><strong>Watermark:</strong> ${bm.watermark_match ? '✓ Verified' : '✗ No match'}` : ''}
            </div>
        `;

        // Show fingerprint breakdown
        showFingerprintBreakdown(bm);
    } else {
        matchHTML = `
            <div class="result-header">
                <span class="result-severity">NO MATCH</span>
            </div>
            <div class="result-meta">No matching assets found in the database.</div>
        `;
    }

    resultCard.className = `result-card ${sevClass}`;
    resultCard.innerHTML = matchHTML;
    resultCard.style.display = 'block';
}

function showResult(data, type) {
    resultCard.className = `result-card severity-${type === 'error' ? 'CRITICAL' : 'success'}`;
    resultCard.innerHTML = `
        <div class="result-header">
            <span class="result-severity">${type === 'error' ? '✗ ERROR' : '✓ SUCCESS'}</span>
        </div>
        <div class="result-meta">${data.message}</div>
    `;
    resultCard.style.display = 'block';
}

function showFingerprintBreakdown(match) {
    const layers = [
        { name: 'CLIP Semantic', score: match.clip_score, weight: '55%' },
        { name: 'pHash Perceptual', score: match.phash_score, weight: '25%' },
        { name: 'Color Moments', score: match.color_score, weight: '12%' },
        { name: 'HOG Edge', score: match.hog_score, weight: '8%' },
    ];

    fingerprintGrid.innerHTML = layers.map(l => `
        <div class="fp-card">
            <div class="fp-card-title">${l.name} (${l.weight})</div>
            <div class="fp-card-value">${(l.score * 100).toFixed(1)}%</div>
            <div class="fp-bar">
                <div class="fp-bar-fill" style="width: ${(l.score * 100).toFixed(0)}%"></div>
            </div>
        </div>
    `).join('');

    fingerprintPanel.style.display = 'block';
}

// ── Health Check ─────────────────────────────────────────────
async function refreshHealth() {
    try {
        const resp = await fetch(`${API}/health`);
        if (!resp.ok) throw new Error('unhealthy');
        const data = await resp.json();

        systemStatus.className = 'status-indicator online';
        statusText.textContent = 'System Online';

        totalAssets.textContent = data.faiss?.clip_vectors ?? 0;
        modelName.textContent = data.clip_model || 'ViT-L/14';

    } catch {
        systemStatus.className = 'status-indicator offline';
        statusText.textContent = 'Offline';
    }
}

// ── Alerts Feed ──────────────────────────────────────────────
let currentFilter = 'all';

$$('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        $$('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentFilter = btn.dataset.severity;
        refreshAlerts();
    });
});

async function refreshAlerts() {
    try {
        let url = `${API}/alerts?limit=30`;
        if (currentFilter !== 'all') url += `&severity=${currentFilter}`;

        const resp = await fetch(url);
        if (!resp.ok) return;
        const data = await resp.json();

        totalViolations.textContent = data.total || 0;
        criticalCount.textContent = data.violations?.filter(v => v.severity === 'CRITICAL').length || 0;

        if (!data.violations || data.violations.length === 0) {
            alertsList.innerHTML = `
                <div class="empty-state">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.3">
                        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                    </svg>
                    <p>No violations detected yet</p>
                </div>
            `;
            return;
        }

        alertsList.innerHTML = data.violations.map(v => `
            <div class="alert-item">
                <div class="alert-severity-dot ${v.severity}"></div>
                <div class="alert-body">
                    <div class="alert-title">${v.severity} — ${v.asset_id.substring(0, 8)}…</div>
                    <div class="alert-detail">${v.source || 'upload'} · ${new Date(v.detected_at).toLocaleString()}</div>
                </div>
                <div class="alert-score">${(v.fusion_score * 100).toFixed(1)}%</div>
            </div>
        `).join('');

    } catch {
        // Silent fail — alerts will refresh on next cycle
    }
}

// ── Init ─────────────────────────────────────────────────────
refreshHealth();
refreshAlerts();
setInterval(refreshHealth, 15000);
setInterval(refreshAlerts, 10000);
updateUI();


// PWA Service Worker & Install Prompt
let deferredPrompt;
window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    const installBtn = document.getElementById("pwa-install-btn");
    if (installBtn) {
        installBtn.classList.remove("hidden");
        installBtn.onclick = async () => {
            if (deferredPrompt) {
                deferredPrompt.prompt();
                const { outcome } = await deferredPrompt.userChoice;
                if (outcome === "accepted") {
                    installBtn.classList.add("hidden");
                }
                deferredPrompt = null;
            }
        };
    }
});

if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/sw.js").catch(console.error);
}
// SSB Document Screening Engine - Single-Page Client
let activeDocType = "AADHAAR";
let capturedFiles = {};

document.addEventListener("DOMContentLoaded", () => {
    selectDocType("AADHAAR");
    renderFaceCaptureCard();
});

function switchTab(tabId) {
    document.getElementById("tab-screen").classList.add("hidden");
    document.getElementById("tab-audit-view").classList.add("hidden");
    document.getElementById("tab-watchlist-view").classList.add("hidden");

    document.querySelectorAll("[id^='tab-btn-']").forEach(btn => {
        btn.classList.remove("bg-emerald-500", "text-slate-950");
        btn.classList.add("text-slate-400");
    });

    if (tabId === "screen") {
        document.getElementById("tab-screen").classList.remove("hidden");
        document.getElementById("tab-btn-screen").classList.add("bg-emerald-500", "text-slate-950");
        document.getElementById("tab-btn-screen").classList.remove("text-slate-400");
    } else if (tabId === "audit") {
        document.getElementById("tab-audit-view").classList.remove("hidden");
        document.getElementById("tab-btn-audit").classList.add("bg-emerald-500", "text-slate-950");
        document.getElementById("tab-btn-audit").classList.remove("text-slate-400");
        loadAuditLogs();
    } else if (tabId === "watchlist") {
        document.getElementById("tab-watchlist-view").classList.remove("hidden");
        document.getElementById("tab-btn-watchlist").classList.add("bg-emerald-500", "text-slate-950");
        document.getElementById("tab-btn-watchlist").classList.remove("text-slate-400");
    }
}

function selectDocType(type) {
    activeDocType = type;
    capturedFiles = {};
    document.querySelectorAll(".doc-btn").forEach(btn => {
        if (btn.dataset.type === type) {
            btn.classList.add("active");
        } else {
            btn.classList.remove("active");
        }
    });

    const container = document.getElementById("capture-container");
    container.innerHTML = "";

    if (type === "AADHAAR") {
        container.appendChild(createCaptureCard("front", "Aadhaar Front (Photo & UID)", "fa-id-card"));
        container.appendChild(createCaptureCard("back", "Aadhaar Back (Secure QR Code)", "fa-qrcode"));
    } else if (type === "PASSPORT") {
        container.appendChild(createCaptureCard("bio", "Passport Bio Page (MRZ Strip)", "fa-passport"));
    } else if (type === "VISA") {
        container.appendChild(createCaptureCard("visa", "Visa Stamp / Sticker", "fa-stamp"));
        container.appendChild(createCaptureCard("passport", "Traveler Passport Bio Page", "fa-passport"));
    } else if (type === "DL") {
        container.appendChild(createCaptureCard("dl", "Driving Licence Card Front", "fa-car"));
    } else if (type === "PERMIT") {
        container.appendChild(createCaptureCard("permit", "Border Permit Document", "fa-file-contract"));
    } else if (type === "GENERIC_ID") {
        container.appendChild(createCaptureCard("generic_id", "National ID / Voter Card", "fa-address-card"));
    }

    document.getElementById("results-panel").classList.add("hidden");
}

function createCaptureCard(key, label, iconClass) {
    const div = document.createElement("div");
    div.className = "bg-slate-900 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between";
    div.id = `card-${key}`;

    div.innerHTML = `
        <div class="flex items-center justify-between mb-3">
            <span class="text-xs font-bold text-slate-300 flex items-center gap-2">
                <i class="fa-solid ${iconClass} text-emerald-400"></i> ${label}
            </span>
            <span id="status-${key}" class="text-[11px] font-mono text-slate-500">PENDING</span>
        </div>
        <div id="preview-${key}" class="w-full h-44 bg-slate-950 rounded-xl border border-dashed border-slate-800 flex flex-col items-center justify-center text-slate-600 relative overflow-hidden mb-3">
            <i class="fa-solid fa-camera text-2xl mb-1"></i>
            <span class="text-xs">Tap Camera Button Below</span>
        </div>
        <label class="cursor-pointer w-full py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold flex items-center justify-center gap-2 border border-slate-700 active:scale-95 transition-all">
            <i class="fa-solid fa-camera text-emerald-400"></i> 
            <span>Snap with Phone Camera</span>
            <input type="file" accept="image/*" capture="environment" class="hidden" onchange="handleFileSelected(event, '${key}')">
        </label>
    `;
    return div;
}

function renderFaceCaptureCard() {
    const card = document.getElementById("face-capture-card");
    card.innerHTML = `
        <div class="flex items-center gap-3">
            <div id="preview-live_face" class="w-16 h-16 bg-slate-950 rounded-xl border border-dashed border-slate-800 flex items-center justify-center text-slate-600 overflow-hidden flex-shrink-0">
                <i class="fa-solid fa-user"></i>
            </div>
            <label class="flex-1 cursor-pointer py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold flex items-center justify-center gap-2 border border-slate-700">
                <i class="fa-solid fa-camera text-teal-400"></i>
                <span>Snap Live Selfie</span>
                <input type="file" accept="image/*" capture="user" class="hidden" onchange="handleFileSelected(event, 'live_face')">
            </label>
        </div>
    `;
}

function handleFileSelected(event, key) {
    const file = event.target.files[0];
    if (!file) return;

    capturedFiles[key] = file;

    // Show preview
    const reader = new FileReader();
    reader.onload = (e) => {
        const previewContainer = document.getElementById(`preview-${key}`);
        previewContainer.innerHTML = `<img src="${e.target.result}" class="w-full h-full object-cover rounded-xl">`;
        
        const statusTag = document.getElementById(`status-${key}`);
        if (statusTag) {
            statusTag.textContent = "READY";
            statusTag.className = "text-[11px] font-mono text-emerald-400 font-bold";
        }
    };
    reader.readAsDataURL(file);
}

async function submitScreening() {
    const btn = document.getElementById("btn-screen-submit");
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin text-lg"></i> <span>Analyzing Micro-Features & Security Tiers...</span>`;

    const formData = new FormData();
    let endpoint = "/screen/aadhaar";

    if (activeDocType === "AADHAAR") {
        if (!capturedFiles["front"] || !capturedFiles["back"]) {
            alert("Please capture both Aadhaar Front and Back.");
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-bolt text-lg"></i> <span>Execute Deep Multi-Layer Screening</span>`;
            return;
        }
        formData.append("front", capturedFiles["front"]);
        formData.append("back", capturedFiles["back"]);
        endpoint = "/screen/aadhaar";
    } else if (activeDocType === "PASSPORT") {
        if (!capturedFiles["bio"]) {
            alert("Please capture the Passport biographical page.");
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-bolt text-lg"></i> <span>Execute Deep Multi-Layer Screening</span>`;
            return;
        }
        formData.append("document", capturedFiles["bio"]);
        endpoint = "/screen/passport";
    } else if (activeDocType === "VISA") {
        if (!capturedFiles["visa"]) {
            alert("Please capture the Visa sticker.");
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-bolt text-lg"></i> <span>Execute Deep Multi-Layer Screening</span>`;
            return;
        }
        formData.append("document", capturedFiles["visa"]);
        endpoint = "/screen/visa";
    } else if (activeDocType === "DL") {
        if (!capturedFiles["dl"]) {
            alert("Please capture the Driving Licence.");
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-bolt text-lg"></i> <span>Execute Deep Multi-Layer Screening</span>`;
            return;
        }
        formData.append("document", capturedFiles["dl"]);
        endpoint = "/screen/dl";
    } else if (activeDocType === "PERMIT") {
        if (!capturedFiles["permit"]) {
            alert("Please capture the Permit.");
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-bolt text-lg"></i> <span>Execute Deep Multi-Layer Screening</span>`;
            return;
        }
        formData.append("document", capturedFiles["permit"]);
        endpoint = "/screen/permit";
    } else if (activeDocType === "GENERIC_ID") {
        if (!capturedFiles["generic_id"]) {
            alert("Please capture the ID card.");
            btn.disabled = false;
            btn.innerHTML = `<i class="fa-solid fa-bolt text-lg"></i> <span>Execute Deep Multi-Layer Screening</span>`;
            return;
        }
        formData.append("document", capturedFiles["generic_id"]);
        endpoint = "/screen/permit";
    }

    if (capturedFiles["live_face"]) {
        formData.append("live_face", capturedFiles["live_face"]);
    }

    const t0 = performance.now();
    try {
        const response = await fetch(endpoint, {
            method: "POST",
            body: formData
        });
        const result = await response.json();
        const tElapsed = ((performance.now() - t0) / 1000).toFixed(2);
        displayScreeningResults(result, tElapsed);
    } catch (err) {
        alert("Screening request failed: " + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fa-solid fa-bolt text-lg"></i> <span>Execute Deep Multi-Layer Screening</span>`;
    }
}

function displayScreeningResults(res, elapsedSec) {
    const panel = document.getElementById("results-panel");
    panel.classList.remove("hidden");
    panel.scrollIntoView({ behavior: "smooth" });

    const risk = res.risk_assessment || {};
    const score = Math.round(risk.overall_score || 0);
    const status = (risk.status || "CLEAR").toUpperCase();

    // Risk Banner Colors
    const banner = document.getElementById("risk-banner");
    const badge = document.getElementById("risk-badge");
    const scoreText = document.getElementById("risk-score");
    const latencyTag = document.getElementById("latency-tag");

    scoreText.textContent = score;
    latencyTag.textContent = `⚡ ${elapsedSec} s`;

    if (status === "FLAGGED") {
        banner.className = "rounded-2xl p-5 border border-rose-500/40 bg-rose-500/10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4";
        badge.className = "px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider font-mono bg-rose-500 text-slate-950";
        badge.textContent = "FLAGGED (THREAT)";
    } else if (status === "REVIEW") {
        banner.className = "rounded-2xl p-5 border border-amber-500/40 bg-amber-500/10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4";
        badge.className = "px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider font-mono bg-amber-500 text-slate-950";
        badge.textContent = "MANUAL REVIEW";
    } else {
        banner.className = "rounded-2xl p-5 border border-emerald-500/40 bg-emerald-500/10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4";
        badge.className = "px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider font-mono bg-emerald-500 text-slate-950";
        badge.textContent = "CLEAR (PASSED)";
    }

    // Officer Summary
    const notes = res.processing_notes || [];
    document.getElementById("officer-summary-text").textContent = notes.length > 0 ? notes.join("; ") : "Document passed all cryptographic, checksum, and ELA forensic integrity checks.";

    // Breakdown Grid
    const checksGrid = document.getElementById("checks-grid");
    checksGrid.innerHTML = "";
    const breakdown = risk.component_breakdown || {};
    for (const [k, v] of Object.entries(breakdown)) {
        const tile = document.createElement("div");
        const failed = v > 0;
        tile.className = `p-3 rounded-xl border ${failed ? 'border-rose-500/30 bg-rose-500/10' : 'border-slate-800 bg-slate-950'} flex items-center justify-between`;
        tile.innerHTML = `
            <div>
                <span class="text-xs font-semibold text-slate-300 block">${k.replace(/_/g, ' ').toUpperCase()}</span>
                <span class="text-[10px] text-slate-500 font-mono">Weight: ${v} pts</span>
            </div>
            <i class="fa-solid ${failed ? 'fa-circle-xmark text-rose-400' : 'fa-circle-check text-emerald-400'} text-lg"></i>
        `;
        checksGrid.appendChild(tile);
    }

    // Demographics
    const demoList = document.getElementById("demographics-list");
    demoList.innerHTML = "";
    const ocr = res.ocr_extraction || {};
    const fields = ocr.fields || ocr.qr_fields || ocr.mrz_fields || {};
    for (const [k, v] of Object.entries(fields)) {
        if (v && typeof v === "string") {
            const item = document.createElement("div");
            item.className = "flex justify-between py-1 border-b border-slate-800/60";
            item.innerHTML = `<span class="text-slate-400 capitalize">${k.replace(/_/g, ' ')}:</span><span class="font-semibold text-white">${v}</span>`;
            demoList.appendChild(item);
        }
    }
}

async function loadAuditLogs() {
    const list = document.getElementById("audit-log-list");
    list.innerHTML = `<span class="text-xs text-slate-500">Loading immutable audit logs...</span>`;
    try {
        const response = await fetch("/audit/recent?limit=25");
        const logs = await response.json();
        list.innerHTML = "";
        if (logs.length === 0) {
            list.innerHTML = `<span class="text-xs text-slate-500">No screenings logged yet.</span>`;
            return;
        }
        logs.forEach(log => {
            const item = document.createElement("div");
            const isFlagged = log.risk_level === "FLAGGED";
            item.className = `p-3 rounded-xl border ${isFlagged ? 'border-rose-500/30 bg-rose-500/10' : 'border-slate-800 bg-slate-900'} flex items-center justify-between text-xs`;
            item.innerHTML = `
                <div>
                    <span class="font-bold text-white">${log.doc_type} (${log.doc_number || 'N/A'})</span>
                    <span class="text-slate-400 block">${log.name || 'Anonymous'} · ${log.timestamp ? log.timestamp.slice(0, 19) : ''}</span>
                </div>
                <span class="px-2 py-0.5 rounded-full font-mono font-bold ${isFlagged ? 'bg-rose-500 text-slate-950' : 'bg-emerald-500 text-slate-950'}">${log.risk_level}</span>
            `;
            list.appendChild(item);
        });
    } catch (e) {
        list.innerHTML = `<span class="text-xs text-rose-400">Failed to load logs: ${e.message}</span>`;
    }
}

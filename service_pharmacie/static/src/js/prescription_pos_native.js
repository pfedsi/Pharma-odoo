/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

/* ═══════════════════════════════════════════════════════════════════════
 *  ÉTAT GLOBAL
 * ═══════════════════════════════════════════════════════════════════════ */

let selectedPoste = "1";
let liveTimer = null;
let currentScannedPrescription = null;

/* ═══════════════════════════════════════════════════════════════════════
 *  HELPERS DOM
 * ═══════════════════════════════════════════════════════════════════════ */

const byId  = (id) => document.getElementById(id);
const getMenu    = () => byId("rattachement-menu");
const getSublist = () => byId("rattachement-sublist");

/* ═══════════════════════════════════════════════════════════════════════
 *  MENU RATTACHEMENT
 * ═══════════════════════════════════════════════════════════════════════ */

function openMenu() {
    const m = getMenu();
    if (!m) return;
    m.classList.add("is-open");
    renderPosteGrid();
    startLive();
}

function closeMenu() {
    const m = getMenu();
    const sub = getSublist();
    if (m)   m.classList.remove("is-open");
    if (sub) sub.innerHTML = "";
    stopLive();
}

function toggleMenu() {
    const m = getMenu();
    if (!m) return;
    m.classList.contains("is-open") ? closeMenu() : openMenu();
}

/* ═══════════════════════════════════════════════════════════════════════
 *  GRILLE POSTES
 * ═══════════════════════════════════════════════════════════════════════ */

function renderPosteGrid() {
    const grid = byId("ratt-poste-grid");
    if (!grid) return;

    grid.innerHTML = Array.from({ length: 10 }, (_, i) => {
        const n = String(i + 1);
        return `<button type="button"
                        class="ratt-poste-btn${selectedPoste === n ? " active" : ""}"
                        data-poste="${n}">${n}</button>`;
    }).join("");

    grid.querySelectorAll(".ratt-poste-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            selectedPoste = btn.dataset.poste;
            renderPosteGrid();
        });
    });
}

/* ═══════════════════════════════════════════════════════════════════════
 *  BADGES MODE
 * ═══════════════════════════════════════════════════════════════════════ */

const MODE_META = {
    manuel:       { label: "Manuel",      cls: "ratt-badge--manuel" },
    auto_attente: { label: "Automatique", cls: "ratt-badge--auto" },
    prioritaire:  { label: "Prioritaire", cls: "ratt-badge--prioritaire" },
};

function updateStatus(mode, queueName, posteNumber = false) {
    const modeEl  = byId("rattachement-mode-label");
    const queueEl = byId("rattachement-queue-label");
    const posteEl = byId("rattachement-poste-label");

    if (modeEl) {
        const meta = MODE_META[mode] || { label: "Aucun", cls: "ratt-badge--aucun" };
        modeEl.textContent = meta.label;
        modeEl.className   = `ratt-badge ${meta.cls}`;
    }
    if (queueEl) queueEl.textContent = queueName   || "—";
    if (posteEl) posteEl.textContent = posteNumber  || "1";

    document.querySelectorAll(".ratt-mode-btn").forEach((btn) => {
        btn.classList.toggle("is-active", btn.dataset.mode === mode);
    });
}

/* ═══════════════════════════════════════════════════════════════════════
 *  TICKET ACTIF
 * ═══════════════════════════════════════════════════════════════════════ */

function updateTicket(ticketName) {
    const el   = byId("current-ticket-label");
    const cell = byId("ratt-ticket-cell");
    if (!el) return;

    const prev = el.textContent;
    el.textContent = ticketName || "—";

    if (ticketName && ticketName !== prev && cell) {
        cell.classList.remove("is-changed");
        void cell.offsetWidth;
        cell.classList.add("is-changed");
        setTimeout(() => cell.classList.remove("is-changed"), 900);
    }
}

/* ═══════════════════════════════════════════════════════════════════════
 *  LIVE QUEUES
 * ═══════════════════════════════════════════════════════════════════════ */

function bindQueueCardClicks() {
    document.querySelectorAll(".ratt-queue-card").forEach((card) => {
        card.onclick = () => {
            const queueId = parseInt(card.dataset.queueId || "0", 10);
            if (queueId) setRattachement("manuel", queueId, false, selectedPoste);
        };
    });
}

async function refreshLive() {
    const grid = byId("ratt-queues-grid");
    if (!grid) return;

    try {
        const response = await fetch("/pharmacy/display/data");
        const res = await response.json();

        if (!res?.success) {
            grid.innerHTML = `<p style="font-size:11px;color:#f43f5e;padding:4px 0">Erreur API</p>`;
            return;
        }

        const queues = res.queues || [];

        if (!queues.length) {
            grid.innerHTML = `<p style="font-size:11px;color:rgba(255,255,255,.3);padding:4px 0">Aucune file active</p>`;
            return;
        }

        const oldCounts = {};
        grid.querySelectorAll(".ratt-queue-card").forEach((c) => {
            oldCounts[c.dataset.queueId] = parseInt(c.dataset.count || "0", 10);
        });

        grid.innerHTML = queues.map((q) => {
            const count   = (q.en_attente || []).length;
            const isZero  = count === 0;
            const changed = oldCounts[String(q.queue_id)] !== undefined
                         && count !== oldCounts[String(q.queue_id)];
            const bump    = !isZero && changed ? " bump" : "";
            const pillCls = isZero ? "ratt-pill--zero" : "ratt-pill--waiting";

            return `
                <div class="ratt-queue-card"
                     data-queue-id="${q.queue_id}"
                     data-count="${count}">
                    <span class="ratt-queue-card__name">${q.queue_name || "—"}</span>
                    <span class="ratt-queue-card__meta">
                        <span class="ratt-pill ${pillCls}${bump}">${count}</span>
                        <span class="ratt-dot-live"></span>
                    </span>
                </div>`;
        }).join("");

        bindQueueCardClicks();
    } catch (err) {
        console.error("[ratt] refreshLive:", err);
        grid.innerHTML = `<p style="font-size:11px;color:#f43f5e;padding:4px 0">Erreur de connexion</p>`;
    }
}

function startLive() {
    refreshLive();
    liveTimer = setInterval(refreshLive, 2000);
}

function stopLive() {
    if (liveTimer) { clearInterval(liveTimer); liveTimer = null; }
}

/* ═══════════════════════════════════════════════════════════════════════
 *  SOUS-LISTES (files / services)
 * ═══════════════════════════════════════════════════════════════════════ */

function renderQueueList(queues) {
    const sub = getSublist();
    if (!sub) return;

    sub.innerHTML = `<p class="ratt-sublist-title">Choisir une file</p>
        ${queues.map((q) =>
            `<button type="button" class="ratt-sublist-item" data-id="${q.id}">${q.name}</button>`
        ).join("")}`;

    sub.querySelectorAll(".ratt-sublist-item").forEach((btn) => {
        btn.addEventListener("click", () =>
            setRattachement("manuel", parseInt(btn.dataset.id, 10), false, selectedPoste)
        );
    });
}

function renderServiceList(services) {
    const sub = getSublist();
    if (!sub) return;

    sub.innerHTML = `<p class="ratt-sublist-title">Choisir un service</p>
        ${services.map((s) =>
            `<button type="button" class="ratt-sublist-item" data-id="${s.id}">${s.name}</button>`
        ).join("")}`;

    sub.querySelectorAll(".ratt-sublist-item").forEach((btn) => {
        btn.addEventListener("click", () =>
            setRattachement("prioritaire", false, parseInt(btn.dataset.id, 10), selectedPoste)
        );
    });
}

/* ═══════════════════════════════════════════════════════════════════════
 *  API RATTACHEMENT
 * ═══════════════════════════════════════════════════════════════════════ */

async function loadCurrentRattachement() {
    try {
        const r = await rpc("/pos/rattachement/current", {});
        selectedPoste = r.poste_number || "1";
        updateStatus(r.mode, r.queue_name, r.poste_number);
        updateTicket(r.current_ticket_name);
    } catch (e) {
        console.error("[ratt] load:", e);
    }
}

async function setRattachement(mode, fileId = false, serviceId = false, posteNumber = "1") {
    try {
        const r = await rpc("/pos/rattachement/set", {
            mode_rattachement:      mode,
            file_id:                fileId,
            service_prioritaire_id: serviceId,
            poste_number:           posteNumber,
        });
        updateStatus(r.mode, r.queue_name, r.poste_number);
        updateTicket(r.current_ticket_name);
        closeMenu();
    } catch (e) {
        console.error("[ratt] set:", e);
    }
}

/* ═══════════════════════════════════════════════════════════════════════
 *  CRÉER ET SÉLECTIONNER UNE NOUVELLE COMMANDE POS
 *  Dispatche "pos-create-and-select-order" → capté par pos_prescription.js
 *  Retourne une Promise qui résout quand "pos-order-ready" arrive.
 * ═══════════════════════════════════════════════════════════════════════ */

function createAndSelectPosOrder(ticketName = "") {
    return new Promise((resolve) => {
        // Timeout de sécurité : 3 secondes
        const timeout = setTimeout(() => {
            window.removeEventListener("pos-order-ready", handler);
            console.warn("[RX] createAndSelectPosOrder timeout — on continue quand même");
            resolve(null);
        }, 3000);

        function handler(ev) {
            clearTimeout(timeout);
            window.removeEventListener("pos-order-ready", handler);
            console.log("[RX] pos-order-ready reçu:", ev.detail);
            resolve(ev.detail);
        }

        window.addEventListener("pos-order-ready", handler);

        window.dispatchEvent(new CustomEvent("pos-create-and-select-order", {
            detail: { ticketName },
        }));
    });
}

/* ═══════════════════════════════════════════════════════════════════════
 *  CALL NEXT TICKET
 * ═══════════════════════════════════════════════════════════════════════ */

async function callNextTicket() {
    try {
        const r = await rpc("/pos/rattachement/call_next", {});

        // ── 1. Créer une commande fraîche et la sélectionner ─────────────
        await createAndSelectPosOrder(r?.ticket?.name || "");

        // ── 2. Mettre à jour l'affichage ticket ──────────────────────────
        updateTicket(r?.ticket?.name || null);
        currentScannedPrescription = null;

        // ── 3. Charger l'ordonnance si présente ──────────────────────────
        if (r?.prescription) {
            console.log("[RX] Prescription auto chargée =", r.prescription);
            switchToCaisseTab();

            const meds = r.prescription.medications || [];

            // Dispatch vers pos_prescription.js → order.addProduct() natif
            window.dispatchEvent(new CustomEvent("prescription-scanned", {
                detail: {
                    prescriptionId: r.prescription.prescription_id || null,
                    data: r.prescription,
                },
            }));

            // Affichage panneau UI
            const items = meds.map((m) => ({
                name:          m.name,
                description:   `${m.dosage || ""} ${m.form || ""}`.trim(),
                productName:   m.product_name || "Non trouvé dans le catalogue",
                message:       m.evaluation_message || "",
                productId:     m.product_id,
                productTmplId: m.product_tmpl_id,
                lineId:        m.line_id,
                quantity:      m.quantity || 1,
                isFound:       !!m.product_id,
            }));
            renderImportedLinesInCaisse("Ordonnance scannée", items);
            showPrescriptionToast("Ordonnance chargée automatiquement", "success");
        }

        // ── 4. Charger le panier mobile si présent ───────────────────────
        if (r?.mobile_order_lines?.length) {
            console.log("[RX] Panier mobile =", r.mobile_order_lines);
            switchToCaisseTab();

            // Dispatch vers pos_prescription.js → order.addProduct() natif
            window.dispatchEvent(new CustomEvent("prescription-scanned", {
                detail: {
                    prescriptionId: null,
                    data: {
                        medications: r.mobile_order_lines.map((l) => ({
                            product_id: l.product_id,
                            quantity:   l.quantity || 1,
                            name:       l.name || "",
                        })),
                    },
                },
            }));

            // Affichage panneau UI
            const items = r.mobile_order_lines.map((l) => ({
                name:          l.name,
                description:   `Source : ${l.source_type || "-"} | Qté : ${l.quantity || 1}`,
                productName:   `Prix : ${Number(l.price_unit || 0).toFixed(2)}`,
                message:       "",
                productId:     l.product_id,
                productTmplId: l.product_tmpl_id || null,
                lineId:        l.id || 0,
                quantity:      l.quantity || 1,
                isFound:       !!l.product_id,
            }));
            renderImportedLinesInCaisse("Panier mobile", items);
            showPrescriptionToast("Panier mobile chargé automatiquement", "success");
        }

    } catch (e) {
        console.error("[ratt] call_next:", e);
    }
}

/* ═══════════════════════════════════════════════════════════════════════
 *  FINISH CURRENT TICKET
 * ═══════════════════════════════════════════════════════════════════════ */

async function finishCurrentTicket() {
    try {
        await rpc("/pos/rattachement/finish_current", {});
        // Créer une commande fraîche après fin de ticket
        await createAndSelectPosOrder();
        updateTicket(null);
        currentScannedPrescription = null;
    } catch (e) {
        console.error("[ratt] finish:", e);
    }
}

/* ═══════════════════════════════════════════════════════════════════════
 *  PRESCRIPTION — Modal de sélection source (Caméra / Fichier)
 * ═══════════════════════════════════════════════════════════════════════ */

function openPrescriptionScanModal() {
    const existing = document.getElementById("rx-source-modal");
    if (existing) existing.remove();

    const overlay = document.createElement("div");
    overlay.id = "rx-source-modal";
    Object.assign(overlay.style, {
        position:       "fixed",
        inset:          "0",
        zIndex:         "999999",
        background:     "rgba(0, 0, 0, 0.60)",
        display:        "flex",
        alignItems:     "center",
        justifyContent: "center",
        backdropFilter: "blur(4px)",
        animation:      "rxOverlayIn 0.18s ease both",
    });

    if (!document.getElementById("rx-modal-styles")) {
        const style = document.createElement("style");
        style.id = "rx-modal-styles";
        style.textContent = `
            @keyframes rxOverlayIn {
                from { opacity: 0; }
                to   { opacity: 1; }
            }
            @keyframes rxCardIn {
                from { opacity: 0; transform: translateY(12px) scale(0.97); }
                to   { opacity: 1; transform: translateY(0) scale(1); }
            }
            .rx-src-btn {
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 10px;
                padding: 20px 16px;
                border-radius: 12px;
                border: 1px solid rgba(255,255,255,0.10);
                background: rgba(255,255,255,0.05);
                color: rgba(255,255,255,0.85);
                cursor: pointer;
                font-family: 'Google Sans','Roboto',system-ui,sans-serif;
                font-size: 13px;
                font-weight: 500;
                flex: 1;
                transition: all 0.15s ease;
                min-width: 120px;
            }
            .rx-src-btn:hover {
                background: rgba(255,255,255,0.11);
                border-color: rgba(255,255,255,0.22);
                transform: translateY(-2px);
            }
            .rx-src-btn:active { transform: scale(0.97); }
            .rx-src-btn .rx-icon {
                width: 48px; height: 48px;
                border-radius: 14px;
                display: flex; align-items: center; justify-content: center;
            }
            .rx-src-btn--camera .rx-icon {
                background: rgba(26,115,232,0.20);
                border: 1px solid rgba(26,115,232,0.35);
                color: #8ab4f8;
            }
            .rx-src-btn--camera:hover .rx-icon {
                background: #1a73e8; color: #fff;
                border-color: #1a73e8;
                box-shadow: 0 4px 16px rgba(26,115,232,0.45);
            }
            .rx-src-btn--file .rx-icon {
                background: rgba(52,168,83,0.18);
                border: 1px solid rgba(52,168,83,0.30);
                color: #81c995;
            }
            .rx-src-btn--file:hover .rx-icon {
                background: #34a853; color: #fff;
                border-color: #34a853;
                box-shadow: 0 4px 16px rgba(52,168,83,0.40);
            }
            .rx-close-btn {
                position: absolute; top: 14px; right: 14px;
                width: 26px; height: 26px;
                border-radius: 8px;
                border: 0.5px solid rgba(255,255,255,0.10);
                background: rgba(255,255,255,0.06);
                color: rgba(255,255,255,0.55);
                display: flex; align-items: center; justify-content: center;
                cursor: pointer;
                transition: all 0.14s ease;
                font-size: 14px; line-height: 1;
            }
            .rx-close-btn:hover {
                background: rgba(255,255,255,0.12);
                color: rgba(255,255,255,0.90);
                border-color: rgba(255,255,255,0.18);
            }
        `;
        document.head.appendChild(style);
    }

    const card = document.createElement("div");
    Object.assign(card.style, {
        position:    "relative",
        width:       "320px",
        background:  "#1e2742",
        borderRadius: "18px",
        border:      "0.5px solid rgba(255,255,255,0.12)",
        padding:     "22px 20px 20px",
        boxShadow:   "0 8px 32px rgba(0,0,0,0.50), 0 2px 8px rgba(0,0,0,0.30)",
        animation:   "rxCardIn 0.22s cubic-bezier(0.34,1.3,0.64,1) both",
        fontFamily:  "'Google Sans','Roboto',system-ui,sans-serif",
    });

    card.innerHTML = `
        <button class="rx-close-btn" id="rx-modal-close" title="Fermer">
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
            </svg>
        </button>
        <div style="margin-bottom:18px;">
            <p style="font-size:14px;font-weight:600;color:rgba(255,255,255,0.92);margin:0 0 4px;letter-spacing:-0.2px;">
                Scanner une ordonnance
            </p>
            <p style="font-size:11.5px;color:rgba(255,255,255,0.42);margin:0;line-height:1.4;">
                Choisissez la source de l'image
            </p>
        </div>
        <div style="display:flex;gap:10px;">
            <button class="rx-src-btn rx-src-btn--camera" id="rx-btn-camera">
                <span class="rx-icon">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                        <path d="M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2z"
                              stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
                        <circle cx="12" cy="13" r="4" stroke="currentColor" stroke-width="1.6"/>
                    </svg>
                </span>
                <span>Caméra</span>
                <span style="font-size:10px;color:rgba(255,255,255,0.35);font-weight:400;">Prendre une photo</span>
            </button>
            <button class="rx-src-btn rx-src-btn--file" id="rx-btn-file">
                <span class="rx-icon">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                        <rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" stroke-width="1.6"/>
                        <circle cx="8.5" cy="8.5" r="1.5" stroke="currentColor" stroke-width="1.4"/>
                        <path d="M21 15l-5-5L5 21" stroke="currentColor" stroke-width="1.6"
                              stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </span>
                <span>Galerie / PC</span>
                <span style="font-size:10px;color:rgba(255,255,255,0.35);font-weight:400;">Image existante</span>
            </button>
        </div>
    `;

    overlay.appendChild(card);
    document.body.appendChild(overlay);

    overlay.addEventListener("click", (e) => { if (e.target === overlay) closeRxModal(); });
    document.getElementById("rx-modal-close").addEventListener("click", closeRxModal);
    document.getElementById("rx-btn-camera").addEventListener("click", () => { closeRxModal(); openCameraCapture(); });
    document.getElementById("rx-btn-file").addEventListener("click",   () => { closeRxModal(); openFilePicker(); });
}

function closeRxModal() {
    document.getElementById("rx-source-modal")?.remove();
}

/* ═══════════════════════════════════════════════════════════════════════
 *  CAMÉRA — getUserMedia
 * ═══════════════════════════════════════════════════════════════════════ */

function openCameraCapture() {
    document.getElementById("rx-camera-modal")?.remove();

    if (!document.getElementById("rx-camera-styles")) {
        const s = document.createElement("style");
        s.id = "rx-camera-styles";
        s.textContent = `
            #rx-camera-modal {
                position: fixed; inset: 0; z-index: 1000000;
                background: rgba(0,0,0,0.92);
                display: flex; flex-direction: column;
                align-items: center; justify-content: center;
                gap: 16px; padding: 20px;
                font-family: 'Google Sans','Roboto',system-ui,sans-serif;
            }
            #rx-camera-modal video {
                width: 100%; max-width: 640px; max-height: 60vh;
                border-radius: 14px; border: 2px solid rgba(255,255,255,0.15);
                display: block; background: #000; object-fit: cover;
            }
            #rx-camera-modal .rx-cam-label {
                font-size: 13px; color: rgba(255,255,255,0.55); margin: 0; text-align: center;
            }
            #rx-camera-modal .rx-cam-label.error { color: #f28b82; }
            #rx-camera-modal .rx-cam-row {
                display: flex; gap: 12px; flex-wrap: wrap; justify-content: center;
            }
            #rx-camera-modal .rx-cam-btn {
                padding: 11px 26px; border-radius: 10px; font-size: 14px;
                font-weight: 700; cursor: pointer; font-family: inherit;
                border: none; transition: opacity 0.15s, transform 0.1s;
            }
            #rx-camera-modal .rx-cam-btn:hover  { opacity: 0.85; }
            #rx-camera-modal .rx-cam-btn:active { transform: scale(0.96); }
            #rx-camera-modal .rx-cam-btn--capture { background: #1a73e8; color: #fff; }
            #rx-camera-modal .rx-cam-btn--capture:disabled {
                background: #444; color: rgba(255,255,255,0.3); cursor: not-allowed; opacity: 1;
            }
            #rx-camera-modal .rx-cam-btn--switch {
                background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.75);
                border: 1px solid rgba(255,255,255,0.15);
            }
            #rx-camera-modal .rx-cam-btn--cancel {
                background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.65);
                border: 1px solid rgba(255,255,255,0.12);
            }
        `;
        document.head.appendChild(s);
    }

    const overlay = document.createElement("div");
    overlay.id = "rx-camera-modal";

    const label = document.createElement("p");
    label.className = "rx-cam-label";
    label.textContent = "Démarrage de la caméra…";

    const video = document.createElement("video");
    video.autoplay = true; video.playsInline = true; video.muted = true;
    video.style.display = "none";

    const btnRow = document.createElement("div");
    btnRow.className = "rx-cam-row";

    const captureBtn = document.createElement("button");
    captureBtn.className = "rx-cam-btn rx-cam-btn--capture";
    captureBtn.textContent = "📸 Capturer";
    captureBtn.disabled = true;

    const switchBtn = document.createElement("button");
    switchBtn.className = "rx-cam-btn rx-cam-btn--switch";
    switchBtn.textContent = "🔄 Changer caméra";
    switchBtn.style.display = "none";

    const cancelBtn = document.createElement("button");
    cancelBtn.className = "rx-cam-btn rx-cam-btn--cancel";
    cancelBtn.textContent = "✕ Annuler";

    btnRow.append(captureBtn, switchBtn, cancelBtn);
    overlay.append(label, video, btnRow);
    document.body.appendChild(overlay);

    let stream = null;
    let facingMode = "environment";
    let availableCameras = [];

    function stopStream() {
        if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
    }
    function closeCamera() { stopStream(); overlay.remove(); }

    async function startStream(facing) {
        stopStream();
        captureBtn.disabled = true;
        video.style.display = "none";
        label.textContent = "Démarrage de la caméra…";
        label.className = "rx-cam-label";

        try {
            stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: { ideal: facing }, width: { ideal: 1920 }, height: { ideal: 1080 } },
                audio: false,
            });
        } catch {
            try {
                stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            } catch (e2) {
                label.textContent = "❌ Caméra inaccessible : " + (e2.message || e2.name);
                label.className = "rx-cam-label error";
                return;
            }
        }

        video.srcObject = stream;
        await video.play().catch(() => {});
        video.style.display = "block";
        label.style.display = "none";
        captureBtn.disabled = false;
        if (availableCameras.length > 1) switchBtn.style.display = "inline-flex";
    }

    navigator.mediaDevices.enumerateDevices()
        .then((devices) => { availableCameras = devices.filter((d) => d.kind === "videoinput"); })
        .catch(() => {})
        .finally(() => startStream(facingMode));

    cancelBtn.addEventListener("click", closeCamera);

    switchBtn.addEventListener("click", () => {
        facingMode = facingMode === "environment" ? "user" : "environment";
        switchBtn.textContent = facingMode === "environment" ? "🔄 Caméra arrière" : "🔄 Caméra avant";
        startStream(facingMode);
    });

    captureBtn.addEventListener("click", () => {
        if (!stream || captureBtn.disabled) return;
        const canvas = document.createElement("canvas");
        canvas.width  = video.videoWidth  || 1280;
        canvas.height = video.videoHeight || 720;
        canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
        closeCamera();
        canvas.toBlob(async (blob) => {
            if (!blob) { showPrescriptionToast("Erreur lors de la capture.", "error"); return; }
            await processRxFile(new File([blob], "capture_ordonnance.jpg", { type: "image/jpeg" }));
        }, "image/jpeg", 0.92);
    });

    overlay.addEventListener("click", (e) => { if (e.target === overlay) closeCamera(); });
}

/* ═══════════════════════════════════════════════════════════════════════
 *  GALERIE / PC
 * ═══════════════════════════════════════════════════════════════════════ */

function openFilePicker() {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/png,image/jpeg,image/webp";
    input.style.display = "none";

    input.addEventListener("change", async (ev) => {
        const file = ev.target.files?.[0];
        if (!file) return;
        await processRxFile(file);
        input.remove();
    });

    document.body.appendChild(input);
    input.click();
}

/* ═══════════════════════════════════════════════════════════════════════
 *  TRAITEMENT FICHIER ORDONNANCE — envoi RPC + évaluation stock
 *
 *  Flux :
 *    1. /pos/prescription/scan          → OCR → prescription créée
 *    2. /api/prescription/:id/check_availability → matching produits
 *    3. CustomEvent "prescription-scanned" avec les product_id renseignés
 * ═══════════════════════════════════════════════════════════════════════ */

async function processRxFile(file) {
    try {
        showPrescriptionToast("Analyse de l'ordonnance en cours…", "info");

        const fileBase64 = await fileToBase64(file);

        // ── 1. Scan OCR ──────────────────────────────────────────────────
        const result = await rpc("/pos/prescription/scan", {
            filename:    file.name || "ordonnance.jpg",
            file_base64: fileBase64,
            mimetype:    file.type || "image/jpeg",
        });

        if (!result?.success) {
            showPrescriptionToast(result?.message || "Erreur lors du scan.", "error");
            return;
        }

        console.log("[RX] scan brut reçu:", result);

        // ── 2. Résoudre l'ID de la prescription ──────────────────────────
        // La route /pos/prescription/scan retourne prescription_id
        // La route /api/prescription/upload retourne data.id ou data.prescription_id
        const prescriptionId =
            result.prescription_id           // /pos/prescription/scan
            || result.data?.prescription_id  // /api/prescription/upload
            || result.data?.id;              // fallback

        let finalData = result.data;

        if (prescriptionId) {
            // ── 3. Évaluation stock → peuple les product_id ──────────────
            try {
                showPrescriptionToast("Matching produits en cours…", "info");
                const evalResult = await rpc(
                    `/api/prescription/${prescriptionId}/check_availability`, {}
                );
                if (evalResult?.success && evalResult.data) {
                    finalData = evalResult.data;
                    console.log(
                        "[RX] ✓ évaluation OK — méds:",
                        finalData?.medications?.length,
                        finalData?.medications
                    );
                } else {
                    console.warn("[RX] check_availability a retourné KO:", evalResult);
                }
            } catch (e) {
                console.warn("[RX] check_availability échoué (on continue sans matching):", e);
            }
        } else {
            console.warn(
                "[RX] prescription_id introuvable dans la réponse scan — pas d'évaluation possible.",
                "Réponse complète:", result
            );
        }

        // ── 4. Dispatch vers le panneau UI + pos_prescription.js ─────────
        showPrescriptionToast("Ordonnance scannée avec succès.", "success");

        window.dispatchEvent(new CustomEvent("prescription-scanned", {
            detail: {
                prescriptionId: prescriptionId || null,
                data:           finalData,
            },
        }));

        console.log("[RX] prescription-scanned dispatché — données finales:", finalData);

    } catch (err) {
        console.error("[prescription] scan error:", err);
        showPrescriptionToast(err?.message || "Erreur lors du scan de l'ordonnance.", "error");
    }
}

/* ═══════════════════════════════════════════════════════════════════════
 *  HELPERS UTILITAIRES
 * ═══════════════════════════════════════════════════════════════════════ */

function showPrescriptionToast(message, type = "info") {
    document.getElementById("pos-prescription-toast")?.remove();

    const toast = document.createElement("div");
    toast.id = "pos-prescription-toast";
    toast.textContent = message;

    Object.assign(toast.style, {
        position:     "fixed",
        right:        "24px",
        bottom:       "24px",
        zIndex:       "99999",
        background:   type === "success" ? "#16a34a" : type === "error" ? "#dc2626" : "#1a73e8",
        color:        "#fff",
        padding:      "12px 16px",
        borderRadius: "12px",
        fontSize:     "14px",
        fontWeight:   "600",
        boxShadow:    "0 8px 24px rgba(0,0,0,.22)",
        maxWidth:     "420px",
        fontFamily:   "'Google Sans','Roboto',system-ui,sans-serif",
    });

    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}

function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            const base64 = String(reader.result || "").split(",")[1];
            if (!base64) { reject(new Error("Conversion base64 impossible")); return; }
            resolve(base64);
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

function switchToCaisseTab() {
    const btn =
        document.querySelector(".register-label") ||
        document.querySelector("button.register-label") ||
        document.querySelector(".navbar-menu .btn.active") ||
        document.querySelector(".navbar-menu .btn");
    if (btn) btn.click();
}

/* ═══════════════════════════════════════════════════════════════════════
 *  AJOUTER UN PRODUIT À LA COMMANDE ACTIVE
 *  Dispatche "prescription-scanned" avec le product_id variante.
 *  pos_prescription.js appelle order.addProduct() nativement.
 * ═══════════════════════════════════════════════════════════════════════ */

async function addScannedProductToCurrentOrder(productId, lineId, btn = null, quantity = 1) {
    try {
        if (!productId) {
            showPrescriptionToast("Aucun produit lié à cette ligne.", "error");
            return;
        }

        console.log("[RX] addScannedProductToCurrentOrder — product_id:", productId, "qty:", quantity);

        // Dispatch vers pos_prescription.js → order.addProduct() via l'API POS officielle
        // name vide + prescriptionId null = dispatch interne → pas de re-affichage du panneau
        window.dispatchEvent(new CustomEvent("prescription-scanned", {
            detail: {
                prescriptionId: null,
                data: {
                    medications: [{
                        product_id: productId,
                        line_id:    lineId,
                        quantity:   quantity,
                        name:       "",
                    }],
                },
            },
        }));

        if (btn) {
            btn.disabled = true;
            btn.textContent = "Ajouté ✓";
            btn.style.background = "#16a34a";
            btn.style.cursor = "default";
        }

        showPrescriptionToast(`Produit (x${quantity}) ajouté à la commande.`, "success");

    } catch (err) {
        console.error("[RX] addScannedProductToCurrentOrder error:", err);
        showPrescriptionToast("Erreur lors de l'ajout à la commande.", "error");
    }
}

/* ═══════════════════════════════════════════════════════════════════════
 *  RENDU PANNEAU CAISSE — lignes importées (ordonnance / panier mobile)
 * ═══════════════════════════════════════════════════════════════════════ */

function getOrderlinesContainer() {
    return (
        document.querySelector(".orderlines") ||
        document.querySelector(".leftpane .paymentlines") ||
        document.querySelector(".leftpane") ||
        document.querySelector(".pos-leftheader")?.parentElement ||
        document.querySelector(".product-screen .leftpane")
    );
}

function renderImportedLinesInCaisse(title, items) {
    const container = getOrderlinesContainer();
    if (!container || !items?.length) return;

    let block = document.getElementById("pos-imported-lines");
    if (!block) {
        block = document.createElement("div");
        block.id = "pos-imported-lines";
        block.style.marginTop  = "10px";
        block.style.borderTop  = "1px solid #d1d5db";
        block.style.paddingTop = "10px";
        container.prepend(block);
    }

    block.innerHTML = `
        <div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;overflow:hidden;">
            <div style="padding:10px 12px;background:#e2e8f0;font-weight:700;font-size:14px;
                        color:#0f172a;display:flex;justify-content:space-between;align-items:center;">
                <span>${title}</span>
                <button id="close-imported-caisse"
                        style="border:none;background:#fff;border-radius:8px;
                               padding:4px 8px;cursor:pointer;font-size:12px;">
                    Fermer
                </button>
            </div>
            <div>
                ${items.map((item) => {
                    const ok    = item.isFound;
                    const bg    = ok ? "#ecfdf5" : "#fef2f2";
                    const color = ok ? "#065f46" : "#991b1b";
                    return `
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;
                                    gap:12px;padding:10px 12px;border-top:1px solid #e5e7eb;background:${bg};">
                            <div style="flex:1;min-width:0;">
                                <div style="font-size:14px;font-weight:700;color:#111827;line-height:1.2;">
                                    ${item.name || "-"}
                                </div>
                                ${item.description
                                    ? `<div style="margin-top:4px;font-size:12px;color:#475569;">${item.description}</div>`
                                    : ""}
                                ${item.productName
                                    ? `<div style="margin-top:4px;font-size:12px;color:${color};">${item.productName}</div>`
                                    : ""}
                                ${item.message
                                    ? `<div style="margin-top:4px;font-size:11px;color:#64748b;">${item.message}</div>`
                                    : ""}
                                <div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;">
                                    <button class="import-add-to-order-btn"
                                            data-line-id="${item.lineId    || ""}"
                                            data-product-id="${item.productId || ""}"
                                            data-quantity="${item.quantity  || 1}"
                                            style="border:none;
                                                   background:${ok ? "#2563eb" : "#cbd5e1"};
                                                   color:#fff;border-radius:8px;padding:7px 10px;
                                                   cursor:${ok ? "pointer" : "not-allowed"};
                                                   font-size:12px;font-weight:700;"
                                            ${ok ? "" : "disabled"}>
                                        Ajouter à la commande
                                    </button>
                                </div>
                            </div>
                            <div style="flex-shrink:0;font-size:12px;font-weight:700;
                                        color:${color};white-space:nowrap;">
                                ${ok ? "Trouvé" : "À vérifier"}
                            </div>
                        </div>
                    `;
                }).join("")}
            </div>
        </div>
    `;

    document.getElementById("close-imported-caisse").onclick = () => block.remove();

    block.querySelectorAll(".import-add-to-order-btn").forEach((btn) => {
        btn.addEventListener("click", async () => {
            const productId = parseInt(btn.dataset.productId || "0", 10);
            const lineId    = parseInt(btn.dataset.lineId    || "0", 10);
            const quantity  = parseFloat(btn.dataset.quantity || "1");
            if (!productId) {
                showPrescriptionToast("Aucun produit lié à cette ligne.", "error");
                return;
            }
            await addScannedProductToCurrentOrder(productId, lineId, btn, quantity);
        });
    });
}

/* ═══════════════════════════════════════════════════════════════════════
 *  ÉVÉNEMENTS GLOBAUX
 * ═══════════════════════════════════════════════════════════════════════ */

window.addEventListener("toggle-rattachement-menu", () => toggleMenu());

window.addEventListener("select-rattachement-mode", async (ev) => {
    const { mode } = ev.detail;
    try {
        if (mode === "auto_attente") {
            await setRattachement("auto_attente", false, false, selectedPoste || "1");
            return;
        }
        if (mode === "manuel") {
            const queues = await rpc("/pos/rattachement/get_queues", {});
            renderQueueList(queues);
            return;
        }
        if (mode === "prioritaire") {
            const services = await rpc("/pos/rattachement/get_services", {});
            renderServiceList(services);
        }
    } catch (e) {
        console.error("[ratt] mode:", e);
    }
});

window.addEventListener("call-next-ticket",      () => callNextTicket());
window.addEventListener("finish-current-ticket", () => finishCurrentTicket());

window.addEventListener("open-prescription-scan", () => openPrescriptionScanModal());

/* ── Listener "prescription-scanned" — affichage panneau UI uniquement ──
 *  L'ajout réel au panier est géré par pos_prescription.js (patch Chrome)
 * ────────────────────────────────────────────────────────────────────── */
window.addEventListener("prescription-scanned", (ev) => {
    const payload = ev.detail || {};
    const data    = payload.data || {};
    const meds    = data.medications || [];

    // Dispatch interne depuis le bouton "Ajouter" (1 méd, name vide, prescriptionId null)
    // → ne pas réafficher le panneau
    if (meds.length === 1 && !meds[0].name && payload.prescriptionId === null) return;

    currentScannedPrescription = payload;
    console.log("[RX] Prescription scannée reçue =", payload);

    switchToCaisseTab();

    const items = meds.map((m) => ({
        name:          m.name,
        description:   `${m.dosage || ""} ${m.form || ""}`.trim(),
        productName:   m.product_name || "Non trouvé dans le catalogue",
        message:       m.evaluation_message || "",
        productId:     m.product_id,
        productTmplId: m.product_tmpl_id,
        lineId:        m.line_id,
        quantity:      m.quantity || 1,
        isFound:       !!m.product_id,
    }));

    renderImportedLinesInCaisse("Ordonnance scannée", items);
});

// Fermer le menu en cliquant en dehors
document.addEventListener("click", (ev) => {
    const wrap = document.querySelector(".ratt-wrapper");
    if (wrap && !wrap.contains(ev.target)) closeMenu();
});

// Init
setTimeout(() => loadCurrentRattachement(), 800);
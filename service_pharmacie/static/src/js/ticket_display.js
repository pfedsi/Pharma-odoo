"use strict";


let queuesCache = [];
let refreshIntervalId = null;
let isRefreshing = false;
let isCreatingTicket = false;
const REFRESH_MS = 10000;

// ── Helpers ──────────────────────────────────────────────────────────
function getEl(id) {
    return document.getElementById(id);
}

function showMessage(message, type) {
    const box = getEl("ticket-display-message");
    if (!box) return;
    box.className = "ticket-message" + (type ? " " + type : "");
    box.textContent = message;
    box.classList.remove("hidden");
    if (type === "success") setTimeout(hideMessage, 5000);
}

function hideMessage() {
    const box = getEl("ticket-display-message");
    if (!box) return;
    box.textContent = "";
    box.className = "ticket-message hidden";
}

function showLoader() {
    const el = getEl("ticket-display-loader");
    if (el) el.classList.remove("hidden");
}

function hideLoader() {
    const el = getEl("ticket-display-loader");
    if (el) el.classList.add("hidden");
}

function normalizeQueuesPayload(result) {
    return result?.queues || result?.data?.queues || [];
}

function areQueuesEqual(a, b) {
    return JSON.stringify(a) === JSON.stringify(b);
}

// ── API ───────────────────────────────────────────────────────────────
async function fetchQueues() {
    const response = await fetch("/api/pharmacy/queues?type_affichage=physique", {
        method: "GET",
        headers: { "Content-Type": "application/json" },
    });

    const raw = await response.text();

    if (!response.ok) {
        throw new Error("Erreur HTTP " + response.status + " : " + raw);
    }

    try {
        return JSON.parse(raw);
    } catch (err) {
        console.error("Réponse non JSON pour /api/pharmacy/queues :", raw);
        throw new Error("Réponse invalide du serveur pour les files.");
    }
}

async function createPhysicalTicket(queueId) {
    const formData = new URLSearchParams();
    formData.append("queue_id", String(queueId));
    formData.append("type_ticket", "physique");

    const response = await fetch("/api/pharmacy/tickets", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
        body: formData.toString(),
    });

    const raw = await response.text();
    const contentType = response.headers.get("content-type") || "";

    if (!response.ok) {
        console.error("Erreur API ticket :", response.status, raw);
        throw new Error("Erreur HTTP " + response.status);
    }

    if (!contentType.includes("application/json")) {
        console.error("Réponse HTML au lieu de JSON :", raw);
        throw new Error("Le serveur a renvoyé du HTML au lieu de JSON.");
    }

    try {
        return JSON.parse(raw);
    } catch (err) {
        console.error("JSON invalide pour /api/pharmacy/tickets :", raw);
        throw new Error("Réponse JSON invalide.");
    }
}
// ── Rendu des files ───────────────────────────────────────────────────
function renderQueues(queues) {
    const container = getEl("ticket-display-queues");
    if (!container) return;

    if (!queues || !queues.length) {
        container.innerHTML = `<div class="empty-state">Aucune file active disponible</div>`;
        return;
    }

    container.innerHTML = queues.map((queue, i) => `
        <div class="queue-card" data-queue-id="${queue.id}" style="animation-delay:${i * 60}ms">
            <div class="queue-card-header">
                <div class="queue-name">${queue.service || queue.nom || "—"}</div>
            </div>
            <div class="queue-meta">
                <div>
                    <span>En attente</span>
                    <strong class="queue-waiting-count">${queue.nb_en_attente || queue.en_attente || 0}</strong>
                </div>
                <div>
                    <span>Temps estimé</span>
                    <strong class="queue-waiting-time">${queue.temps_attente_estime || 0} min</strong>
                </div>
            </div>
            <button
                type="button"
                class="create-ticket-btn"
                data-queue-id="${queue.id}"
                data-service-name="${queue.service || queue.nom || "—"}">
                Prendre un ticket
            </button>
        </div>
    `).join("");

    bindCreateButtons();
}

async function refreshQueuesSilently(forceRender = false) {
    if (isRefreshing || isCreatingTicket) return;

    isRefreshing = true;

    try {
        const result = await fetchQueues();
        const queues = normalizeQueuesPayload(result);

        if (forceRender || !areQueuesEqual(queues, queuesCache)) {
            queuesCache = queues;
            renderQueues(queues);
        }
    } catch (err) {
        console.error("Erreur refresh queues :", err);
    } finally {
        isRefreshing = false;
    }
}

function startAutoRefresh() {
    stopAutoRefresh();
    refreshIntervalId = setInterval(() => {
        refreshQueuesSilently(false);
    }, REFRESH_MS);
}

function stopAutoRefresh() {
    if (refreshIntervalId) {
        clearInterval(refreshIntervalId);
        refreshIntervalId = null;
    }
}

// ── Boutons créer ticket ──────────────────────────────────────────────
function bindCreateButtons() {
    document.querySelectorAll(".create-ticket-btn").forEach(button => {
        button.addEventListener("click", async function () {
            if (isCreatingTicket) return;

            hideMessage();

            const queueId = parseInt(this.dataset.queueId, 10);
            const serviceName = this.dataset.serviceName || "—";

            if (!queueId) {
                showMessage("File invalide.", "error");
                return;
            }

            const confirmed = await confirmDialog(
                `Créer un ticket pour <strong>${serviceName}</strong> ?`
            );
            if (!confirmed) return;

            const oldText = this.textContent;
            isCreatingTicket = true;
            stopAutoRefresh();

            this.disabled = true;
            this.textContent = "Création…";

            try {
                const result = await createPhysicalTicket(queueId);
                const ticket = result.ticket || result.data?.ticket;

                if (!ticket) {
                    throw new Error("Réponse API invalide");
                }

                printTicket(ticket);
                showMessage(`Ticket ${ticket.numero} créé avec succès.`, "success");
                await refreshQueuesSilently(true);

            } catch (err) {
                console.error("Erreur création ticket :", err);
                showMessage(err.message || "Impossible de créer le ticket.", "error");
            } finally {
                this.disabled = false;
                this.textContent = oldText;
                isCreatingTicket = false;
                startAutoRefresh();
            }
        });
    });
}

// ── Modale de confirmation ────────────────────────────────────────────
function confirmDialog(htmlMessage) {
    return new Promise(resolve => {
        document.getElementById("_rph-modal")?.remove();

        const overlay = document.createElement("div");
        overlay.id = "_rph-modal";
        overlay.style.cssText = `
            position:fixed;inset:0;z-index:9999;
            background:rgba(15,23,42,.45);
            backdrop-filter:blur(4px);
            display:flex;align-items:center;justify-content:center;
            animation:_fadein .15s ease;
        `;

        overlay.innerHTML = `
            <style>
                @keyframes _fadein{from{opacity:0}to{opacity:1}}
                @keyframes _popin{from{opacity:0;transform:scale(.94) translateY(8px)}to{opacity:1;transform:scale(1) translateY(0)}}
                #_rph-box{
                    background:#fff;border-radius:20px;padding:28px 28px 22px;
                    max-width:380px;width:calc(100% - 40px);
                    box-shadow:0 8px 32px rgba(15,23,42,.18);
                    animation:_popin .2s cubic-bezier(.16,1,.3,1);
                    font-family:'DM Sans',sans-serif;
                }
                #_rph-box p{margin:0 0 22px;font-size:15px;color:#334155;line-height:1.55;}
                #_rph-box p strong{color:#0f172a;font-weight:700;}
                #_rph-actions{display:flex;gap:10px;justify-content:flex-end;}
                #_rph-cancel{padding:10px 18px;border:1px solid #e2e8f0;background:#f8fafc;color:#475569;border-radius:10px;font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;transition:.15s;}
                #_rph-cancel:hover{background:#e2e8f0;}
                #_rph-confirm{padding:10px 22px;background:#059669;color:#fff;border:none;border-radius:10px;font-family:inherit;font-size:14px;font-weight:600;cursor:pointer;transition:.15s;box-shadow:0 2px 8px rgba(5,150,105,.3);}
                #_rph-confirm:hover{background:#047857;}
            </style>
            <div id="_rph-box">
                <p>${htmlMessage}</p>
                <div id="_rph-actions">
                    <button id="_rph-cancel">Annuler</button>
                    <button id="_rph-confirm">Confirmer</button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        const close = val => {
            overlay.remove();
            resolve(val);
        };

        overlay.querySelector("#_rph-confirm").addEventListener("click", () => close(true));
        overlay.querySelector("#_rph-cancel").addEventListener("click", () => close(false));
        overlay.addEventListener("click", e => {
            if (e.target === overlay) close(false);
        });
    });
}

// ── Impression ticket ─────────────────────────────────────────────────
function printTicket(ticket) {
    const win = window.open("", "_blank", "width=420,height=620");
    if (!win) {
        alert("Impossible d'ouvrir la fenêtre d'impression.");
        return;
    }

    win.document.write(`<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>Ticket ${ticket.numero || ""}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700&family=DM+Mono:wght@500&display=swap');
  *{box-sizing:border-box;margin:0;padding:0;}
  body{font-family:'DM Sans',sans-serif;width:72mm;margin:0 auto;padding:6mm 5mm 8mm;background:#fff;color:#0f172a;}
  .brand{text-align:center;margin-bottom:14px;padding-bottom:12px;border-bottom:1px dashed #cbd5e1;}
  .brand-name{font-size:18px;font-weight:700;color:#059669;letter-spacing:-.3px;}
  .brand-sub{font-size:10px;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:#94a3b8;margin-top:3px;}
  .service{text-align:center;margin:14px 0 8px;font-size:13px;font-weight:600;color:#475569;text-transform:uppercase;letter-spacing:1px;}
  .number{text-align:center;font-family:'DM Mono',monospace;font-size:52px;font-weight:500;color:#0f172a;line-height:1;letter-spacing:-2px;margin:8px 0 14px;}
  .rows{border-top:1px dashed #e2e8f0;padding-top:10px;display:flex;flex-direction:column;gap:7px;}
  .row{display:flex;justify-content:space-between;align-items:baseline;font-size:12px;}
  .row span:first-child{color:#64748b;font-weight:500;}
  .row span:last-child{font-weight:600;color:#0f172a;}
  .footer{text-align:center;margin-top:16px;padding-top:10px;border-top:1px dashed #e2e8f0;font-size:10px;color:#94a3b8;line-height:1.6;}
  @media print{body{margin:0;padding:5mm;}}
</style>
</head>
<body>
  <div class="brand">
    <div class="brand-name">Q-Pharma</div>
    <div class="brand-sub">File d'attente</div>
  </div>
  <div class="service">${ticket.service || "—"}</div>
  <div class="number">${ticket.numero || "—"}</div>
  <div class="rows">
    <div class="row"><span>État</span><span>${ticket.etat || "—"}</span></div>
    <div class="row"><span>Temps estimé</span><span>${ticket.temps_attente_estime || "—"} min</span></div>
    <div class="row"><span>Créé à</span><span>${ticket.heure_creation || "—"}</span></div>
  </div>
  <div class="footer">
    Conservez ce ticket<br/>Présentez-le au guichet
  </div>
  <script>
    window.onload = function() {
      window.print();
      window.onafterprint = function() { window.close(); };
    };
  <\/script>
</body>
</html>`);
    win.document.close();
}

// ── Init ─────────────────────────────────────────────────────────────
async function startTicketDisplay() {
    hideMessage();
    showLoader();

    try {
        const result = await fetchQueues();
        const queues = normalizeQueuesPayload(result);
        queuesCache = queues;
        renderQueues(queues);
        startAutoRefresh();
    } catch (err) {
        console.error(err);
        showMessage("Erreur lors du chargement des files actives.", "error");
    } finally {
        hideLoader();
    }
}

document.addEventListener("DOMContentLoaded", startTicketDisplay);
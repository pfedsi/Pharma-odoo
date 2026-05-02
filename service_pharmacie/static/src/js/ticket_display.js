"use strict";

let queuesCache = [];
let refreshIntervalId = null;
let isRefreshing = false;
let isCreatingTicket = false;
const REFRESH_MS = 10000;

// ── Helpers ──────────────────────────────────────────────────────────
function getEl(id) { return document.getElementById(id); }

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

/**
 * Extrait uniquement les chiffres/lettres finaux du numéro.
 * "File - ordonnance - 038" → "038"
 * "A-012" → "012"
 * "045" → "045"
 */
function extractNumero(raw) {
    if (!raw) return "—";
    // Cherche le dernier token alphanumérique (chiffres ou lettres)
    const match = String(raw).match(/([A-Z0-9]+)\s*$/i);
    return match ? match[1].toUpperCase() : String(raw).trim();
}

// ── API ───────────────────────────────────────────────────────────────
async function fetchQueues() {
    const response = await fetch("/api/pharmacy/queues?type_affichage=physique", {
        method: "GET",
        headers: { "Content-Type": "application/json" },
    });
    const raw = await response.text();
    if (!response.ok) throw new Error("Erreur HTTP " + response.status + " : " + raw);
    try { return JSON.parse(raw); }
    catch { throw new Error("Réponse invalide du serveur pour les files."); }
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
    if (!response.ok) throw new Error("Erreur HTTP " + response.status);
    if (!contentType.includes("application/json")) throw new Error("Le serveur a renvoyé du HTML au lieu de JSON.");
    try { return JSON.parse(raw); }
    catch { throw new Error("Réponse JSON invalide."); }
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
            <button type="button" class="create-ticket-btn"
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
    refreshIntervalId = setInterval(() => refreshQueuesSilently(false), REFRESH_MS);
}

function stopAutoRefresh() {
    if (refreshIntervalId) { clearInterval(refreshIntervalId); refreshIntervalId = null; }
}

// ── Boutons créer ticket (sans popup) ────────────────────────────────
function bindCreateButtons() {
    document.querySelectorAll(".create-ticket-btn").forEach(button => {
        button.addEventListener("click", async function () {
            if (isCreatingTicket) return;
            hideMessage();

            const queueId = parseInt(this.dataset.queueId, 10);
            if (!queueId) { showMessage("File invalide.", "error"); return; }

            const oldText = this.textContent;
            isCreatingTicket = true;
            stopAutoRefresh();
            this.disabled = true;
            this.textContent = "Création…";

            try {
                const result = await createPhysicalTicket(queueId);
                const ticket = result.ticket || result.data?.ticket;
                if (!ticket) throw new Error("Réponse API invalide");

                printTicketSilent(ticket);
                showMessage(`Ticket ${extractNumero(ticket.numero)} créé avec succès.`, "success");
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

// ── Impression silencieuse via iframe masqué ──────────────────────────
function printTicketSilent(ticket) {
    const old = document.getElementById("_print-frame");
    if (old) old.remove();

    const iframe = document.createElement("iframe");
    iframe.id = "_print-frame";
    iframe.style.cssText = "position:fixed;top:-9999px;left:-9999px;width:80mm;height:1px;border:none;visibility:hidden;";
    document.body.appendChild(iframe);

    const doc = iframe.contentWindow.document;
    doc.open();
    doc.write(buildTicketHTML(ticket));
    doc.close();

    iframe.onload = function () {
        setTimeout(() => {
            try {
                iframe.contentWindow.focus();
                iframe.contentWindow.print();
            } catch (e) {
                console.error("Erreur impression :", e);
            }
            setTimeout(() => { if (iframe.parentNode) iframe.remove(); }, 5000);
        }, 400);
    };
}

// ── HTML du ticket ────────────────────────────────────────────────────
function buildTicketHTML(ticket) {
    const now     = ticket.heure_creation
        || new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
    const date    = new Date().toLocaleDateString("fr-FR");

    // Numéro propre : on extrait uniquement les derniers chiffres/lettres
    const numero  = extractNumero(ticket.numero);

    // Service : on nettoie aussi si besoin (retire "File - " en début)
    const serviceRaw = ticket.service || ticket.nom || "Service";
    const service = serviceRaw.replace(/^file\s*[-–]\s*/i, "").trim().toUpperCase();

    const etat    = ticket.etat || "En attente";
    const attente = (ticket.temps_attente_estime != null && ticket.temps_attente_estime !== "")
        ? ticket.temps_attente_estime + " min"
        : "—";
    const devant  = (ticket.nb_en_attente != null)
        ? ticket.nb_en_attente
        : (ticket.personnes_devant != null ? ticket.personnes_devant : "—");

    const bw = [1,2,1,3,1,1,2,1,3,1,2,1,1,2,1,3,1,2,1,1,3,1,2,1,1,2,3,1,2,1];
    const bh = [14,14,10,14,12,14,10,14,12,14,10,14,12,14,10,14,12,14,10,14,12,14,10,14,12,14,10,14,12,14];
    const bars = bw.map((w, i) =>
        `<span style="display:inline-block;width:${w}px;height:${bh[i]}px;background:#111;margin:0 0.5px;vertical-align:bottom;"></span>`
    ).join("");

    return `<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8"/>
<title>Ticket ${numero}</title>
<style>
  @page { size: 80mm auto; margin: 0; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Courier New', Courier, monospace;
    width: 72mm;
    padding: 4mm 3.5mm 4mm;
    background: #fff;
    color: #111;
    font-size: 10px;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  .c { text-align: center; }
  .row { display: flex; justify-content: space-between; align-items: center; }
  .sep-solid { border: none; border-top: 1.5px solid #111; margin: 2.5mm 0; }
  .sep-dash  { border: none; border-top: 1px dashed #bbb; margin: 1.5mm 0; }
</style>
</head>
<body>

  <!-- EN-TÊTE -->
  <div class="c" style="padding-bottom:2.5mm;border-bottom:2px solid #111;margin-bottom:2.5mm;">
    <div style="font-size:15px;font-weight:900;letter-spacing:5px;">Q-PHARMA TN</div>
    <div style="font-size:6.5px;letter-spacing:3px;color:#666;margin-top:1px;">GESTION DE LA FILE D'ATTENTE</div>
  </div>
  <!-- SERVICE -->
  <div class="c" style="margin-bottom:2mm;">
    <span style="background:#111;color:#fff;font-size:7px;font-weight:700;letter-spacing:2px;padding:2px 8px;display:inline-block;">${service}</span>
  </div>
  <!-- NUMÉRO -->
  <div class="c" style="margin-bottom:2.5mm;">
    <div style="font-size:50px;font-weight:900;line-height:1;letter-spacing:-2px;">${numero}</div>
    <div style="font-size:6.5px;letter-spacing:3px;color:#999;margin-top:1mm;">VOTRE NUMÉRO</div>
  </div>
  <!-- ATTENTE EN ÉVIDENCE -->
  <div class="row" style="border-top:1.5px solid #111;border-bottom:1.5px solid #111;padding:2mm 0;margin-bottom:2.5mm;">
    <span style="font-size:7px;letter-spacing:1.5px;text-transform:uppercase;color:#555;">Attente estimée</span>
    <span style="font-size:16px;font-weight:900;">${attente}</span>
  </div>
  <!-- DÉTAILS -->
  <div style="margin-bottom:2.5mm;">
    <div class="row" style="padding:1.5px 0;"><span style="font-size:7.5px;color:#777;letter-spacing:0.5px;text-transform:uppercase;">État</span><span style="font-size:8px;font-weight:700;">${etat}</span></div>
    <hr class="sep-dash"/>
    <div class="row" style="padding:1.5px 0;"><span style="font-size:7.5px;color:#777;letter-spacing:0.5px;text-transform:uppercase;">Personnes devant</span><span style="font-size:8px;font-weight:700;">${devant}</span></div>
    <hr class="sep-dash"/>
    <div class="row" style="padding:1.5px 0;"><span style="font-size:7.5px;color:#777;letter-spacing:0.5px;text-transform:uppercase;">Heure</span><span style="font-size:8px;font-weight:700;">${now}</span></div>
    <hr class="sep-dash"/>
    <div class="row" style="padding:1.5px 0;"><span style="font-size:7.5px;color:#777;letter-spacing:0.5px;text-transform:uppercase;">Date</span><span style="font-size:8px;font-weight:700;">${date}</span></div>
  </div>
  <!-- CODE-BARRE DÉCORATIF -->
  <div class="c" style="margin:2.5mm 0 1mm;line-height:0;">${bars}</div>
  <div class="c" style="font-size:6.5px;color:#bbb;letter-spacing:0.5px;margin-bottom:2.5mm;">Q-${numero}-${date.replace(/\//g,"")}</div>
  <!-- PIED -->
  <div class="c" style="border-top:1px dashed #aaa;padding-top:2mm;font-size:6.5px;letter-spacing:1px;color:#999;text-transform:uppercase;line-height:1.8;">
    Conservez ce ticket · Présentez-le au guichet
  </div>
</body>
</html>`;
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
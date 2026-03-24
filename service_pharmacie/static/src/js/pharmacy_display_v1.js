"use strict";

/*
 * previousAppeles : Map<rattachement_id, ticket_name|null>
 * On stocke null pour "poste vide" et un nom pour "poste occupé".
 * Le popup se déclenche quand on passe de null → nom (nouveau ticket appelé).
 */
let previousAppeles = {};
let popupTimer = null;
let firstLoad = true;

/* ══ Horloge ══ */
function renderClock() {
    const el = document.getElementById("display-clock");
    if (!el) return;
    const now = new Date();
    el.innerHTML = `
        <div class="clock-time">${now.toLocaleTimeString("fr-FR", {
            hour: "2-digit", minute: "2-digit", second: "2-digit"
        })}</div>
        <div class="clock-date">${now.toLocaleDateString("fr-FR", {
            weekday: "long", day: "2-digit", month: "long"
        })}</div>
    `;
}

/* ══ Popup ══ */
function showPopup(ticketName, queueName, posteNumber) {
    const popup    = document.getElementById("ticket-popup");
    const ticketEl = document.getElementById("popup-ticket-number");
    const queueEl  = document.getElementById("popup-queue-name");
    const posteEl  = document.getElementById("popup-counter-number");
    if (!popup || !ticketEl || !queueEl || !posteEl) return;

    ticketEl.textContent = ticketName  || "--";
    queueEl.textContent  = queueName   || "";
    posteEl.textContent  = posteNumber || "--";

    /* Reset + relance animation progress bar */
    const bar = popup.querySelector(".popup-progress-bar");
    if (bar) {
        bar.style.animation = "none";
        void bar.offsetWidth;                          // force reflow
        bar.style.animation = "drain 5s linear forwards";
    }

    popup.classList.remove("hidden");

    if (popupTimer) clearTimeout(popupTimer);
    popupTimer = setTimeout(() => {
        popup.classList.add("hidden");
    }, 5000);
}

/* ══ Détection nouveau ticket appelé ══
 *
 * Règle : popup déclenché quand
 *   - le poste avait null (vide) et reçoit un ticket  → nouvel appel
 *   - le poste avait un ticket et reçoit un AUTRE ticket → changement d'appel
 * Pas de popup au premier chargement (firstLoad) pour éviter le flood initial.
 */
function detectNewAppels(queues) {
    const snapshot = {};   // nouveau snapshot à construire

    queues.forEach(queue => {
        /* Construction du snapshot complet de tous les postes */
        (queue.appeles || []).forEach(item => {
            const key = String(item.rattachement_id);
            snapshot[key] = {
                ticket_name:  item.ticket_name  || null,
                poste_number: item.poste_number || "--",
                queue_name:   queue.queue_name  || "",
            };
        });
    });

    if (!firstLoad) {
        /* Comparer snapshot actuel vs précédent */
        Object.entries(snapshot).forEach(([key, cur]) => {
            const prev = previousAppeles[key] || null;
            const prevName = prev ? prev.ticket_name : null;

            if (cur.ticket_name && cur.ticket_name !== prevName) {
                /* Nouveau ticket sur ce poste → popup */
                showPopup(cur.ticket_name, cur.queue_name, cur.poste_number);
            }
        });
    }

    previousAppeles = snapshot;
    firstLoad = false;
}

/* ══ Rendu grille ══ */
function renderQueues(queues) {
    const grid = document.getElementById("display-grid");
    if (!grid) return;

    if (!queues || !queues.length) {
        grid.innerHTML = `<div class="empty-state">Aucune file active</div>`;
        return;
    }

    grid.innerHTML = queues.map(queue => {
        const appeles   = queue.appeles    || [];
        const enAttente = queue.en_attente || [];
        const total     = appeles.length + enAttente.length;

        /* ── Section appelés ── */
        let appelHtml = "";
        if (appeles.length) {
            appelHtml = appeles.map(item => `
                <div class="ticket-line is-appele">
                    <div class="tl-top">
                        <div class="ticket-label">Guichet ${item.poste_number}</div>
                        <div class="ticket-value">${item.ticket_name}</div>
                    </div>
                    <div class="tl-bot">
                        <div class="poste-label">Poste</div>
                        <div class="poste-value">${item.poste_number}</div>
                    </div>
                </div>`).join("");
        } else {
            appelHtml = `<div class="no-ticket">Aucun ticket en cours d'appel</div>`;
        }

        /* ── Section en attente ── */
        let attenteHtml = "";
        if (enAttente.length) {
            attenteHtml = `
                <div class="section-label">File d'attente</div>
                ${enAttente.map((item, index) => `
                <div class="ticket-line is-waiting">
                    <div class="tl-top">
                        <div class="ticket-label">Position ${index + 1}</div>
                        <div class="ticket-value">${item.ticket_name}</div>
                    </div>
                    <div class="tl-bot">
                        <div class="poste-label">Statut</div>
                        <div class="poste-value">En attente</div>
                    </div>
                </div>`).join("")}`;
        }

        return `
            <div class="display-card">
                <div class="card-header">
                    <div class="queue-title">${queue.queue_name || "--"}</div>
                    <div class="queue-badge">${total} ticket${total !== 1 ? "s" : ""}</div>
                </div>
                <div class="card-body">
                    ${appelHtml}
                    ${attenteHtml}
                </div>
            </div>`;
    }).join("");
}

/* ══ Fetch ══ */
async function fetchData() {
    try {
        const response = await fetch("/pharmacy/display/data", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const result = await response.json();
        if (!result.success) return;

        const queues = result.queues || [];
        detectNewAppels(queues);
        renderQueues(queues);

    } catch (e) {
        _logger.error && _logger.error(e);
        const grid = document.getElementById("display-grid");
        if (grid) grid.innerHTML = `
            <div class="empty-state" style="color:#dc2626;">
                Erreur de connexion — nouvelle tentative dans 2s
            </div>`;
    }
}

/* ══ Init ══ */
function startDisplay() {
    renderClock();
    setInterval(renderClock, 1000);
    fetchData();
    setInterval(fetchData, 2000);
}

document.addEventListener("DOMContentLoaded", startDisplay);
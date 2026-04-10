// ═══════════════════════════════════════════════════════════════════
//  Pharmacy Display — JS principal
//  - Affiche uniquement les tickets APPELÉS (pas la liste en attente)
//  - Compteurs "En cours" + "En attente" toujours visibles
//  - "Service disponible" quand aucun ticket actif
//  - File d'attente des popups : le suivant attend la fin du son
// ═══════════════════════════════════════════════════════════════════

// ── Horloge ─────────────────────────────────────────────────────────
function updateClock() {
    const el = document.getElementById("display-clock");
    if (!el) return;
    const now  = new Date();
    const time = now.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    const date = now.toLocaleDateString("fr-FR", { weekday: "long", day: "2-digit", month: "long", year: "numeric" });
    const timeEl = el.querySelector(".clock-time");
    const dateEl = el.querySelector(".clock-date");
    if (timeEl) timeEl.textContent = time;
    if (dateEl) dateEl.textContent = date.charAt(0).toUpperCase() + date.slice(1);
}
setInterval(updateClock, 1000);
updateClock();

// ── État global ──────────────────────────────────────────────────────
let lastData      = null;
let popupQueue    = [];
let popupBusy     = false;
let currentSpeech = null;

// ── Synthèse vocale ──────────────────────────────────────────────────
function speak(text, onEnd) {
    if (!window.speechSynthesis) { onEnd && onEnd(); return; }
    const utter   = new SpeechSynthesisUtterance(text);
    utter.lang    = "fr-FR";
    utter.rate    = 0.95;
    utter.pitch   = 1;
    utter.onend   = () => { currentSpeech = null; onEnd && onEnd(); };
    currentSpeech = utter;
    window.speechSynthesis.speak(utter);
}

// ── File d'attente des popups ────────────────────────────────────────
function enqueuePopup(ticketName, posteNumber, queueName) {
    popupQueue.push({ ticketName, posteNumber, queueName });
    if (!popupBusy) processNextPopup();
}

function processNextPopup() {
    if (popupQueue.length === 0) { popupBusy = false; return; }
    popupBusy = true;
    const { ticketName, posteNumber, queueName } = popupQueue.shift();
    showPopup(ticketName, posteNumber, queueName, () => processNextPopup());
}

// ── Popup ────────────────────────────────────────────────────────────
const POPUP_DURATION = 6000;

function showPopup(ticketName, posteNumber, queueName, onDone) {
    const popup    = document.getElementById("ticket-popup");
    const ticketEl = document.getElementById("popup-ticket-number");
    const posteEl  = document.getElementById("popup-counter-number");
    const queueEl  = document.getElementById("popup-queue-name");
    const bar      = popup && popup.querySelector(".popup-progress-bar");

    if (!popup) { onDone && onDone(); return; }

    if (ticketEl) ticketEl.textContent = ticketName  || "—";
    if (posteEl)  posteEl.textContent  = posteNumber || "—";
    if (queueEl)  queueEl.textContent  = queueName   || "";

    popup.classList.remove("hidden");
    popup.classList.add("visible");

    if (bar) {
        bar.style.transition = "none";
        bar.style.width      = "100%";
        void bar.offsetWidth;
        bar.style.transition = `width ${POPUP_DURATION}ms linear`;
        bar.style.width      = "0%";
    }

    const speechText = `Ticket ${ticketName}, veuillez vous rendre au poste ${posteNumber}`;
    speak(speechText, () => {
        setTimeout(() => {
            popup.classList.remove("visible");
            popup.classList.add("hidden");
            onDone && onDone();
        }, 400);
    });
}

// ── Rendu de la grille ────────────────────────────────────────────────
function renderGrid(queues) {
    const grid = document.getElementById("display-grid");
    if (!grid) return;

    if (!queues || queues.length === 0) {
        grid.innerHTML = "";
        return;
    }

    grid.innerHTML = queues.map(q => {
        const appeles   = q.appeles   || [];
        const enAttente = q.en_attente || [];
        const isEmpty   = appeles.length === 0 && enAttente.length === 0;
        const total     = appeles.length + enAttente.length;

        // ── Badge en-tête
        const badge = isEmpty
            ? `<span class="queue-badge queue-badge--free">Libre</span>`
            : `<span class="queue-badge queue-badge--waiting">${total} ticket${total > 1 ? "s" : ""}</span>`;

        // ── Ligne de stats (toujours visible)
        const statsRow = `
            <div class="card-stats">
                <div class="stat-cell">
                    <div class="stat-number ${appeles.length > 0 ? "stat-number--active" : "stat-number--zero"}">${appeles.length}</div>
                    <div class="stat-label">En cours</div>
                </div>
                <div class="stat-cell">
                    <div class="stat-number ${enAttente.length > 0 ? "stat-number--active" : "stat-number--zero"}">${enAttente.length}</div>
                    <div class="stat-label">En attente</div>
                </div>
            </div>`;

        // ── Corps : tickets appelés uniquement — jamais la liste en attente
        let bodyContent;

        if (isEmpty) {
            bodyContent = `
                <div class="available-state">
                    <span class="available-state__dot"></span>
                    <span class="available-state__label">Service disponible</span>
                </div>`;
        } else {
            const appelRows = appeles.map(a => `
                <div class="ticket-called">
                    <div class="ticket-called__top">
                        <div class="ticket-called__label">Ticket · En cours</div>
                        <div class="ticket-called__number">${a.ticket_name || "—"}</div>
                    </div>
                    <div class="ticket-called__bottom">
                        <div>
                            <div class="poste-label">Poste</div>
                            <div class="poste-value">${a.poste_number || "—"}</div>
                        </div>
                    </div>
                </div>`).join("");

            bodyContent = `
                <div class="card-body">
                    ${appeles.length > 0
                        ? `<div class="section-label">Ticket${appeles.length > 1 ? "s" : ""} appelé${appeles.length > 1 ? "s" : ""}</div>${appelRows}`
                        : ""}
                </div>`;
        }

        return `
            <div class="display-card${isEmpty ? " is-available" : ""}">
                <div class="card-header">
                    <span class="queue-title">${q.queue_name || "—"}</span>
                    ${badge}
                </div>
                ${statsRow}
                ${bodyContent}
            </div>`;
    }).join("");
}

// ── Détection des nouveaux appels ─────────────────────────────────────
function detectNewCalls(newQueues, oldQueues) {
    if (!oldQueues) return;

    const oldAppeles = new Set();
    (oldQueues || []).forEach(q =>
        (q.appeles || []).forEach(a => oldAppeles.add(`${q.queue_id}-${a.ticket_id}`))
    );

    (newQueues || []).forEach(q => {
        (q.appeles || []).forEach(a => {
            const key = `${q.queue_id}-${a.ticket_id}`;
            if (!oldAppeles.has(key)) {
                enqueuePopup(a.ticket_name, a.poste_number, q.queue_name);
            }
        });
    });
}

// ── Polling API ───────────────────────────────────────────────────────
async function fetchAndRender() {
    try {
        const response = await fetch("/pharmacy/display/data");
        const res      = await response.json();

        if (!res?.success) return;

        const queues = res.queues || [];
        detectNewCalls(queues, lastData);
        lastData = queues;
        renderGrid(queues);

    } catch (err) {
        console.error("[display] fetchAndRender:", err);
    }
}

fetchAndRender();
setInterval(fetchAndRender, 3000);
/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

// ── État ────────────────────────────────────────────────────────
let selectedPoste = "1";
let liveTimer     = null;

// ── Helpers DOM ─────────────────────────────────────────────────
const byId       = id => document.getElementById(id);
const getMenu    = ()  => byId("rattachement-menu");
const getSublist = ()  => byId("rattachement-sublist");

// ── Menu ────────────────────────────────────────────────────────
function openMenu() {
    const m = getMenu();
    if (!m) return;
    m.classList.add("is-open");
    renderPosteGrid();
    startLive();
}

function closeMenu() {
    const m   = getMenu();
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

// ── Poste grid (injecté dans #ratt-poste-grid) ──────────────────
function renderPosteGrid() {
    const grid = byId("ratt-poste-grid");
    if (!grid) return;

    grid.innerHTML = Array.from({ length: 10 }, (_, i) => {
        const n = String(i + 1);
        return `<button type="button" class="ratt-poste-btn${selectedPoste === n ? " active" : ""}" data-poste="${n}">${n}</button>`;
    }).join("");

    grid.querySelectorAll(".ratt-poste-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            selectedPoste = btn.dataset.poste;
            renderPosteGrid();
        });
    });
}

// ── Badge mode ───────────────────────────────────────────────────
const MODE_META = {
    manuel:       { label: "Manuel",      cls: "ratt-badge--manuel" },
    auto_attente: { label: "Automatique", cls: "ratt-badge--auto"   },
    prioritaire:  { label: "Prioritaire", cls: "ratt-badge--prioritaire" },
};

function updateStatus(mode, queueName, posteNumber = false) {
    const modeEl  = byId("rattachement-mode-label");
    const queueEl = byId("rattachement-queue-label");
    const posteEl = byId("rattachement-poste-label");

    if (modeEl) {
        const meta     = MODE_META[mode] || { label: "Aucun", cls: "ratt-badge--aucun" };
        modeEl.textContent = meta.label;
        modeEl.className   = `ratt-badge ${meta.cls}`;
    }
    if (queueEl) queueEl.textContent = queueName  || "—";
    if (posteEl) posteEl.textContent = posteNumber || "1";

    document.querySelectorAll(".ratt-mode-btn").forEach(btn => {
        btn.classList.toggle("is-active", btn.dataset.mode === mode);
    });
}

// ── Ticket actif ─────────────────────────────────────────────────
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

async function refreshLive() {
    const grid = byId("ratt-queues-grid");
    if (!grid) return;

    try {
        // ⚠️ Utiliser fetch ici pour éviter les soucis RPC POST
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
        grid.querySelectorAll(".ratt-queue-card").forEach(c => {
            oldCounts[c.dataset.queueId] = parseInt(c.dataset.count || "0");
        });

        grid.innerHTML = queues.map(q => {
            const count = (q.en_attente || []).length;
            const isZero = count === 0;
            const changed = oldCounts[String(q.queue_id)] !== undefined
                         && count !== oldCounts[String(q.queue_id)];
            const bump = (!isZero && changed) ? " bump" : "";
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

        // Réattacher les événements click
      document.addEventListener("click", ev => {
    const card = ev.target.closest(".ratt-queue-card");
    if (!card) return;
    const queueId = parseInt(card.dataset.queueId, 10);
    setRattachement("manuel", queueId, false, selectedPoste);
});

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

// ── Listes sublist ───────────────────────────────────────────────
function renderQueueList(queues) {
    const sub = getSublist();
    if (!sub) return;

    sub.innerHTML = `<p class="ratt-sublist-title">Choisir une file</p>
        ${queues.map(q =>
            `<button type="button" class="ratt-sublist-item" data-id="${q.id}">${q.name}</button>`
        ).join("")}`;

    sub.querySelectorAll(".ratt-sublist-item").forEach(btn => {
        btn.addEventListener("click", () =>
            setRattachement("manuel", parseInt(btn.dataset.id, 10), false, selectedPoste)
        );
    });
}

function renderServiceList(services) {
    const sub = getSublist();
    if (!sub) return;

    sub.innerHTML = `<p class="ratt-sublist-title">Choisir un service</p>
        ${services.map(s =>
            `<button type="button" class="ratt-sublist-item" data-id="${s.id}">${s.name}</button>`
        ).join("")}`;

    sub.querySelectorAll(".ratt-sublist-item").forEach(btn => {
        btn.addEventListener("click", () =>
            setRattachement("prioritaire", false, parseInt(btn.dataset.id, 10), selectedPoste)
        );
    });
}

// ── API ──────────────────────────────────────────────────────────
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

async function callNextTicket() {
    try {
        const r = await rpc("/pos/rattachement/call_next", {});
        updateTicket(r?.ticket?.name || null);
    } catch (e) {
        console.error("[ratt] call_next:", e);
    }
}

async function finishCurrentTicket() {
    try {
        await rpc("/pos/rattachement/finish_current", {});
        updateTicket(null);
    } catch (e) {
        console.error("[ratt] finish:", e);
    }
}

// ── Événements ───────────────────────────────────────────────────
window.addEventListener("toggle-rattachement-menu", () => toggleMenu());

window.addEventListener("select-rattachement-mode", async ev => {
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

document.addEventListener("click", ev => {
    const wrap = document.querySelector(".ratt-wrapper");
    if (wrap && !wrap.contains(ev.target)) closeMenu();
});

// Init
setTimeout(() => loadCurrentRattachement(), 800);
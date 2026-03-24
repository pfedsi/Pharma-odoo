/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
let selectedPosteNumber = "1";
function getMenu() {
    return document.getElementById("rattachement-menu");
}

function getSublist() {
    return document.getElementById("rattachement-sublist");
}

function closeMenu() {
    const menu = getMenu();
    const sub = getSublist();
    if (menu) menu.style.display = "none";
    if (sub) sub.innerHTML = "";
}

function openMenu() {
    const menu = getMenu();
    if (menu) menu.style.display = "block";
}

function toggleMenu() {
    const menu = getMenu();
    if (!menu) return;
    menu.style.display =
        menu.style.display === "none" || !menu.style.display ? "block" : "none";
}

function getModeLabel(mode) {
    if (mode === "manuel") return "Manuel";
    if (mode === "auto_attente") return "Automatique";
    if (mode === "prioritaire") return "Prioritaire";
    return "Aucun";
}

function updateRattachementStatus(mode, queueName, posteNumber = false) {
    const modeEl = document.getElementById("rattachement-mode-label");
    const queueEl = document.getElementById("rattachement-queue-label");
    const posteEl = document.getElementById("rattachement-poste-label");

    if (modeEl) {
        modeEl.textContent = getModeLabel(mode);
    }
    if (queueEl) {
        queueEl.textContent = queueName || "Aucune";
    }
    if (posteEl) {
        posteEl.textContent = posteNumber || "1";
    }
}
function renderPosteList() {
    const sub = getSublist();
    if (!sub) return;

    const postesHtml = Array.from({ length: 10 }, (_, i) => {
        const num = String(i + 1);
        return `
            <button type="button"
                    class="btn btn-sm ${selectedPosteNumber === num ? 'btn-primary' : 'btn-outline-secondary'} rattachement-poste-item"
                    data-poste="${num}">
                Poste ${num}
            </button>
        `;
    }).join("");

    const existing = sub.querySelector(".poste-selector-wrapper");
    if (existing) existing.remove();

    const wrapper = document.createElement("div");
    wrapper.className = "poste-selector-wrapper mb-3";
    wrapper.innerHTML = `
        <div class="fw-bold mb-2 mt-2">Choisir un poste</div>
        <div class="d-flex flex-wrap gap-2">
            ${postesHtml}
        </div>
        <hr/>
    `;

    sub.prepend(wrapper);

    wrapper.querySelectorAll(".rattachement-poste-item").forEach(btn => {
        btn.addEventListener("click", () => {
            selectedPosteNumber = btn.dataset.poste;
            renderPosteList();

            
        });
    });
}

async function loadCurrentRattachement() {
    try {
        const result = await rpc("/pos/rattachement/current", {});
        selectedPosteNumber = result.poste_number || "1";
        updateRattachementStatus(result.mode, result.queue_name, result.poste_number);
        updateCurrentTicketDisplay(result.current_ticket_name);
    } catch (error) {
        console.error("Erreur chargement rattachement courant :", error);
    }
}

async function setRattachement(mode, fileId = false, serviceId = false, posteNumber = "1") {
    try {
        const result = await rpc("/pos/rattachement/set", {
            mode_rattachement: mode,
            file_id: fileId,
            service_prioritaire_id: serviceId,
            poste_number: posteNumber,
        });

        updateRattachementStatus(result.mode, result.queue_name, result.poste_number);
        updateCurrentTicketDisplay(result.current_ticket_name);
        closeMenu();
    } catch (error) {
        console.error("Erreur définition rattachement :", error);
    }
}
function renderQueueList(queues) {
    const sub = getSublist();
    if (!sub) return;

    sub.innerHTML = `
        <div class="sublist-main-content">
            <div class="fw-bold mb-2 mt-2">Choisir une file</div>
            ${queues.map(q => `
                <button type="button" class="dropdown-item rattachement-queue-item" data-id="${q.id}">
                    ${q.name}
                </button>
            `).join("")}
        </div>
    `;

    renderPosteList();

    sub.querySelectorAll(".rattachement-queue-item").forEach(btn => {
        btn.addEventListener("click", async () => {
            const id = parseInt(btn.dataset.id, 10);
            await setRattachement("manuel", id, false, selectedPosteNumber);
        });
    });
}

function renderServiceList(services) {
    const sub = getSublist();
    if (!sub) return;

    sub.innerHTML = `
        <div class="sublist-main-content">
            <div class="fw-bold mb-2 mt-2">Choisir un service</div>
            ${services.map(s => `
                <button type="button" class="dropdown-item rattachement-service-item" data-id="${s.id}">
                    ${s.name}
                </button>
            `).join("")}
        </div>
    `;

    renderPosteList();

    sub.querySelectorAll(".rattachement-service-item").forEach(btn => {
        btn.addEventListener("click", async () => {
            const id = parseInt(btn.dataset.id, 10);
            await setRattachement("prioritaire", false, id, selectedPosteNumber);
        });
    });
}

function updateCurrentTicketDisplay(ticketName) {
    const ticketEl = document.getElementById("current-ticket-label");
    if (ticketEl) {
        ticketEl.textContent = ticketName || "---";
    }
}
window.addEventListener("toggle-rattachement-menu", () => {
    toggleMenu();
});

window.addEventListener("select-rattachement-mode", async (ev) => {
    const mode = ev.detail.mode;

    try {
        if (mode === "auto_attente") {
            selectedPosteNumber = selectedPosteNumber || "1";
            await setRattachement("auto_attente", false, false, selectedPosteNumber);
            return;
        }

        if (mode === "manuel") {
            const queues = await rpc("/pos/rattachement/get_queues", {});
            renderQueueList(queues);
            openMenu();
            return;
        }

        if (mode === "prioritaire") {
            const services = await rpc("/pos/rattachement/get_services", {});
            renderServiceList(services);
            openMenu();
        }
    } catch (error) {
        console.error("Erreur sélection mode rattachement :", error);
    }
});
document.addEventListener("click", (ev) => {
    const wrapper = document.querySelector(".rattachement-wrapper");
    if (!wrapper) return;
    if (!wrapper.contains(ev.target)) {
        closeMenu();
    }
});
async function callNextTicket() {
    try {
        const result = await rpc("/pos/rattachement/call_next", {});
        console.log("BOUTON SUIVANT =", result);

        if (result && result.ticket) {
            updateCurrentTicketDisplay(result.ticket.name);
        } else {
            updateCurrentTicketDisplay(false);
        }
    } catch (error) {
        console.error("Erreur bouton suivant :", error);
    }
}

async function finishCurrentTicket() {
    try {
        const result = await rpc("/pos/rattachement/finish_current", {});
        console.log("BOUTON TERMINER =", result);
        updateCurrentTicketDisplay(false);
    } catch (error) {
        console.error("Erreur bouton terminer :", error);
    }
}

window.addEventListener("call-next-ticket", async () => {
    await callNextTicket();
});

window.addEventListener("finish-current-ticket", async () => {
    await finishCurrentTicket();
});

setTimeout(() => {
    loadCurrentRattachement();
}, 1000);
/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

// ── État ────────────────────────────────────────────────────────
let selectedPoste = "1";
let liveTimer = null;
let currentScannedPrescription = null;

// ── Helpers DOM ─────────────────────────────────────────────────
const byId = (id) => document.getElementById(id);
const getMenu = () => byId("rattachement-menu");
const getSublist = () => byId("rattachement-sublist");

// ── Menu ────────────────────────────────────────────────────────
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
    if (m) m.classList.remove("is-open");
    if (sub) sub.innerHTML = "";
    stopLive();
}

function toggleMenu() {
    const m = getMenu();
    if (!m) return;
    m.classList.contains("is-open") ? closeMenu() : openMenu();
}

// ── Poste grid ──────────────────────────────────────────────────
function renderPosteGrid() {
    const grid = byId("ratt-poste-grid");
    if (!grid) return;

    grid.innerHTML = Array.from({ length: 10 }, (_, i) => {
        const n = String(i + 1);
        return `<button type="button" class="ratt-poste-btn${selectedPoste === n ? " active" : ""}" data-poste="${n}">${n}</button>`;
    }).join("");

    grid.querySelectorAll(".ratt-poste-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            selectedPoste = btn.dataset.poste;
            renderPosteGrid();
        });
    });
}

// ── Badge mode ───────────────────────────────────────────────────
const MODE_META = {
    manuel: { label: "Manuel", cls: "ratt-badge--manuel" },
    auto_attente: { label: "Automatique", cls: "ratt-badge--auto" },
    prioritaire: { label: "Prioritaire", cls: "ratt-badge--prioritaire" },
};

function updateStatus(mode, queueName, posteNumber = false) {
    const modeEl = byId("rattachement-mode-label");
    const queueEl = byId("rattachement-queue-label");
    const posteEl = byId("rattachement-poste-label");

    if (modeEl) {
        const meta = MODE_META[mode] || { label: "Aucun", cls: "ratt-badge--aucun" };
        modeEl.textContent = meta.label;
        modeEl.className = `ratt-badge ${meta.cls}`;
    }
    if (queueEl) queueEl.textContent = queueName || "—";
    if (posteEl) posteEl.textContent = posteNumber || "1";

    document.querySelectorAll(".ratt-mode-btn").forEach((btn) => {
        btn.classList.toggle("is-active", btn.dataset.mode === mode);
    });
}

// ── Ticket actif ─────────────────────────────────────────────────
function updateTicket(ticketName) {
    const el = byId("current-ticket-label");
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

// ── Live queues ──────────────────────────────────────────────────
function bindQueueCardClicks() {
    document.querySelectorAll(".ratt-queue-card").forEach((card) => {
        card.onclick = () => {
            const queueId = parseInt(card.dataset.queueId || "0", 10);
            if (queueId) {
                setRattachement("manuel", queueId, false, selectedPoste);
            }
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
            const count = (q.en_attente || []).length;
            const isZero = count === 0;
            const changed =
                oldCounts[String(q.queue_id)] !== undefined &&
                count !== oldCounts[String(q.queue_id)];
            const bump = !isZero && changed ? " bump" : "";
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
    if (liveTimer) {
        clearInterval(liveTimer);
        liveTimer = null;
    }
}

// ── Listes sublist ───────────────────────────────────────────────
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

// ── API rattachement ─────────────────────────────────────────────
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
            mode_rattachement: mode,
            file_id: fileId,
            service_prioritaire_id: serviceId,
            poste_number: posteNumber,
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

        window.dispatchEvent(new CustomEvent("pos-clear-current-order"));

        updateTicket(r?.ticket?.name || null);
        currentScannedPrescription = null;

        if (r?.prescription) {
            console.log("Prescription auto chargée =", r.prescription);

            switchToCaisseTab();
            renderPrescriptionInCaisse(r.prescription);

            showPrescriptionToast(
                "Ordonnance chargée automatiquement",
                "success"
            );
        }
if (r?.mobile_order_lines?.length) {
    console.log("Panier mobile complet =", r.mobile_order_lines);

    switchToCaisseTab();
    renderMobileOrderLinesInCaisse(r.mobile_order_lines);

    showPrescriptionToast(
        "Panier mobile chargé automatiquement",
        "success"
    );
}

    } catch (e) {
        console.error("[ratt] call_next:", e);
    }
}

async function finishCurrentTicket() {
    try {
        await rpc("/pos/rattachement/finish_current", {});
        window.dispatchEvent(new CustomEvent("pos-clear-current-order"));

        updateTicket(null);
        currentScannedPrescription = null;
    } catch (e) {
        console.error("[ratt] finish:", e);
    }
}

// ── Prescription helpers ────────────────────────────────────────
function showPrescriptionToast(message, type = "info") {
    const old = document.getElementById("pos-prescription-toast");
    if (old) old.remove();

    const toast = document.createElement("div");
    toast.id = "pos-prescription-toast";
    toast.textContent = message;

    const bg =
        type === "success" ? "#16a34a" :
        type === "error" ? "#dc2626" :
        "#2563eb";

    Object.assign(toast.style, {
        position: "fixed",
        right: "24px",
        bottom: "24px",
        zIndex: "99999",
        background: bg,
        color: "#fff",
        padding: "12px 16px",
        borderRadius: "12px",
        fontSize: "14px",
        fontWeight: "600",
        boxShadow: "0 8px 24px rgba(0,0,0,.18)",
        maxWidth: "420px",
    });

    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}

function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
            const result = reader.result || "";
            const base64 = String(result).split(",")[1];
            if (!base64) {
                reject(new Error("Conversion base64 impossible"));
                return;
            }
            resolve(base64);
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

function openPrescriptionScanModal() {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/png,image/jpeg,image/webp";
    input.style.display = "none";

    input.addEventListener("change", async (ev) => {
        const file = ev.target.files && ev.target.files[0];
        if (!file) return;

        try {
            showPrescriptionToast("Analyse de l'ordonnance en cours...", "info");

            const fileBase64 = await fileToBase64(file);

            const result = await rpc("/pos/prescription/scan", {
                filename: file.name || "ordonnance.jpg",
                file_base64: fileBase64,
                mimetype: file.type || "image/jpeg",
            });

            if (!result || !result.success) {
                showPrescriptionToast(
                    (result && result.message) || "Erreur lors du scan.",
                    "error"
                );
                return;
            }

            showPrescriptionToast("Ordonnance scannée avec succès.", "success");

            window.dispatchEvent(new CustomEvent("prescription-scanned", {
                detail: {
                    prescriptionId: result.prescription_id,
                    data: result.data,
                },
            }));

            console.log("[prescription] scanned:", result);
        } catch (err) {
            console.error("[prescription] scan error:", err);
            showPrescriptionToast(
                err?.message || "Erreur lors du scan de l'ordonnance.",
                "error"
            );
        } finally {
            input.remove();
        }
    });

    document.body.appendChild(input);
    input.click();
}

function switchToCaisseTab() {
    const caisseBtn =
        document.querySelector(".register-label") ||
        document.querySelector("button.register-label") ||
        document.querySelector(".navbar-menu .btn.active") ||
        document.querySelector(".navbar-menu .btn");

    if (caisseBtn) {
        caisseBtn.click();
    }
}

async function addScannedProductToCurrentOrder(productId, lineId, btn = null) {
    try {
        if (!productId) {
            showPrescriptionToast("Aucun produit lié à cette ligne.", "error");
            return;
        }

        const result = await rpc("/pos/prescription/get_product_for_pos", {
            product_id: productId,
        });

        if (!result || !result.success) {
            showPrescriptionToast(
                (result && result.message) || "Impossible de charger le produit.",
                "error"
            );
            return;
        }

        const productData = result.data;
        console.log("Produit POS à ajouter =", productData);

        const added = clickNativeProductCard(productData);

        if (!added) {
            showPrescriptionToast(
                "Produit trouvé mais carte introuvable dans la grille POS.",
                "error"
            );
            return;
        }

        if (btn) {
            btn.disabled = true;
            btn.textContent = "Ajouté";
            btn.style.background = "#16a34a";
            btn.style.cursor = "default";
        }

        showPrescriptionToast(
            `${productData.display_name} ajouté à la vraie caisse.`,
            "success"
        );
    } catch (err) {
        console.error("addScannedProductToCurrentOrder error:", err);
        showPrescriptionToast("Erreur lors de l'ajout à la commande.", "error");
    }
}



// ── Caisse UI ────────────────────────────────────────────────────
function getOrderlinesContainer() {
    return (
        document.querySelector(".orderlines") ||
        document.querySelector(".leftpane .paymentlines") ||
        document.querySelector(".leftpane") ||
        document.querySelector(".pos-leftheader")?.parentElement ||
        document.querySelector(".product-screen .leftpane")
    );
}

function updateManualPosTotal() {
    const totalLabel = Array.from(document.querySelectorAll("div,span"))
        .find((el) => (el.textContent || "").trim() === "Total");

    if (!totalLabel) return;

    const parent = totalLabel.parentElement;
    if (!parent) return;

    let amountEl = parent.querySelector(".manual-total-value");
    if (!amountEl) {
        amountEl = document.createElement("div");
        amountEl.className = "manual-total-value";
        parent.appendChild(amountEl);
    }

    const lines = document.querySelectorAll("#manual-pos-added-lines .manual-pos-line");
    let total = 0;

    lines.forEach((line) => {
        const qty = parseInt(line.querySelector(".manual-pos-line-qty")?.textContent || "0", 10);
        const price = Number(line.dataset.price || 0);
        total += qty * price;
    });

    amountEl.textContent = `$ ${total.toFixed(2)}`;
    amountEl.style.fontWeight = "700";
    amountEl.style.fontSize = "18px";
    amountEl.style.marginLeft = "auto";
}
function normalizeText(text) {
    return String(text || "")
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/\s+/g, " ")
        .trim();
}

function clickNativeProductCard(productData) {
    const cards = Array.from(
        document.querySelectorAll(".product, .product-card, .grid-item")
    );

    if (!cards.length) {
        console.warn("Aucune carte produit POS trouvée");
        return false;
    }

    const targetName = normalizeText(productData.display_name);
    let matchedCard = null;

    for (const card of cards) {
        const text = normalizeText(card.textContent || "");
        if (text && (text.includes(targetName) || targetName.includes(text))) {
            matchedCard = card;
            break;
        }
    }

    if (!matchedCard) {
        console.warn("Carte produit introuvable pour", productData.display_name);
        return false;
    }

    matchedCard.click();
    return true;
}
function injectProductIntoCaisse(productData) {
    const orderlines =
        document.querySelector(".orderlines") ||
        document.querySelector(".leftpane") ||
        document.querySelector(".product-screen .leftpane");

    if (!orderlines) {
        console.warn("Zone orderlines introuvable");
        return;
    }

    let list = document.getElementById("manual-pos-added-lines");
    if (!list) {
        list = document.createElement("div");
        list.id = "manual-pos-added-lines";
        list.style.borderTop = "1px solid #e5e7eb";
        list.style.marginTop = "8px";
        orderlines.appendChild(list);
    }

    const existing = list.querySelector(`[data-product-id="${productData.id}"]`);
    if (existing) {
        const qtyEl = existing.querySelector(".manual-pos-line-qty");
        const totalEl = existing.querySelector(".manual-pos-line-total");
        const currentQty = parseInt(qtyEl.textContent || "1", 10) || 1;
        const nextQty = currentQty + 1;
        const price = Number(existing.dataset.price || 0);

        qtyEl.textContent = String(nextQty);
        totalEl.textContent = `$ ${Number(price * nextQty).toFixed(2)}`;
        updateManualPosTotal();
        return;
    }

    const price = Number(productData.lst_price || 0);

    const line = document.createElement("div");
    line.className = "manual-pos-line";
    line.dataset.productId = String(productData.id);
    line.dataset.price = String(price);

    Object.assign(line.style, {
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "10px 12px",
        borderTop: "1px solid #e5e7eb",
        background: "#ffffff",
        fontSize: "14px",
    });

    line.innerHTML = `
        <div style="display:flex; gap:10px; align-items:center; min-width:0;">
            <div class="manual-pos-line-qty"
                 style="font-weight:700; width:24px; text-align:center;">
                1
            </div>

            <div style="min-width:0;">
                <div style="
                    font-weight:600;
                    color:#111827;
                    white-space:nowrap;
                    overflow:hidden;
                    text-overflow:ellipsis;
                    max-width:220px;
                ">
                    ${productData.display_name}
                </div>
            </div>
        </div>

        <div class="manual-pos-line-total"
             style="font-weight:700; color:#111827; white-space:nowrap;">
            $ ${price.toFixed(2)}
        </div>
    `;

    list.appendChild(line);
    updateManualPosTotal();
}
function renderMobileOrderLinesInCaisse(lines) {
    const container = getOrderlinesContainer();

    if (!container || !lines?.length) return;

    let block = document.getElementById("pos-mobile-order-lines");
    if (!block) {
        block = document.createElement("div");
        block.id = "pos-mobile-order-lines";
        block.style.marginTop = "10px";
        block.style.borderTop = "1px solid #d1d5db";
        block.style.paddingTop = "10px";
        container.prepend(block);
    }

    block.innerHTML = `
        <div style="
            background:#fff7ed;
            border:1px solid #fdba74;
            border-radius:12px;
            overflow:hidden;
        ">
            <div style="
                padding:10px 12px;
                background:#fed7aa;
                font-weight:700;
                font-size:14px;
                color:#7c2d12;
                display:flex;
                justify-content:space-between;
                align-items:center;
            ">
                <span>Panier mobile</span>
                <button id="close-mobile-cart"
                        style="border:none;background:#fff;border-radius:8px;padding:4px 8px;cursor:pointer;font-size:12px;">
                    Fermer
                </button>
            </div>

            <div>
                ${lines.map((l) => `
                    <div style="
                        display:flex;
                        justify-content:space-between;
                        align-items:flex-start;
                        gap:12px;
                        padding:10px 12px;
                        border-top:1px solid #fed7aa;
                        background:#fffaf0;
                    ">
                        <div style="flex:1; min-width:0;">
                            <div style="font-size:14px;font-weight:700;color:#111827;">
                                ${l.name || "-"}
                            </div>
                            <div style="margin-top:4px;font-size:12px;color:#475569;">
                                Source : ${l.source_type || "-"} | Qté : ${l.quantity || 1}
                            </div>
                            <div style="margin-top:4px;font-size:12px;color:#475569;">
                                Prix : ${Number(l.price_unit || 0).toFixed(2)}
                            </div>
                        </div>

                        <button class="mobile-add-to-order-btn"
                                data-product-tmpl-id="${l.product_tmpl_id || ""}"
                                style="
                                    border:none;
                                    background:${l.product_tmpl_id ? "#2563eb" : "#cbd5e1"};
                                    color:#fff;
                                    border-radius:8px;
                                    padding:7px 10px;
                                    cursor:${l.product_tmpl_id ? "pointer" : "not-allowed"};
                                    font-size:12px;
                                    font-weight:700;
                                "
                                ${l.product_tmpl_id ? "" : "disabled"}>
                            Ajouter
                        </button>
                    </div>
                `).join("")}
            </div>
        </div>
    `;

    document.getElementById("close-mobile-cart")?.addEventListener("click", () => {
        block.remove();
    });
}


function renderPrescriptionInCaisse(data) {
    const meds = (data && data.medications) || [];
    const container = getOrderlinesContainer();

    if (!container) {
        console.warn("Zone Caisse introuvable pour afficher l'ordonnance");
        return;
    }

    let block = document.getElementById("pos-scanned-rx-lines");
    if (!block) {
        block = document.createElement("div");
        block.id = "pos-scanned-rx-lines";
        block.style.marginTop = "10px";
        block.style.borderTop = "1px solid #d1d5db";
        block.style.paddingTop = "10px";
        container.prepend(block);
    }

    block.innerHTML = `
        <div style="
            background:#f8fafc;
            border:1px solid #cbd5e1;
            border-radius:12px;
            overflow:hidden;
        ">
            <div style="
                padding:10px 12px;
                background:#e2e8f0;
                font-weight:700;
                font-size:14px;
                color:#0f172a;
                display:flex;
                justify-content:space-between;
                align-items:center;
            ">
                <span>Ordonnance scannée</span>
                <button id="close-rx-caisse"
                        style="
                            border:none;
                            background:#fff;
                            border-radius:8px;
                            padding:4px 8px;
                            cursor:pointer;
                            font-size:12px;
                        ">
                    Fermer
                </button>
            </div>

            <div>
                ${meds.map((m) => {
                    const ok = !!m.product_id;
                    const bg = ok ? "#ecfdf5" : "#fef2f2";
                    const color = ok ? "#065f46" : "#991b1b";

                    return `
                        <div style="
                            display:flex;
                            justify-content:space-between;
                            align-items:flex-start;
                            gap:12px;
                            padding:10px 12px;
                            border-top:1px solid #e5e7eb;
                            background:${bg};
                        ">
                            <div style="flex:1; min-width:0;">
                                <div style="
                                    font-size:14px;
                                    font-weight:700;
                                    color:#111827;
                                    line-height:1.2;
                                ">
                                    ${m.name || "-"}
                                </div>

                                <div style="
                                    margin-top:4px;
                                    font-size:12px;
                                    color:#475569;
                                ">
                                    ${(m.dosage || "")} ${(m.form || "")}
                                </div>

                                <div style="
                                    margin-top:4px;
                                    font-size:12px;
                                    color:${color};
                                ">
                                    ${m.product_name || "Non trouvé dans le catalogue"}
                                </div>

                                <div style="
                                    margin-top:4px;
                                    font-size:11px;
                                    color:#64748b;
                                ">
                                    ${m.evaluation_message || ""}
                                </div>

                                <div style="margin-top:8px; display:flex; gap:8px; flex-wrap:wrap;">
                                    <button class="rx-add-to-order-btn"
                                            data-line-id="${m.line_id || ""}"
                                            data-product-id="${m.product_id || ""}"
                                            style="
                                                border:none;
                                                background:${m.product_id ? "#2563eb" : "#cbd5e1"};
                                                color:#fff;
                                                border-radius:8px;
                                                padding:7px 10px;
                                                cursor:${m.product_id ? "pointer" : "not-allowed"};
                                                font-size:12px;
                                                font-weight:700;
                                            "
                                            ${m.product_id ? "" : "disabled"}>
                                        Ajouter à la commande
                                    </button>
                                </div>
                            </div>

                            <div style="
                                flex-shrink:0;
                                font-size:12px;
                                font-weight:700;
                                color:${color};
                                white-space:nowrap;
                            ">
                                ${ok ? "Trouvé" : "À vérifier"}
                            </div>
                        </div>
                    `;
                }).join("")}
            </div>
        </div>
    `;

    const closeBtn = document.getElementById("close-rx-caisse");
    if (closeBtn) {
        closeBtn.onclick = () => block.remove();
    }

    block.querySelectorAll(".rx-add-to-order-btn").forEach((btn) => {
        btn.addEventListener("click", async () => {
            const productId = parseInt(btn.dataset.productId || "0", 10);
            const lineId = parseInt(btn.dataset.lineId || "0", 10);

            console.log("Ajouter à la commande POS =>", { lineId, productId });

            if (!productId) {
                showPrescriptionToast("Aucun produit lié à cette ligne.", "error");
                return;
            }

            await addScannedProductToCurrentOrder(productId, lineId, btn);
        });
    });
}

// ── Événements ───────────────────────────────────────────────────
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

window.addEventListener("call-next-ticket", () => callNextTicket());
window.addEventListener("finish-current-ticket", () => finishCurrentTicket());
window.addEventListener("open-prescription-scan", () => {
    openPrescriptionScanModal();
});
window.addEventListener("prescription-scanned", async (ev) => {
    const payload = ev.detail || {};
    const data = payload.data || {};

    currentScannedPrescription = payload;
    console.log("Prescription scannée reçue dans POS =", payload);

    switchToCaisseTab();
    renderPrescriptionInCaisse(data);

    
});

document.addEventListener("click", (ev) => {
    const wrap = document.querySelector(".ratt-wrapper");
    if (wrap && !wrap.contains(ev.target)) closeMenu();
});

// Init
setTimeout(() => loadCurrentRattachement(), 800);
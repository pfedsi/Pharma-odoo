/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Chrome } from "@point_of_sale/app/pos_app";
import { onMounted, onWillUnmount } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";

// ══════════════════════════════════════════════════════════════════
//  HELPERS
// ══════════════════════════════════════════════════════════════════

/**
 * Cherche un product.product dans le POS par son ID (variante).
 * Supporte plusieurs structures internes selon la version d'Odoo.
 */
function getProductFromPos(pos, productId) {
    if (!productId) return null;

    const id = parseInt(productId, 10);
    if (!id) return null;

    // Odoo 16 / 17 — pos.db.get_product_by_id() travaille sur product.product
    if (pos?.db?.get_product_by_id) {
        const p = pos.db.get_product_by_id(id);
        if (p) return p;
    }

    // Fallback : tableau pos.products (product.product)
    if (Array.isArray(pos?.products)) {
        const p = pos.products.find((x) => x.id === id);
        if (p) return p;
    }

    // Fallback : pos.db.product_by_id (map interne)
    if (pos?.db?.product_by_id) {
        const p = pos.db.product_by_id[id];
        if (p) return p;
    }

    return null;
}

/**
 * Retourne la commande POS active quelle que soit la version.
 */
function getCurrentOrder(pos) {
    return pos?.getOrder?.() || pos?.selectedOrder || pos?.get_order?.() || null;
}

function getOrderLines(order) {
    return order?.get_orderlines?.() || order?.orderlines || order?.lines || [];
}

function getPayloadPrice(med) {
    const rawPrice =
        med.price_unit ??
        med.prix_ttc ??
        med.prix_vente_tnd ??
        med.lst_price ??
        med.list_price;
    const price = Number(rawPrice);
    return Number.isFinite(price) ? price : null;
}

function findOrderLineForProduct(order, productId) {
    const lines = [...getOrderLines(order)];
    for (let i = lines.length - 1; i >= 0; i--) {
        const line = lines[i];
        const lineProduct = line?.product || line?.get_product?.();
        if (lineProduct?.id === productId) {
            return line;
        }
    }
    return null;
}

function setOrderLineUnitPrice(line, price) {
    if (!line || price === null) return;

    if (typeof line.set_unit_price === "function") {
        line.set_unit_price(price);
    } else if (typeof line.setUnitPrice === "function") {
        line.setUnitPrice(price);
    } else {
        line.price = price;
        line.price_unit = price;
    }

    line.trigger?.("change", line);
}

async function addProductToOrder(order, product, options) {
    if (typeof order?.add_product === "function") {
        return order.add_product(product, options);
    }
    if (typeof order?.addProduct === "function") {
        return order.addProduct(product, options);
    }
    throw new Error("API POS add_product/addProduct introuvable");
}

/**
 * Vide la commande courante et en crée une nouvelle.
 */
function clearCurrentOrder(pos) {
    if (!pos) return;

    try {
        const currentOrder = getCurrentOrder(pos);

        console.log("[RX] clearCurrentOrder — order =", currentOrder);

        if (!currentOrder) {
            console.warn("[RX] aucune commande active");
            document.getElementById("pos-scanned-rx-lines")?.remove();
            document.getElementById("manual-pos-added-lines")?.remove();
            document.getElementById("pos-imported-lines")?.remove();
            return;
        }

        // Supprimer toutes les lignes
        const lines = currentOrder.get_orderlines
            ? [...currentOrder.get_orderlines()]
            : [];

        console.log("[RX] lignes avant vidage =", lines.length);

        for (const line of lines) {
            try {
                currentOrder.removeOrderline?.(line);
            } catch (err) {
                console.error("[RX] erreur suppression ligne:", err);
            }
        }

        // Supprimer l'ancienne commande
        if (typeof pos.deleteOrder === "function") {
            try {
                pos.deleteOrder(currentOrder);
                console.log("[RX] ancienne commande supprimée via deleteOrder");
            } catch (err) {
                console.warn("[RX] deleteOrder impossible:", err);
            }
        }

        // Créer une nouvelle commande
        let newOrder = null;

        if (typeof pos.add_new_order === "function") {
            newOrder = pos.add_new_order();
            console.log("[RX] nouvelle commande créée via add_new_order");
        } else if (typeof pos.addNewOrder === "function") {
            newOrder = pos.addNewOrder();
            console.log("[RX] nouvelle commande créée via addNewOrder");
        }

        // Sélectionner la nouvelle commande
        if (newOrder && typeof pos.set_order === "function") {
            pos.set_order(newOrder);
            console.log("[RX] nouvelle commande sélectionnée via set_order");
        } else if (newOrder && typeof pos.setOrder === "function") {
            pos.setOrder(newOrder);
            console.log("[RX] nouvelle commande sélectionnée via setOrder");
        }

        // Nettoyer les blocs DOM injectés
        document.getElementById("pos-scanned-rx-lines")?.remove();
        document.getElementById("manual-pos-added-lines")?.remove();
        document.getElementById("pos-imported-lines")?.remove();

        console.log("[RX] caisse vidée avec succès");
    } catch (err) {
        console.error("[RX] erreur clearCurrentOrder:", err);
    }
}

// ══════════════════════════════════════════════════════════════════
//  PATCH OWL — Chrome
// ══════════════════════════════════════════════════════════════════

patch(Chrome.prototype, {
    setup() {
        super.setup(...arguments);
        this.pos = usePos();

        // ── Handler : prescription scannée ou panier mobile ────────
        // Reçoit ev.detail.data.medications[]
        // Chaque médicament doit avoir :
        //   - product_id  : product.product.id  (variante — obligatoire)
        //   - quantity    : float (optionnel, défaut 1)
        this._onPrescriptionScannedNative = async (ev) => {
            const meds = ev.detail?.data?.medications || [];
            const order = getCurrentOrder(this.pos);

            console.log("[RX] prescription-scanned reçu — meds =", meds.length, "| order =", order);

            if (!order) {
                console.warn("[RX] aucune commande POS active");
                return;
            }

            let addedCount = 0;
            let notFoundIds = [];

            for (const med of meds) {
                if (!med.product_id) {
                    console.warn("[RX] ligne sans product_id — ignorée:", med);
                    continue;
                }

                const product = getProductFromPos(this.pos, med.product_id);

                if (!product) {
                    console.warn("[RX] produit non chargé dans le POS — product_id:", med.product_id);
                    notFoundIds.push(med.product_id);
                    continue;
                }

                // ✅ Garde critique : uom_id requis par le POS pour calculer les prix.
                // Sans uom_id, le POS lève TypeError: Cannot read properties of undefined (reading 'uom_id')
                // Cause : produit créé sans unité de mesure — corriger via :
                //   env["product.template"].search([...]).write({"uom_id": env.ref("uom.product_uom_unit").id})
                if (!product.uom_id) {
                    console.warn(
                        "[RX] produit sans uom_id — ignoré (corriger en base Odoo):",
                        product.display_name || product.name,
                        "| product_id:", med.product_id
                    );
                    notFoundIds.push(med.product_id);
                    continue;
                }

                const qty = parseFloat(med.quantity || 1);
                const price = getPayloadPrice(med);

                try {
                    const addOptions = {
                        quantity: qty,
                        merge: true,
                    };
                    if (price !== null) {
                        addOptions.price = price;
                        addOptions.price_unit = price;
                    }

                    await addProductToOrder(order, product, addOptions);
                    setOrderLineUnitPrice(
                        findOrderLineForProduct(order, product.id),
                        price
                    );
                    addedCount++;
                    console.log(
                        "[RX] produit ajouté:",
                        product.display_name || product.name,
                        "x", qty,
                        "| prix =", price
                    );
                } catch (err) {
                    console.error("[RX] erreur add_product pour", med.product_id, ":", err);
                }
            }

            console.log(
                "[RX] résumé — ajoutés:", addedCount,
                "| non trouvés:", notFoundIds
            );

            if (notFoundIds.length > 0) {
                console.warn(
                    "[RX] Ces product_id n'ont pas été trouvés dans le POS " +
                    "(vérifier uom_id et available_in_pos sur le produit) :",
                    notFoundIds
                );
            }
        };

        // ── Handler : vider la commande courante ───────────────────
        this._onClearCurrentOrder = () => {
            console.log("[RX] event pos-clear-current-order reçu");
            clearCurrentOrder(this.pos);
        };

        // ── Montage / Démontage ────────────────────────────────────
        onMounted(() => {
            window.addEventListener("prescription-scanned", this._onPrescriptionScannedNative);
            window.addEventListener("pos-clear-current-order", this._onClearCurrentOrder);
            console.log("[RX] Chrome patch monté — listeners actifs");
        });

        onWillUnmount(() => {
            window.removeEventListener("prescription-scanned", this._onPrescriptionScannedNative);
            window.removeEventListener("pos-clear-current-order", this._onClearCurrentOrder);
            console.log("[RX] Chrome patch démonté — listeners supprimés");
        });
    },
});

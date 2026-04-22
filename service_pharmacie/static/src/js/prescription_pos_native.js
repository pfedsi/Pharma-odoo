/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Chrome } from "@point_of_sale/app/pos_app";
import { onMounted, onWillUnmount } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";

function getProductFromPos(pos, productId) {
    if (!productId) return null;

    if (pos?.db?.get_product_by_id) {
        const p = pos.db.get_product_by_id(productId);
        if (p) return p;
    }

    if (Array.isArray(pos?.products)) {
        const p = pos.products.find((x) => x.id === productId);
        if (p) return p;
    }

    return null;
}

function getCurrentOrder(pos) {
    return pos?.getOrder?.() || pos?.selectedOrder || null;
}

function clearCurrentOrder(pos) {
    if (!pos) return;

    try {
        let currentOrder = getCurrentOrder(pos);

        console.log("[RX] pos =", pos);
        console.log("[RX] get_order =", pos?.get_order?.());
        console.log("[RX] getOrder =", pos?.getOrder?.());
        console.log("[RX] selectedOrder =", pos?.selectedOrder);
        console.log("[RX] selected_order =", pos?.selected_order);
        console.log("[RX] currentOrder resolved =", currentOrder);

        if (!currentOrder) {
            console.warn("[RX] aucune commande active");
            document.getElementById("pos-scanned-rx-lines")?.remove();
            document.getElementById("manual-pos-added-lines")?.remove();
            return;
        }

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

        if (typeof pos.deleteOrder === "function") {
            try {
                pos.deleteOrder(currentOrder);
                console.log("[RX] ancienne commande supprimée via deleteOrder");
            } catch (err) {
                console.warn("[RX] deleteOrder impossible:", err);
            }
        }

        let newOrder = null;

        if (typeof pos.add_new_order === "function") {
            newOrder = pos.add_new_order();
            console.log("[RX] nouvelle commande créée via add_new_order");
        } else if (typeof pos.addNewOrder === "function") {
            newOrder = pos.addNewOrder();
            console.log("[RX] nouvelle commande créée via addNewOrder");
        }

        if (newOrder && typeof pos.set_order === "function") {
            pos.set_order(newOrder);
            console.log("[RX] nouvelle commande sélectionnée via set_order");
        } else if (newOrder && typeof pos.setOrder === "function") {
            pos.setOrder(newOrder);
            console.log("[RX] nouvelle commande sélectionnée via setOrder");
        }

        document.getElementById("pos-scanned-rx-lines")?.remove();
        document.getElementById("manual-pos-added-lines")?.remove();

        console.log("[RX] caisse vidée");
    } catch (err) {
        console.error("[RX] erreur clearCurrentOrder:", err);
    }
}

patch(Chrome.prototype, {
    setup() {
        super.setup(...arguments);
        this.pos = usePos();

        this._onPrescriptionScannedNative = async (ev) => {
            const meds = ev.detail?.data?.medications || [];
            const order = getCurrentOrder(this.pos);

            console.log("[RX] order au scan =", order);

            if (!order) {
                console.warn("[RX] aucune commande POS active");
                return;
            }

            for (const med of meds) {
                if (!med.product_id) continue;

                const product = getProductFromPos(this.pos, med.product_id);
                if (!product) {
                    console.warn("[RX] produit non chargé dans le POS:", med.product_id);
                    continue;
                }

                try {
                    order.add_product?.(product, {
                        quantity: 1,
                        merge: true,
                    });
                    console.log("[RX] produit ajouté au panier natif:", product.display_name || product.name);
                } catch (err) {
                    console.error("[RX] erreur add_product:", err);
                }
            }
        };

        this._onClearCurrentOrder = () => {
            console.log("[RX] event pos-clear-current-order reçu");
            clearCurrentOrder(this.pos);
        };

        onMounted(() => {
            window.addEventListener("prescription-scanned", this._onPrescriptionScannedNative);
            window.addEventListener("pos-clear-current-order", this._onClearCurrentOrder);
        });

        onWillUnmount(() => {
            window.removeEventListener("prescription-scanned", this._onPrescriptionScannedNative);
            window.removeEventListener("pos-clear-current-order", this._onClearCurrentOrder);
        });
    },
});
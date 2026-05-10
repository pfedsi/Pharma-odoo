# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model
    def _process_order(self, order, *args, **kwargs):
        """
        Override pour bloquer la commande si un produit storable
        est en rupture de stock (quantité disponible <= 0).

        La signature `(self, order, *args, **kwargs)` est compatible
        Odoo 16 et 17 quelle que soit l'arité exacte de la méthode parente.
        """
        # ── Vérification du stock avant traitement ──────────────────
        self._pharmacie_check_stock(order)

        result = super()._process_order(order, *args, **kwargs)

        order_id = result
        if isinstance(result, dict):
            order_id = result.get("id")

        pos_order = self.browse(order_id)
        if pos_order and pos_order.exists() and not pos_order.is_refund:
            pos_order._pharmacie_create_stock_picking()

        return result

    @api.model
    def _pharmacie_check_stock(self, order):
        """
        Parcourt les lignes de la commande POS (format dict reçu du frontend)
        et lève une UserError si un produit storable est en rupture de stock.

        :param order: dict envoyé par le client POS
        :raises UserError: si au moins un produit est en rupture
        """
        lines = order.get("lines", [])
        if not lines:
            return

        Product = self.env["product.product"].sudo()
        Quant   = self.env["stock.quant"].sudo()
        Warehouse = self.env["stock.warehouse"].sudo().search([], limit=1)

        errors = []

        for line in lines:
            # Les lignes arrivent sous la forme [0, 0, {vals}] (ORM many2many)
            if isinstance(line, (list, tuple)) and len(line) == 3:
                line_vals = line[2]
            elif isinstance(line, dict):
                line_vals = line
            else:
                continue

            product_id = line_vals.get("product_id")
            qty        = line_vals.get("qty", 0)

            # On ignore les remboursements (qty négative) et les qté nulles
            if not product_id or qty <= 0:
                continue

            product = Product.browse(product_id)
            if not product.exists():
                continue

            # Ne contrôler que les produits stockables
            if hasattr(product, "is_storable"):
                storable = product.is_storable
            else:
                storable = product.type == "product"

            if not storable:
                continue

            # Calculer la quantité disponible sur les locations internes
            domain = [
                ("product_id", "=", product.id),
                ("location_id.usage", "=", "internal"),
            ]
            if Warehouse:
                domain.append(
                    ("location_id", "child_of", Warehouse.lot_stock_id.id)
                )

            quants = Quant.search(domain)
            qty_available = sum(quants.mapped("quantity"))

            _logger.info(
                "[PHARMACIE] Stock check — %s : disponible=%.2f / demandé=%.2f",
                product.display_name,
                qty_available,
                qty,
            )

            if qty_available <= 0:
                errors.append(
                    _("• %s : stock épuisé (disponible : 0)") % product.display_name
                )
            elif qty_available < qty:
                errors.append(
                    _("• %s : stock insuffisant (disponible : %.2f, demandé : %.2f)")
                    % (product.display_name, qty_available, qty)
                )

        if errors:
            raise UserError(
                _("Impossible de valider la commande — rupture de stock :\n\n%s")
                % "\n".join(errors)
            )

    def _pharmacie_create_stock_picking(self):
        Picking = self.env["stock.picking"].sudo()
        Move    = self.env["stock.move"].sudo()

        move_name_field = (
            "description_picking"
            if "description_picking" in Move._fields
            else "name"
        )

        for order in self:
            if order.picking_ids:
                _logger.info(
                    "[PHARMACIE] Picking déjà existant pour %s, ignoré.", order.name
                )
                continue

            pos_picking_type = order.config_id.picking_type_id
            if not pos_picking_type:
                _logger.error(
                    "[PHARMACIE] POS config sans picking_type_id: %s",
                    order.config_id.name,
                )
                continue

            is_refund = order.is_refund

            if is_refund:
                return_picking_type = (
                    self.env["stock.picking.type"]
                    .sudo()
                    .search(
                        [
                            ("code", "=", "incoming"),
                            ("warehouse_id", "=", pos_picking_type.warehouse_id.id),
                        ],
                        limit=1,
                    )
                )

                if not return_picking_type:
                    _logger.error(
                        "[PHARMACIE] Aucun type 'incoming' trouvé pour entrepôt %s",
                        pos_picking_type.warehouse_id.name,
                    )
                    continue

                active_picking_type = return_picking_type

                src = self.env.ref(
                    "stock.stock_location_customers", raise_if_not_found=False
                ) or return_picking_type.default_location_src_id

                dest = (
                    pos_picking_type.warehouse_id.lot_stock_id
                    or return_picking_type.default_location_dest_id
                )

            else:
                active_picking_type = pos_picking_type
                src  = pos_picking_type.default_location_src_id
                dest = pos_picking_type.default_location_dest_id

            if not src or not dest:
                _logger.error(
                    "[PHARMACIE] Locations src/dest manquantes — src=%s dest=%s",
                    src,
                    dest,
                )
                continue

            _logger.info(
                "[PHARMACIE] %s — src: %s → dest: %s",
                "RETOUR" if is_refund else "VENTE",
                src.complete_name,
                dest.complete_name,
            )

            picking_vals = {
                "picking_type_id":  active_picking_type.id,
                "location_id":      src.id,
                "location_dest_id": dest.id,
                "origin":           order.name,
            }
            if "pos_order_id" in Picking._fields:
                picking_vals["pos_order_id"] = order.id

            picking = Picking.create(picking_vals)

            has_moves = False
            for line in order.lines:
                product = line.product_id

                if hasattr(product, "is_storable"):
                    storable = product.is_storable
                else:
                    storable = product.type == "product"

                if not storable:
                    continue

                qty = abs(line.qty)
                if qty <= 0:
                    continue

                move_vals = {
                    move_name_field:    product.display_name,
                    "product_id":       product.id,
                    "product_uom_qty":  qty,
                    "product_uom":      product.uom_id.id,
                    "picking_id":       picking.id,
                    "location_id":      src.id,
                    "location_dest_id": dest.id,
                }

                Move.create(move_vals)
                has_moves = True
                _logger.info(
                    "[PHARMACIE] Move créé: %s x%s",
                    product.display_name,
                    qty,
                )

            if not has_moves:
                picking.unlink()
                _logger.warning(
                    "[PHARMACIE] Aucun produit storable dans %s — picking supprimé.",
                    order.name,
                )
                continue

            picking.action_confirm()
            picking.action_assign()

            for move in picking.move_ids:
                move.quantity = move.product_uom_qty

            try:
                picking.with_context(skip_backorder=True).button_validate()
                _logger.info(
                    "[PHARMACIE] Picking %s (%s) validé — commande %s",
                    picking.name,
                    "RETOUR" if is_refund else "SORTIE",
                    order.name,
                )
            except Exception as e:
                _logger.error(
                    "[PHARMACIE] Erreur validation picking %s: %s",
                    picking.name,
                    e,
                )
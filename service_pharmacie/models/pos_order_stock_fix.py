# -*- coding: utf-8 -*-
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model
    def _process_order(self, *args, **kwargs):
        result = super()._process_order(*args, **kwargs)

        order_id = result
        if isinstance(result, dict):
            order_id = result.get("id")

        pos_order = self.browse(order_id)
        if pos_order and pos_order.exists():
            pos_order._pharmacie_create_stock_picking()

        return result

    def _pharmacie_create_stock_picking(self):
        Picking = self.env["stock.picking"].sudo()
        Move = self.env["stock.move"].sudo()

        for order in self:
            if order.picking_ids:
                continue

            picking_type = order.config_id.picking_type_id
            if not picking_type:
                _logger.error("[PHARMACIE] POS sans type opération stock: %s", order.config_id.name)
                continue

            src = picking_type.default_location_src_id
            dest = picking_type.default_location_dest_id

            if not src or not dest:
                _logger.error("[PHARMACIE] Type opération mal configuré: %s", picking_type.name)
                continue

            picking_vals = {
                "picking_type_id": picking_type.id,
                "location_id": src.id,
                "location_dest_id": dest.id,
                "origin": order.name,
            }

            if "pos_order_id" in Picking._fields:
                picking_vals["pos_order_id"] = order.id

            picking = Picking.create(picking_vals)

            for line in order.lines:
                product = line.product_id

                if product.type != "product":
                    continue

                if line.qty <= 0:
                    continue

                vals = {
                    "product_id": product.id,
                    "product_uom_qty": line.qty,
                    "product_uom": product.uom_id.id,
                    "picking_id": picking.id,
                    "location_id": src.id,
                    "location_dest_id": dest.id,
                }

                if "description_picking" in Move._fields:
                    vals["description_picking"] = product.display_name

                Move.create(vals)

            if not picking.move_ids:
                picking.unlink()
                continue

            picking.action_confirm()
            picking.action_assign()

            for move in picking.move_ids:
                move.quantity = move.product_uom_qty

            picking.with_context(skip_backorder=True).button_validate()

            _logger.info(
                "[PHARMACIE] Picking POS créé et validé %s pour commande %s",
                picking.name,
                order.name,
            )
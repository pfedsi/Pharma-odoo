# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class StockLot(models.Model):
    _inherit = "stock.lot"

    quantite_en_stock = fields.Float(
        string="Quantité en Stock",
        compute="_compute_quantite_en_stock",
        store=False,
        digits=(16, 2),
    )

    state = fields.Selection(
        [
            ("disponible", "Disponible"),
            ("faible", "Stock Faible"),
            ("epuise", "Épuisé"),
        ],
        string="État",
        compute="_compute_state",
        store=False,
    )

    @api.depends("product_id")
    def _compute_quantite_en_stock(self):
        Quant = self.env["stock.quant"].sudo()

        for rec in self:
            if not rec.product_id:
                rec.quantite_en_stock = 0.0
                continue

            quants = Quant.search([
                ("lot_id", "=", rec.id),
                ("product_id", "=", rec.product_id.id),
                ("location_id.usage", "=", "internal"),
            ])

            rec.quantite_en_stock = sum(quants.mapped("quantity"))

    @api.depends("quantite_en_stock", "product_id.product_tmpl_id.seuil_alerte_stock")
    def _compute_state(self):
        for rec in self:
            seuil = rec.product_id.product_tmpl_id.seuil_alerte_stock or 0.0

            if rec.quantite_en_stock <= 0:
                rec.state = "epuise"
            elif rec.quantite_en_stock < seuil:
                rec.state = "faible"
            else:
                rec.state = "disponible"


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.model_create_multi
    def create(self, vals_list):
        Quant = self.env["stock.quant"].sudo()

        for vals in vals_list:
            try:
                product_id = vals.get("product_id")
                if not product_id:
                    continue

                product = self.env["product.product"].browse(product_id)
                if not product.exists():
                    continue

                if product.tracking not in ("lot", "serial"):
                    continue

                if vals.get("lot_id") or vals.get("lot_name"):
                    continue

                picking_id = vals.get("picking_id")
                if not picking_id:
                    continue

                picking = self.env["stock.picking"].browse(picking_id)
                if not picking.exists():
                    continue

                # Sortie POS / vente client : prendre un lot existant avec stock
                if picking.picking_type_id.code == "outgoing":
                    quant = Quant.search([
                        ("product_id", "=", product.id),
                        ("location_id.usage", "=", "internal"),
                        ("quantity", ">", 0),
                        ("lot_id", "!=", False),
                    ], order="in_date asc", limit=1)

                    if quant:
                        vals["lot_id"] = quant.lot_id.id
                        _logger.info(
                            "[PHARMACIE] Lot existant utilisé : %s pour %s",
                            quant.lot_id.name,
                            product.display_name,
                        )
                    else:
                        _logger.warning(
                            "[PHARMACIE] Aucun lot disponible pour %s",
                            product.display_name,
                        )

                # Entrée stock : autoriser création automatique du lot
                elif picking.picking_type_id.code == "incoming":
                    base_name = (
                        product.product_tmpl_id.name
                        or product.default_code
                        or str(product.id)
                        or "LOT"
                    )
                    base_name = base_name.replace(" ", "-").upper()[:30]

                    lot = self.env["stock.lot"].sudo().create({
                        "name": "%s-%s" % (
                            base_name,
                            fields.Datetime.now().strftime("%Y%m%d%H%M%S"),
                        ),
                        "product_id": product.id,
                        "company_id": vals.get("company_id") or self.env.company.id,
                    })

                    vals["lot_id"] = lot.id

                    _logger.info(
                        "[PHARMACIE] Lot auto créé en réception : %s pour %s",
                        lot.name,
                        product.display_name,
                    )

            except Exception as e:
                _logger.error(
                    "[PHARMACIE] Erreur StockMoveLine.create product=%s : %s",
                    vals.get("product_id"),
                    e,
                )
                continue

        return super().create(vals_list)
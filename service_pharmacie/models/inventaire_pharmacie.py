# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


# =========================================================
# EXTENSION DES LOTS
# =========================================================
class StockLot(models.Model):
    _inherit = "stock.lot"

    quantite_en_stock = fields.Float(
        string="Quantité en Stock",
        compute="_compute_quantite_en_stock",
        store=False,
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

    @api.depends(
        "product_id",
        "product_id.product_tmpl_id.seuil_alerte_stock",
    )
    def _compute_quantite_en_stock(self):
        Quant = self.env["stock.quant"]
        for rec in self:
            if not rec.product_id:
                rec.quantite_en_stock = 0.0
                continue
            quants = Quant.search([
                ("lot_id", "=", rec.id),
                ("product_id", "=", rec.product_id.id),
                ("location_id.usage", "=", "internal"),
                ("quantity", ">", 0),
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


# =========================================================
# CRÉATION AUTOMATIQUE DES LOTS
# =========================================================
class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.model_create_multi
    def create(self, vals_list):
        Lot = self.env["stock.lot"]

        for vals in vals_list:
            product_id = vals.get("product_id")
            company_id = vals.get("company_id") or self.env.company.id

            if not product_id:
                continue

            product = self.env["product.product"].browse(product_id)
            template = product.product_tmpl_id

            if product.tracking != "lot":
                continue

            if vals.get("lot_id") or vals.get("lot_name"):
                continue

            base_name = (
                template.name
                or product.default_code
                or str(product.id)
            )
            base_name = (base_name or "LOT").replace(" ", "-").upper()

            now = fields.Datetime.now()
            lot_name = "%s-%s" % (
                base_name,
                now.strftime("%Y%m%d%H%M%S"),
            )

            lot = Lot.create({
                "name": lot_name,
                "product_id": product.id,
                "company_id": company_id,
            })

            vals["lot_id"] = lot.id

        return super().create(vals_list)
# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    """
    Corrige qty_available = 0 dans le popup POS pour les médicaments.

    Cause : _compute_quantities_dict cherche le stock sur toutes les locations
    sans contexte warehouse, et retourne 0 si les quants sont sur une location
    interne non sélectionnée par défaut.

    Solution : on override _compute_quantities_dict pour injecter automatiquement
    le contexte warehouse sur les médicaments, même sans contexte extérieur.
    """
    _inherit = "product.product"

    # ── Related vers product.template ──────────────────────────────────
    is_medicament = fields.Boolean(
        related="product_tmpl_id.is_medicament",
        string="Est un médicament",
        store=True,
    )
    seuil_alerte_stock = fields.Float(
        related="product_tmpl_id.seuil_alerte_stock",
        string="Seuil d'Alerte Stock",
        store=True,
        digits=(16, 2),
    )

    def _compute_quantities_dict(self, lot_id, owner_id, package_id,
                                 from_date=False, to_date=False):
        """
        Override : force le contexte warehouse sur les médicaments.
        Sans ça, qty_available = 0 dans le popup POS et partout ailleurs
        où le contexte n'est pas passé.
        """
        warehouse = self.env["stock.warehouse"].sudo().search([], limit=1)

        medicaments = self.filtered(lambda p: p.product_tmpl_id.is_medicament)
        others      = self - medicaments

        result = {}

        if others:
            result.update(
                super(ProductProduct, others)._compute_quantities_dict(
                    lot_id, owner_id, package_id, from_date, to_date
                )
            )

        if medicaments and warehouse:
            # Injecter le contexte warehouse + location pour forcer
            # la lecture sur la location de stock interne
            ctx_self = medicaments.with_context(
                location=warehouse.lot_stock_id.id,
                warehouse=warehouse.id,
            )
            med_result = super(ProductProduct, ctx_self)._compute_quantities_dict(
                lot_id, owner_id, package_id, from_date, to_date
            )

            # Vérification : si qty_available est encore 0, lire depuis stock.quant
            Quant = self.env["stock.quant"].sudo()
            for pid, vals in med_result.items():
                if vals.get("qty_available", 0) == 0:
                    quants = Quant.search([
                        ("product_id", "=", pid),
                        ("location_id", "child_of", warehouse.lot_stock_id.id),
                        ("location_id.usage", "=", "internal"),
                    ])
                    real_qty = sum(quants.mapped("quantity"))
                    if real_qty > 0:
                        vals["qty_available"]    = real_qty
                        vals["virtual_available"] = real_qty
                        vals["free_qty"]          = real_qty
                        _logger.debug(
                            "[PHARMACIE] qty fallback product_id=%s → %.2f",
                            pid, real_qty,
                        )

            result.update(med_result)

        elif medicaments and not warehouse:
            # Pas de warehouse configuré : fallback direct sur stock.quant
            Quant = self.env["stock.quant"].sudo()
            for product in medicaments:
                quants = Quant.search([
                    ("product_id", "=", product.id),
                    ("location_id.usage", "=", "internal"),
                ])
                real_qty = sum(quants.mapped("quantity"))
                result[product.id] = {
                    "qty_available":     real_qty,
                    "virtual_available": real_qty,
                    "free_qty":          real_qty,
                    "incoming_qty":      0.0,
                    "outgoing_qty":      0.0,
                }

        return result

    @api.model
    def _load_pos_data_fields(self, config_id):
        """
        Ajoute les champs pharmacie aux données envoyées au POS.
        """
        pos_fields = super()._load_pos_data_fields(config_id)
        for extra in ("qty_available", "is_medicament", "seuil_alerte_stock"):
            if extra not in pos_fields:
                pos_fields.append(extra)
        return pos_fields
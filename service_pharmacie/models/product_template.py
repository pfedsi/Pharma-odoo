# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FormeGalenique(models.Model):
    _name = "pharmacie.forme.galenique"
    _description = "Forme Galénique"
    _order = "name"

    name = fields.Char(string="Forme Galénique", required=True, translate=True)
    code = fields.Char(string="Code", size=10)
    active = fields.Boolean(default=True)

    @api.constrains("name")
    def _check_name_unique(self):
        for rec in self:
            if self.search([("id", "!=", rec.id), ("name", "=", rec.name)], limit=1):
                raise ValidationError(_("Cette forme galénique existe déjà."))


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_medicament = fields.Boolean(
        string="Est un médicament", default=False,
        help="Cocher si ce produit est un médicament soumis aux règles pharmacie.",
    )
    nom_commercial        = fields.Char(string="Nom Commercial")
    nom_generique         = fields.Char(string="DCI / Nom Générique")
    code_barre_pharmacie  = fields.Char(string="Code à Barre (CIP)", copy=False)
    fabricant             = fields.Char(string="Fabricant / Laboratoire")
    dosage                = fields.Char(string="Dosage", help="ex : 500 mg, 250 mg/5 ml")
    forme_galenique_id    = fields.Many2one("pharmacie.forme.galenique", string="Forme Galénique")
    description_pharmacie = fields.Text(string="Description / Indications")
    necessite_ordonnance  = fields.Boolean(string="Nécessite une Ordonnance", default=False)
    obligation_de_paiement = fields.Boolean(string="Obligation de Paiement", default=True)
    parapharmaceutique    = fields.Boolean(string="Parapharmaceutique", default=False)
    prix_achat_tnd        = fields.Float(string="Prix d'Achat (TND)", digits=(12, 3))
    prix_vente_tnd        = fields.Float(string="Prix de Vente Public (TND)", digits=(12, 3))
    tva_taux = fields.Selection(
        [("0", "0 %"), ("7", "7 %"), ("13", "13 %"), ("19", "19 %")],
        string="Taux TVA Tunisie", default="19",
    )
    seuil_alerte_stock = fields.Float(
        string="Seuil d'Alerte Stock", default=10.0,
        help="Déclenche une alerte quand le stock passe sous ce seuil",
    )
    quantite_stock = fields.Integer(
        string="Quantité en Stock",
        compute="_compute_quantite_stock",
        store=False,
    )
    alerte_stock = fields.Boolean(
        string="Alerte Stock Faible",
        compute="_compute_alerte_stock",
        search="_search_alerte_stock",
        store=False,
    )
    lot_count = fields.Integer(
        string="Nombre de Lots",
        compute="_compute_lot_count",
        store=False,
    )

    # ── Création ──────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        unit = self.env.ref("uom.product_uom_unit", raise_if_not_found=False)
        for vals in vals_list:
            if vals.get("is_medicament"):
                vals.update({
                    "is_storable": True,
                    "tracking": "lot",
                    "sale_ok": True,
                    "purchase_ok": True,
                })
                if "available_in_pos" in self._fields:
                    vals.setdefault("available_in_pos", True)
                if unit and "uom_id" in self._fields:
                    vals.setdefault("uom_id", unit.id)
        return super().create(vals_list)

    # ── Écriture ──────────────────────────────────────────────────────
    def write(self, vals):
        if vals.get("is_medicament"):
            unit = self.env.ref("uom.product_uom_unit", raise_if_not_found=False)
            vals.setdefault("is_storable", True)
            vals.setdefault("tracking", "lot")
            vals.setdefault("sale_ok", True)
            vals.setdefault("purchase_ok", True)
            if "available_in_pos" in self._fields:
                vals.setdefault("available_in_pos", True)
            if unit and "uom_id" in self._fields:
                vals.setdefault("uom_id", unit.id)
        return super().write(vals)

    # ── Calculs ───────────────────────────────────────────────────────
    @api.depends(
        "product_variant_ids",
        "product_variant_ids.stock_quant_ids",
        "product_variant_ids.stock_quant_ids.quantity",
        "product_variant_ids.stock_quant_ids.location_id",
    )
    def _compute_quantite_stock(self):
        Quant = self.env["stock.quant"]
        for rec in self:
            if not rec.product_variant_ids:
                rec.quantite_stock = 0
                continue
            quants = Quant.search([
                ("product_id", "in", rec.product_variant_ids.ids),
                ("location_id.usage", "=", "internal"),
                ("quantity", ">", 0),
            ])
            rec.quantite_stock = int(sum(quants.mapped("quantity")))

    @api.depends("quantite_stock", "seuil_alerte_stock")
    def _compute_alerte_stock(self):
        for rec in self:
            rec.alerte_stock = (rec.quantite_stock or 0.0) < (rec.seuil_alerte_stock or 0.0)

    def _compute_lot_count(self):
        Lot = self.env["stock.lot"]
        for rec in self:
            rec.lot_count = Lot.search_count(
                [("product_id", "in", rec.product_variant_ids.ids)]
            )

    def _search_alerte_stock(self, operator, value):
        if operator not in ("=", "!="):
            raise ValidationError(_("Opérateur non supporté pour la recherche sur alerte_stock."))
        products = self.search([]).filtered(
            lambda p: (p.quantite_stock or 0.0) < (p.seuil_alerte_stock or 0.0)
        )
        ids = products.ids
        want_true = bool(value)
        if operator == "!=":
            want_true = not want_true
        return [("id", "in", ids)] if want_true else [("id", "not in", ids)]

    # ── Actions ───────────────────────────────────────────────────────
    def action_open_moves(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Mouvements de stock',
            'res_model': 'stock.move.line',
            'view_mode': 'list,form',
            'domain': [('product_id', 'in', self.product_variant_ids.ids)],
        }

    def action_open_quants(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Stock par emplacement',
            'res_model': 'stock.quant',
            'view_mode': 'list,form',
            'domain': [('product_id', 'in', self.product_variant_ids.ids)],
        }

    def action_open_inventory_lots(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Inventaire Pharmacie',
            'res_model': 'stock.lot',
            'view_mode': 'list,form',
            'domain': [('product_id', 'in', self.product_variant_ids.ids)],
        }

    # ── Contraintes ───────────────────────────────────────────────────
    @api.constrains("prix_vente_tnd", "prix_achat_tnd")
    def _check_prix(self):
        for rec in self:
            if rec.is_medicament:
                if rec.prix_vente_tnd < 0:
                    raise ValidationError(_("Le prix de vente ne peut pas être négatif."))
                if rec.prix_achat_tnd < 0:
                    raise ValidationError(_("Le prix d'achat ne peut pas être négatif."))

    @api.constrains("seuil_alerte_stock")
    def _check_seuil(self):
        for rec in self:
            if rec.seuil_alerte_stock < 0:
                raise ValidationError(_("Le seuil ne peut pas être négatif."))

    # ── Onchange ──────────────────────────────────────────────────────
    @api.onchange("prix_vente_tnd")
    def _onchange_prix_vente_tnd(self):
        if self.is_medicament:
            self.list_price = self.prix_vente_tnd or 0.0

    @api.onchange("nom_commercial", "nom_generique", "dosage")
    def _onchange_nom_medicament(self):
        if self.is_medicament:
            parts = [self.nom_commercial, self.nom_generique, self.dosage]
            name = " - ".join(p for p in parts if p)
            if name:
                self.name = name

    @api.onchange("is_medicament")
    def _onchange_is_medicament(self):
        if self.is_medicament:
            self.is_storable = True
            self.tracking = "lot"
            self.sale_ok = True
            self.purchase_ok = True
            if "available_in_pos" in self._fields:
                self.available_in_pos = True


class StockLot(models.Model):
    _inherit = "stock.lot"

    quantite_en_stock = fields.Float(
        string="Quantité en Stock",
        compute="_compute_quantite_en_stock",
        store=False,
    )
    state = fields.Selection(
        [("disponible", "Disponible"), ("faible", "Stock Faible"), ("epuise", "Épuisé")],
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
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class FormeGalenique(models.Model):
    _name = "pharmacie.forme.galenique"
    _description = "Forme Galénique"
    _order = "name"

    _sql_constraints = [
        ("forme_galenique_name_uniq", "unique(name)", "Cette forme galénique existe déjà.")
    ]

    name = fields.Char(string="Forme Galénique", required=True, translate=True)
    code = fields.Char(string="Code", size=10)
    active = fields.Boolean(default=True)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_medicament = fields.Boolean(
        string="Est un médicament",
        default=False,
        help="Cocher si ce produit est un médicament soumis aux règles pharmacie.",
    )
    nom_commercial       = fields.Char(string="Nom Commercial")
    nom_generique        = fields.Char(string="DCI / Nom Générique")
    code_barre_pharmacie = fields.Char(string="Code à Barre (CIP)", copy=False)
    fabricant            = fields.Char(string="Fabricant / Laboratoire")
    dosage               = fields.Char(string="Dosage", help="Ex : 500 mg, 250 mg/5 ml")
    forme_galenique_id   = fields.Many2one("pharmacie.forme.galenique", string="Forme Galénique")
    description_pharmacie    = fields.Text(string="Description / Indications")
    necessite_ordonnance     = fields.Boolean(string="Nécessite une Ordonnance", default=False)
    obligation_de_paiement   = fields.Boolean(string="Obligation de Paiement", default=True)
    parapharmaceutique       = fields.Boolean(string="Parapharmaceutique", default=False)
    prix_achat_tnd = fields.Float(string="Prix d'Achat (TND)", digits=(12, 3))
    prix_vente_tnd = fields.Float(string="Prix de Vente Public (TND)", digits=(12, 3))
    tva_taux = fields.Selection(
        [("0", "0 %"), ("7", "7 %"), ("13", "13 %"), ("19", "19 %")],
        string="Taux TVA Tunisie",
        default="19",
    )
    seuil_alerte_stock = fields.Float(
        string="Seuil d'Alerte Stock",
        default=10.0,
        help="Déclenche une alerte quand le stock passe sous ce seuil",
    )
    quantite_stock = fields.Float(
        string="Quantité en Stock",
        compute="_compute_quantite_stock",
        store=False,
        digits=(16, 2),
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
    )

    def _medicament_vals(self):
        vals = {
            "sale_ok": True,
            "purchase_ok": True,
        }

        if "is_storable" in self._fields:
            vals["is_storable"] = True

        if "available_in_pos" in self._fields:
            vals["available_in_pos"] = True

        unit = self.env.ref("uom.product_uom_unit", raise_if_not_found=False)
        if unit:
            if "uom_id" in self._fields:
                vals["uom_id"] = unit.id
            if "uom_po_id" in self._fields:
                vals["uom_po_id"] = unit.id

        return vals


    def _force_storable_type(self):
        # Ne pas écrire type='product' dans Odoo 19
        # Le produit est géré par is_storable=True
        return True

    def _force_storable_type(self):
        for rec in self:
            if not rec.is_medicament:
                continue
            self.env.cr.execute(
                "SELECT type FROM product_template WHERE id = %s", (rec.id,)
            )
            row = self.env.cr.fetchone()
            if row and row[0] != "product":
                _logger.info("[PHARMACIE] Fix type %s : %s → product", rec.id, row[0])
                self.env.cr.execute(
                    "UPDATE product_template SET type = 'product' WHERE id = %s",
                    (rec.id,),
                )
                rec.invalidate_recordset(["type"])

    # ─────────────────────────────────────────────────────────────────────
    # CREATE
    # ─────────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("is_medicament"):
                for k, v in self._medicament_vals().items():
                    vals.setdefault(k, v)
                if "prix_vente_tnd" in vals and "list_price" in self._fields:
                    vals["list_price"] = vals.get("prix_vente_tnd", 0.0)
                if not vals.get("name"):
                    parts = [vals.get("nom_commercial"),
                             vals.get("nom_generique"),
                             vals.get("dosage")]
                    name = " - ".join(p for p in parts if p)
                    if name:
                        vals["name"] = name
        records = super().create(vals_list)
        records.filtered("is_medicament")._force_storable_type()
        return records

    # ─────────────────────────────────────────────────────────────────────
    # WRITE
    # ─────────────────────────────────────────────────────────────────────
    def write(self, vals):
        if self.env.context.get("skip_pharmacie"):
            return super().write(vals)

        vals = dict(vals)        
        becoming = self.env["product.template"]
        existing = self.env["product.template"]

        for rec in self:
            will_be = vals.get("is_medicament", rec.is_medicament)
            was     = rec.is_medicament
            if will_be and not was:
                becoming |= rec
            elif will_be and was:
                existing |= rec

        if becoming:
            bvals = dict(vals)
            for k, v in self._medicament_vals().items():
                bvals.setdefault(k, v)
            if "prix_vente_tnd" in bvals and "list_price" in self._fields:
                bvals["list_price"] = bvals.get("prix_vente_tnd", 0.0)
            super(ProductTemplate, becoming).write(bvals)

        if existing:
            evals = dict(vals)
            for k, v in self._medicament_vals().items():
                evals.setdefault(k, v)
            if "prix_vente_tnd" in evals and "list_price" in self._fields:
                evals["list_price"] = evals.get("prix_vente_tnd", 0.0)
            super(ProductTemplate, existing).write(evals)

        others = self - becoming - existing
        if others:
            super(ProductTemplate, others).write(vals)

        (becoming | existing)._force_storable_type()

        if {"nom_commercial", "nom_generique", "dosage"} & set(vals.keys()):
            for rec in (becoming | existing):
                if rec.is_medicament:
                    parts = [rec.nom_commercial, rec.nom_generique, rec.dosage]
                    generated = " - ".join(p for p in parts if p)
                    if generated and rec.name != generated:
                        super(ProductTemplate, rec).write({"name": generated})

        return True

    # ─────────────────────────────────────────────────────────────────────
    # COMPUTES
    # ─────────────────────────────────────────────────────────────────────
    @api.depends("product_variant_ids")
    def _compute_quantite_stock(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        location_id = warehouse.lot_stock_id.id if warehouse else False
        Quant = self.env["stock.quant"].sudo()

        for rec in self:
            variant_ids = rec.product_variant_ids.ids
            if not variant_ids:
                rec.quantite_stock = 0.0
                continue

            domain = [
                ("product_id", "in", variant_ids),
                ("location_id.usage", "=", "internal"),
            ]
            if location_id:
                domain.append(("location_id", "child_of", location_id))

            quants = Quant.search(domain)
            rec.quantite_stock = sum(quants.mapped("quantity"))

    @api.depends("quantite_stock", "seuil_alerte_stock")
    def _compute_alerte_stock(self):
        for rec in self:
            rec.alerte_stock = (rec.quantite_stock or 0.0) < (rec.seuil_alerte_stock or 0.0)

    def _compute_lot_count(self):
        Lot = self.env["stock.lot"]
        for rec in self:
            rec.lot_count = Lot.search_count([
                ("product_id", "in", rec.product_variant_ids.ids)
            ])

    def _search_alerte_stock(self, operator, value):
        if operator not in ("=", "!="):
            raise ValidationError(_("Opérateur non supporté pour alerte_stock."))
        products = self.search([]).filtered(
            lambda p: (p.quantite_stock or 0.0) < (p.seuil_alerte_stock or 0.0)
        )
        ids    = products.ids
        wanted = bool(value)
        if operator == "!=":
            wanted = not wanted
        return [("id", "in", ids)] if wanted else [("id", "not in", ids)]

    # ─────────────────────────────────────────────────────────────────────
    # ACTION correction one-shot
    # ─────────────────────────────────────────────────────────────────────
    def action_fix_medicament_type(self):
        bad = self.search([("is_medicament", "=", True)])
        for rec in bad:
            super(ProductTemplate, rec).write(rec._medicament_vals())
        bad._force_storable_type()
        return {
            "type": "ir.actions.client",
            "tag":  "display_notification",
            "params": {
                "title":   _("Correction terminée"),
                "message": _("%d médicament(s) corrigé(s).") % len(bad),
                "type":    "success",
                "sticky":  False,
            },
        }

    # ─────────────────────────────────────────────────────────────────────
    # ACTIONS inventaire
    # ─────────────────────────────────────────────────────────────────────
    def action_open_moves(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Mouvements de stock"),
            "res_model": "stock.move.line",
            "view_mode": "list,form",
            "domain": [("product_id", "in", self.product_variant_ids.ids)],
        }

    def action_open_quants(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Stock par emplacement"),
            "res_model": "stock.quant",
            "view_mode": "list,form",
            "domain": [("product_id", "in", self.product_variant_ids.ids)],
        }

    def action_open_inventory_lots(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Inventaire Pharmacie"),
            "res_model": "stock.lot",
            "view_mode": "list,form",
            "domain": [("product_id", "in", self.product_variant_ids.ids)],
        }

    def action_set_initial_stock(self, qty):
        self.ensure_one()
        if qty < 0:
            raise ValidationError(_("La quantité initiale ne peut pas être négative."))
        product = self.product_variant_ids[:1]
        if not product:
            raise ValidationError(_("Aucune variante produit trouvée."))
        location = self.env.ref("stock.stock_location_stock", raise_if_not_found=False)
        if not location:
            raise ValidationError(_("Emplacement de stock introuvable."))
        quant = self.env["stock.quant"].search([
            ("product_id", "=", product.id),
            ("location_id", "=", location.id),
            ("lot_id", "=", False),
        ], limit=1)
        if quant:
            quant.inventory_quantity = qty
        else:
            quant = self.env["stock.quant"].create({
                "product_id":         product.id,
                "location_id":        location.id,
                "inventory_quantity": qty,
            })
        quant.action_apply_inventory()

    # ─────────────────────────────────────────────────────────────────────
    # CONTRAINTES
    # ─────────────────────────────────────────────────────────────────────
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

    # ─────────────────────────────────────────────────────────────────────
    # ONCHANGE
    # ─────────────────────────────────────────────────────────────────────
    @api.onchange("prix_vente_tnd")
    def _onchange_prix_vente_tnd(self):
        if self.is_medicament and "list_price" in self._fields:
            self.list_price = self.prix_vente_tnd or 0.0

    @api.onchange("nom_commercial", "nom_generique", "dosage")
    def _onchange_nom_medicament(self):
        if self.is_medicament:
            parts = [self.nom_commercial, self.nom_generique, self.dosage]
            name  = " - ".join(p for p in parts if p)
            if name:
                self.name = name

    @api.onchange("is_medicament")
    def _onchange_is_medicament(self):
        if self.is_medicament:
            for k, v in self._medicament_vals().items():
                if k in self._fields:
                    try:
                        setattr(self, k, v)
                    except Exception:
                        pass

    # ─────────────────────────────────────────────────────────────────────
    # CHATBOT
    # ─────────────────────────────────────────────────────────────────────
    def chatbot_search_products(self, query, limit=3):
        if not query:
            return self.browse()
        return self.sudo().search([
            "|", "|",
            ("name",           "ilike", query),
            ("nom_commercial", "ilike", query),
            ("nom_generique",  "ilike", query),
        ], limit=limit)

    def chatbot_search_alternatives(self, limit=3):
        self.ensure_one()
        domain = [
            ("id", "!=", self.id),
            ("is_medicament", "=", True),
            ("necessite_ordonnance", "=", False),
        ]
        if self.nom_generique:
            domain.append(("nom_generique", "ilike", self.nom_generique))
        products = self.sudo().search(domain).filtered(lambda p: p.quantite_stock > 0)
        return products[:limit]

    def chatbot_to_dict(self, qty=1):
        self.ensure_one()
        prix_ttc = round(
            float(self.prix_vente_tnd or 0.0)
            * (1 + float(self.tva_taux or "0") / 100.0),
            3,
        )
        return {
            "product_id":           self.id,
            "nom":                  self.nom_commercial or self.name,
            "dosage":               self.dosage or "",
            "disponible":           (self.quantite_stock or 0) > 0,
            "quantite_stock":       int(self.quantite_stock or 0),
            "necessite_ordonnance": self.necessite_ordonnance,
            "prix_ttc":             prix_ttc,
            "quantite":             qty,
        }


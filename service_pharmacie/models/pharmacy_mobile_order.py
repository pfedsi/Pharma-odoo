# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PharmacyMobileOrder(models.Model):
    _name = "pharmacy.mobile.order"
    _description = "Commande mobile pharmacie"
    _order = "id desc"
    _inherit = ["mail.thread"]

    name = fields.Char(default="New", tracking=True)

    state = fields.Selection([
        ("draft", "Brouillon"),
        ("reserved", "Réservation créée"),
        ("arrived", "Arrivé"),
        ("confirmed", "Confirmée"),
        ("cancelled", "Annulée"),
    ], default="draft", required=True, tracking=True)

    partner_id = fields.Many2one("res.partner", string="Client", ondelete="set null")
    user_id = fields.Many2one("res.users", string="Utilisateur", ondelete="set null")
    session_token = fields.Char(string="Session Token", index=True)

    reservation_id = fields.Many2one(
        "pharmacy.reservation",
        string="Réservation",
        ondelete="set null",
        tracking=True,
    )
    ticket_id = fields.Many2one(
        "pharmacy.ticket",
        string="Ticket",
        ondelete="set null",
        tracking=True,
    )
    pos_order_id = fields.Many2one(
        "pos.order",
        string="Commande POS",
        ondelete="set null",
        tracking=True,
    )

    prescription_id = fields.Many2one(
        "pharmacy.prescription",
        string="Ordonnance principale",
        ondelete="set null",
    )

    service_id = fields.Many2one(
        "pharmacy.service",
        related="reservation_id.service_id",
        store=True,
        readonly=True,
        string="Service",
    )

    notes = fields.Text(string="Notes")
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id.id,
        required=True,
    )

    line_ids = fields.One2many(
        "pharmacy.mobile.order.line",
        "order_id",
        string="Lignes",
    )

    amount_total = fields.Monetary(
        string="Total",
        compute="_compute_amount_total",
        store=True,
        currency_field="currency_id",
    )

    item_count = fields.Integer(
        string="Nb articles",
        compute="_compute_item_count",
        store=True,
    )

    @api.depends("line_ids.subtotal")
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped("subtotal"))

    @api.depends("line_ids.quantity")
    def _compute_item_count(self):
        for rec in self:
            rec.item_count = int(sum(rec.line_ids.mapped("quantity")))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals.get("name") == "New":
                vals["name"] = self.env["ir.sequence"].sudo().next_by_code(
                    "pharmacy.mobile.order"
                ) or "MOB-ORDER"
        return super().create(vals_list)

    def action_cancel(self):
        for rec in self:
            if rec.state == "confirmed":
                raise ValidationError(_("Une commande confirmée ne peut pas être annulée."))
            rec.state = "cancelled"

    def action_mark_reserved(self):
        self.write({"state": "reserved"})

    def action_mark_arrived(self):
        self.write({"state": "arrived"})

    def action_mark_confirmed(self):
        self.write({"state": "confirmed"})


class PharmacyMobileOrderLine(models.Model):
    _name = "pharmacy.mobile.order.line"
    _description = "Ligne commande mobile"
    _order = "id asc"

    order_id = fields.Many2one(
        "pharmacy.mobile.order",
        required=True,
        ondelete="cascade",
    )

    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Produit",
        required=True,
        ondelete="restrict",
    )

    name = fields.Char(string="Nom", required=True)
    quantity = fields.Float(string="Quantité", default=1.0, required=True)
    price_unit = fields.Float(string="Prix unitaire", required=True)
    subtotal = fields.Float(
        string="Sous-total",
        compute="_compute_subtotal",
        store=True,
    )

    source_type = fields.Selection([
        ("parapharma", "Parapharmacie"),
        ("chatbot", "Chatbot"),
        ("prescription", "Ordonnance"),
        ("manual", "Manuel"),
    ], string="Source", default="manual", required=True)

    prescription_id = fields.Many2one("pharmacy.prescription", string="Ordonnance")
    prescription_line_id = fields.Many2one("pharmacy.prescription.line", string="Ligne ordonnance")

    requires_prescription = fields.Boolean(string="Nécessite ordonnance", default=False)
    product_type_label = fields.Char(string="Type produit")

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = (rec.quantity or 0.0) * (rec.price_unit or 0.0)

    @api.constrains("quantity")
    def _check_quantity(self):
        for rec in self:
            if rec.quantity <= 0:
                raise ValidationError(_("La quantité doit être strictement positive."))
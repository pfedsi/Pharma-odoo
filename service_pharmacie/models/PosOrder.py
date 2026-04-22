# -*- coding: utf-8 -*-
from odoo import models, fields


class PosOrder(models.Model):
    _inherit = "pos.order"

    reservation_id = fields.Many2one(
        "pharmacy.reservation",
        string="Réservation",
        ondelete="set null",
        index=True,
    )

    ticket_id = fields.Many2one(
        "pharmacy.ticket",
        string="Ticket",
        ondelete="set null",
        index=True,
    )

    mobile_order_id = fields.Many2one(
        "pharmacy.mobile.order",
        string="Commande mobile",
        ondelete="set null",
        index=True,
    )

    prescription_ids = fields.One2many(
        "pharmacy.prescription",
        "pos_order_id",
        string="Ordonnances",
    )
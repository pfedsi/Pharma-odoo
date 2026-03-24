# -*- coding: utf-8 -*-
"""
MODEL — pharmacy.queue
"""
from odoo import api, models, fields
from odoo.exceptions import ValidationError


class PharmacyQueue(models.Model):
    _name = "pharmacy.queue"
    _description = "File d'attente pharmacie"
    _rec_name = "display_name"

    name = fields.Char(string="Nom", required=True)
    active = fields.Boolean(
        string="Active",
        default=True
    )

    position_client_virtuel = fields.Integer(
        string="Position client virtuel",
        default=2,
        help="Position d'insertion du client virtuel dans la file lorsqu'il confirme sa présence."
    )

    service_id = fields.Many2one(
        "pharmacy.service",
        string="Service",
        required=False,
        ondelete="set null",
    )

    ticket_ids = fields.One2many(
        "pharmacy.ticket", "queue_id", string="Tickets"
    )

    display_name = fields.Char(compute="_compute_display_name", store=True)

    nb_en_attente = fields.Integer(
        string="En attente",
        compute="_compute_stats"
    )

    temps_attente_estime = fields.Integer(
        string="Attente estimée (min)",
        compute="_compute_stats"
    )

    @api.depends("name", "service_id.nom")
    def _compute_display_name(self):
        for rec in self:
            service = rec.service_id.nom or ""
            rec.display_name = f"{service} – {rec.name}" if service else rec.name

    @api.depends("ticket_ids.etat", "service_id.dure_estimee_par_defaut")
    def _compute_stats(self):
        for rec in self:
            en_attente = rec.ticket_ids.filtered(lambda t: t.etat == "en_attente")
            rec.nb_en_attente = len(en_attente)
            rec.temps_attente_estime = (
                rec.nb_en_attente * (rec.service_id.dure_estimee_par_defaut or 15)
                if rec.service_id else 0
            )

    @api.constrains("position_client_virtuel")
    def _check_position_client_virtuel(self):
        for rec in self:
            if rec.position_client_virtuel < 1:
                raise ValidationError(
                    "La position du client virtuel doit être supérieure ou égale à 1."
                )
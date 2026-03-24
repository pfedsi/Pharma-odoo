# -*- coding: utf-8 -*-
"""
MODEL — pharmacy.ticket
Noms de champs alignés avec ticket_views.xml :
  - name, queue_id, service_id, etat, heure_creation, priorite
"""
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class PharmacyTicket(models.Model):
    _name = "pharmacy.ticket"
    _description = "Ticket de file d'attente"
    _rec_name = "name"
    _order = "priorite desc, heure_creation asc"
    _inherit = ["mail.thread"]

    # ── Champs ────────────────────────────────────────────────────────────────

    name = fields.Char(
        string="Numéro", required=True,
        copy=False, readonly=True, default="Nouveau"
    )
    queue_id = fields.Many2one(
        "pharmacy.queue", string="File d'attente",
        required=True, ondelete="cascade"
    )
    # Aligné avec ticket_views.xml : service_id readonly
    service_id = fields.Many2one(
        "pharmacy.service",
        related="queue_id.service_id",
        store=True, readonly=True, string="Service"
    )
    user_id = fields.Many2one(
        "res.users", string="Client", ondelete="set null"
    )
    reservation_id = fields.Many2one(
        "pharmacy.reservation",
        string="Réservation", ondelete="set null", readonly=True
    )
    type_ticket = fields.Selection(
        [("physique", "Physique"), ("virtuel", "Virtuel")],
        default="physique", required=True
    )
    etat = fields.Selection(
        [
            ("en_attente", "En attente"),
            ("appele", "Appelé"),
            ("termine", "Terminé"),
            ("annule", "Annulé"),
        ],
        default="en_attente", required=True, tracking=True
    )
    # Aligné avec ticket_views.xml : priorite (widget="priority" = 0-3)
    priorite = fields.Selection(
        [("0", "Normal"), ("1", "Bas"), ("2", "Haut"), ("3", "Très haut")],
        string="Priorité", default="0"
    )
    heure_creation = fields.Datetime(
        default=fields.Datetime.now, required=True
    )
    heure_appel = fields.Datetime(readonly=True)
    heure_fin = fields.Datetime(readonly=True)
    active = fields.Boolean(default=True)

    position = fields.Integer(compute="_compute_position")

    # ── Computed ──────────────────────────────────────────────────────────────

    @api.depends("queue_id", "etat", "heure_creation", "priorite")
    def _compute_position(self):
        for rec in self:
            if rec.etat != "en_attente" or not rec.queue_id:
                rec.position = 0
                continue
            rec.position = self.search_count([
                ("queue_id", "=", rec.queue_id.id),
                ("etat", "=", "en_attente"),
                ("heure_creation", "<", rec.heure_creation),
            ]) + 1

    # ── Hooks CRUD ────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            queue = self.env["pharmacy.queue"].browse(vals.get("queue_id"))
            if not queue.exists():
                raise ValidationError(_("File d'attente introuvable."))
            if not vals.get("name") or vals["name"] == "Nouveau":
                seq = self.search_count([("queue_id", "=", queue.id)]) + 1
                vals["name"] = f"{queue.name}-{seq:03d}"
        return super().create(vals_list)

    # ── Transitions d'état ────────────────────────────────────────────────────

    def action_appeler(self):
        self.write({"etat": "appele", "heure_appel": fields.Datetime.now()})

    def action_terminer(self):
        self.write({"etat": "termine", "heure_fin": fields.Datetime.now()})

    def action_annuler(self):
        self.write({"etat": "annule", "heure_fin": fields.Datetime.now()})
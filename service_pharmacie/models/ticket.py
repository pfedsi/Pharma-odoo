# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class PharmacyTicket(models.Model):
    _name = "pharmacy.ticket"
    _description = "Ticket de file d'attente"
    _rec_name = "name"
    _order = "priorite desc, heure_creation asc"
    _inherit = ["mail.thread"]

    name = fields.Char(
        string="Numéro", required=True,
        copy=False, readonly=True, default="Nouveau",
    )
    queue_id = fields.Many2one(
        "pharmacy.queue", string="File d'attente",
        required=True, ondelete="cascade",
    )
    service_id = fields.Many2one(
        "pharmacy.service",
        related="queue_id.service_id",
        store=True, readonly=True, string="Service",
    )
    user_id = fields.Many2one(
        "res.users", string="Client", ondelete="set null",
    )
    reservation_id = fields.Many2one(
        "pharmacy.reservation",
        string="Réservation", ondelete="set null", readonly=True,
    )
    type_ticket = fields.Selection(
        [("physique", "Physique"), ("virtuel", "Virtuel")],
        default="physique", required=True,
    )
    prescription_ids = fields.One2many(
    "pharmacy.prescription",
    "ticket_id",
    string="Ordonnances"
)
    mobile_order_id = fields.Many2one(
    "pharmacy.mobile.order",
    string="Commande mobile",
    ondelete="set null",
)
    etat = fields.Selection(
        [
            ("en_attente", "En attente"),
            ("appele",     "Appelé"),
            ("termine",    "Terminé"),
            ("annule",     "Annulé"),
        ],
        default="en_attente", required=True, tracking=True,
    )

    # priorite = niveau individuel du ticket (calculé selon type_ticket + mode global)
    # Valeurs : 1 (normal) ou 2 (prioritaire — virtuel en mode virtuel_first)
    # Utilisé par _order pour trier la file.
    priorite = fields.Integer(
        string="Priorité",
        default=1,
        help=(
            "Niveau de priorité du ticket dans la file :\n"
            "- 2 : prioritaire (ticket virtuel en mode 'Virtuel en priorité').\n"
            "- 1 : normal (tous les autres cas)."
        ),
    )

    heure_creation = fields.Datetime(default=fields.Datetime.now, required=True)
    heure_appel    = fields.Datetime(readonly=True)
    heure_fin      = fields.Datetime(readonly=True)
    active         = fields.Boolean(default=True)

    position = fields.Integer(compute="_compute_position")


    def _get_mode_priorite(self):
        """Lit le paramètre global mode_priorite depuis ir.config_parameter."""
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("service_pharmacie.mode_priorite", default="mix")
        )

    # ── Computed ──────────────────────────────────────────────────────────────

    @api.depends("queue_id", "etat", "heure_creation", "priorite", "type_ticket")
    def _compute_position(self):
        mode = self._get_mode_priorite()

        for rec in self:
            if rec.etat != "en_attente" or not rec.queue_id:
                rec.position = 0
                continue

            base_domain = [
                ("queue_id", "=", rec.queue_id.id),
                ("etat",     "=", "en_attente"),
            ]

            if mode == "virtuel_first":
                if rec.type_ticket == "virtuel":
                    rec.position = self.search_count(base_domain + [
                        ("type_ticket",    "=", "virtuel"),
                        ("heure_creation", "<", rec.heure_creation),
                    ]) + 1
                else:
                    nb_virtuels = self.search_count(base_domain + [
                        ("type_ticket", "=", "virtuel"),
                    ])
                    nb_physiques_avant = self.search_count(base_domain + [
                        ("type_ticket",    "=", "physique"),
                        ("heure_creation", "<", rec.heure_creation),
                    ])
                    rec.position = nb_virtuels + nb_physiques_avant + 1

            else:
                # mode == "mix" : FIFO pur, type_ticket ignoré.
                rec.position = self.search_count(base_domain + [
                    ("heure_creation", "<", rec.heure_creation),
                ]) + 1

    # ── Create ────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        mode = self.env["ir.config_parameter"].sudo().get_param(
            "service_pharmacie.mode_priorite", default="mix"
        )

        for vals in vals_list:
            queue = self.env["pharmacy.queue"].browse(vals.get("queue_id"))
            if not queue.exists():
                raise ValidationError(_("File d'attente introuvable."))

            if not vals.get("name") or vals["name"] == "Nouveau":
                seq = self.search_count([("queue_id", "=", queue.id)]) + 1
                vals["name"] = f"{queue.name}-{seq:03d}"

            # Calcul de la priorité individuelle au moment de la création
            type_ticket = vals.get("type_ticket", "physique")
            if mode == "virtuel_first" and type_ticket == "virtuel":
                vals["priorite"] = 2   # passe avant les physiques
            else:
                vals["priorite"] = 1   # ordre normal

        return super().create(vals_list)


    def action_appeler(self):
        self.write({"etat": "appele", "heure_appel": fields.Datetime.now()})

    def action_terminer(self):
        self.write({"etat": "termine", "heure_fin": fields.Datetime.now()})

    def action_annuler(self):
        self.write({"etat": "annule", "heure_fin": fields.Datetime.now()})
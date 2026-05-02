# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ticket_public_enabled = fields.Boolean(
        string="Activer l'interface ticket publique",
        config_parameter="service_pharmacie.ticket_public_enabled",
    )

    ticket_public_password = fields.Char(
        string="Mot de passe interface ticket",
        config_parameter="service_pharmacie.ticket_public_password",
    )

    ticket_password_show = fields.Boolean(
        string="Afficher le mot de passe",
        default=False,
        store=False,
    )

    mode_priorite = fields.Selection(
        [
            ("virtuel_first", "Virtuel en priorité"),
            ("mix",           "Gestion équilibrée (mix — FIFO)"),
        ],
        string="Mode de priorité de la file",
        default="mix",
        config_parameter="service_pharmacie.mode_priorite",
        help=(
            "Définit le comportement global de la file d'attente :\n"
            "- Virtuel en priorité : les clients ayant réservé en ligne passent avant les tickets physiques.\n"
            "- Mix : ordre d'arrivée pur (FIFO), quel que soit le canal."
        ),
    )

    # ── Localisation ──────────────────────────────────────────────────────────

    localization_id = fields.Many2one(
        "pharmacy.localization",
        string="Localisation",
        compute="_compute_localization_id",
    )

    localization_nom             = fields.Char(related="localization_id.nom",                string="Nom de la pharmacie", readonly=True)
    localization_adresse         = fields.Char(related="localization_id.pharmacie_adresse",  string="Adresse",             readonly=True)
    localization_lat             = fields.Float(related="localization_id.pharmacie_lat",     string="Latitude",            readonly=True)
    localization_lon             = fields.Float(related="localization_id.pharmacie_lon",     string="Longitude",           readonly=True)
    localization_rayon           = fields.Integer(related="localization_id.rayon_validation",string="Rayon GPS (m)",       readonly=True)
    localization_maps_url        = fields.Char(related="localization_id.maps_url",           string="Google Maps",         readonly=True)
    localization_nb_reservations = fields.Integer(related="localization_id.nb_reservations", string="Nb réservations",     readonly=True)

    def _compute_localization_id(self):
        loc = self.env["pharmacy.localization"].get_singleton()
        for rec in self:
            rec.localization_id = loc or False
    mode_estimation = fields.Selection(
        [
            ("manuel", "Manuel"),
            ("intelligent", "Intelligent"),
        ],
        string="Mode d'estimation",
        config_parameter="service_pharmacie.mode_estimation",
        default="manuel",
    )

    service_min_records = fields.Integer(
        string="Seuil minimum tickets service",
        config_parameter="service_pharmacie.service_min_records",
        default=5,
    )

    assistant_min_records = fields.Integer(
        string="Seuil minimum tickets assistant",
        config_parameter="service_pharmacie.assistant_min_records",
        default=15,
    )
    rf_retraining_enabled = fields.Boolean(
    string="Activer le réentraînement automatique",
    config_parameter="service_pharmacie.rf_retraining_enabled",
    default=True,
    )

    rf_retraining_days = fields.Integer(
        string="Période des données d'entraînement (jours)",
        config_parameter="service_pharmacie.rf_retraining_days",
        default=60,
    )

    rf_retraining_min_records = fields.Integer(
        string="Minimum tickets pour réentraînement",
        config_parameter="service_pharmacie.rf_retraining_min_records",
        default=100,
    )
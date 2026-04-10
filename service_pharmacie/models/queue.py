# -*- coding: utf-8 -*-
from math import ceil
import logging
from odoo import api, models, fields
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PharmacyQueue(models.Model):
    _name = "pharmacy.queue"
    _description = "File d'attente pharmacie"
    _rec_name = "display_name"

    name = fields.Char(string="Nom", required=True)
    active = fields.Boolean(string="Active", default=True)

    position_client_virtuel = fields.Integer(
        string="Position client virtuel",
        default=2,
        help=(
            "Position d'insertion du client virtuel dans la file "
            "lorsqu'il confirme sa présence."
        ),
    )

    service_id = fields.Many2one(
        "pharmacy.service",
        string="Service",
        required=False,
        ondelete="set null",
    )

    ticket_ids = fields.One2many("pharmacy.ticket", "queue_id", string="Tickets")
    rattachement_ids = fields.One2many("pharmacy.rattachement", "file_id", string="Rattachements")

    display_name = fields.Char(compute="_compute_display_name", store=True)

    nb_en_attente = fields.Integer(string="En attente", compute="_compute_stats")
    temps_attente_estime = fields.Integer(string="Attente estimée (min)", compute="_compute_stats")
    nb_rattachements_actifs = fields.Integer(string="Nb rattachements actifs", compute="_compute_stats")

    methode_estimation = fields.Char(
        string="Méthode estimation",
        compute="_compute_stats",
    )
    detail_estimation = fields.Char(
        string="Détail estimation",
        compute="_compute_stats",
    )

    @api.depends("name", "service_id.nom")
    def _compute_display_name(self):
        for rec in self:
            service = rec.service_id.nom or ""
            rec.display_name = f"{service} – {rec.name}" if service else rec.name

    def _get_mode_estimation(self):
        return self.env["ir.config_parameter"].sudo().get_param(
            "service_pharmacie.mode_estimation",
            default="manuel",
        )

    def _get_service_min_records(self):
        value = self.env["ir.config_parameter"].sudo().get_param(
            "service_pharmacie.service_min_records",
            default="5",
        )
        return int(value)

    def _get_assistant_min_records(self):
        value = self.env["ir.config_parameter"].sudo().get_param(
            "service_pharmacie.assistant_min_records",
            default="15",
        )
        return int(value)

    @api.depends(
        "ticket_ids.etat",
        "service_id",
        "service_id.dure_estimee_par_defaut",
        "rattachement_ids.active",
    )
    def _compute_stats(self):
        history_model = self.env["pharmacy.queue.history"]

        mode_estimation = self._get_mode_estimation()
        service_min_records = self._get_service_min_records()
        assistant_min_records = self._get_assistant_min_records()

        for rec in self:
            en_attente = rec.ticket_ids.filtered(lambda t: t.etat == "en_attente")
            rec.nb_en_attente = len(en_attente)

            rattachements_actifs = rec.rattachement_ids.filtered(lambda r: r.active)
            rec.nb_rattachements_actifs = len(rattachements_actifs)

            if not rec.service_id or rec.nb_en_attente <= 0:
                rec.temps_attente_estime = 0
                rec.methode_estimation = "-"
                rec.detail_estimation = "-"
                _logger.info(
                    "QUEUE ESTIMATION | queue=%s | service=%s | waiting=%s | active_ratt=%s | mode=%s | method=%s | detail=%s | estimated=%s",
                    rec.display_name or rec.name,
                    rec.service_id.id if rec.service_id else False,
                    rec.nb_en_attente,
                    rec.nb_rattachements_actifs,
                    mode_estimation,
                    rec.methode_estimation,
                    rec.detail_estimation,
                    rec.temps_attente_estime,
                )
                continue

            default_duration = rec.service_id.dure_estimee_par_defaut or 15.0

            if mode_estimation == "manuel":
                duree_unitaire = default_duration
                rec.methode_estimation = "manuel"
                rec.detail_estimation = "Durée par défaut"

            else:
                assistant_ids = rattachements_actifs.mapped("assistant_id").ids
                durations = []
                methods = []
                details = []

                for assistant_id in assistant_ids:
                    info = history_model.get_intelligent_unit_duration_info(
                        service_id=rec.service_id.id,
                        assistant_id=assistant_id,
                        default_duration=default_duration,
                        service_min_records=service_min_records,
                        assistant_min_records=assistant_min_records,
                    )
                    durations.append(info["duration"])
                    methods.append(f"A{assistant_id}:{info['method']}")
                    details.append(f"A{assistant_id}:{info['detail']}")

                if durations:
                    duree_unitaire = sum(durations) / len(durations)
                    rec.methode_estimation = "multi_assistant"
                    rec.detail_estimation = " | ".join(methods)
                else:
                    info = history_model.get_intelligent_unit_duration_info(
                        service_id=rec.service_id.id,
                        assistant_id=False,
                        default_duration=default_duration,
                        service_min_records=service_min_records,
                        assistant_min_records=assistant_min_records,
                    )
                    duree_unitaire = info["duration"]
                    rec.methode_estimation = info["method"]
                    rec.detail_estimation = info["detail"]

            diviseur = rec.nb_rattachements_actifs if rec.nb_rattachements_actifs > 0 else 1
            rec.temps_attente_estime = ceil(
                (rec.nb_en_attente * duree_unitaire) / diviseur
            )

            _logger.info(
                "QUEUE ESTIMATION | queue=%s | service=%s | waiting=%s | active_ratt=%s | mode=%s | unit=%.2f | method=%s | detail=%s | estimated=%s",
                rec.display_name or rec.name,
                rec.service_id.id if rec.service_id else False,
                rec.nb_en_attente,
                rec.nb_rattachements_actifs,
                mode_estimation,
                duree_unitaire,
                rec.methode_estimation,
                rec.detail_estimation,
                rec.temps_attente_estime,
            )

    @api.constrains("position_client_virtuel")
    def _check_position_client_virtuel(self):
        for rec in self:
            if rec.position_client_virtuel < 1:
                raise ValidationError(
                    "La position du client virtuel doit être supérieure ou égale à 1."
                )
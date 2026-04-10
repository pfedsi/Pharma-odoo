from odoo import api, fields, models
from datetime import timedelta
import logging
_logger = logging.getLogger(__name__)

class PharmacyQueueHistory(models.Model):
    _name = "pharmacy.queue.history"
    _description = "Historique des rattachements et traitements"
    _rec_name = "display_name"
    _order = "date_debut desc"

    display_name = fields.Char(
        string="Libellé",
        compute="_compute_display_name",
        store=True,
    )

    rattachement_id = fields.Many2one(
        "pharmacy.rattachement",
        string="Rattachement source",
        ondelete="set null",
    )

    assistant_id = fields.Many2one(
        "res.users",
        string="Assistant",
        required=True,
    )

    file_id = fields.Many2one(
        "pharmacy.queue",
        string="File",
        required=True,
    )

    service_id = fields.Many2one(
        "pharmacy.service",
        string="Service",
        ondelete="set null",
    )

    mode_rattachement = fields.Selection(
        [
            ("manuel", "Manuel"),
            ("auto_attente", "Automatique (temps d'attente)"),
            ("prioritaire", "Prioritaire"),
        ],
        string="Mode",
    )

    poste_number = fields.Char(string="Numéro de poste")

    date_debut = fields.Datetime(string="Début rattachement", required=True)
    date_fin = fields.Datetime(string="Fin rattachement", required=True)

    ticket_id = fields.Many2one(
        "pharmacy.ticket",
        string="Ticket traité",
        ondelete="set null",
    )

    date_debut_traitement = fields.Datetime(string="Début traitement")
    date_fin_traitement = fields.Datetime(string="Fin traitement")

    duree_rattachement_min = fields.Float(
        string="Durée rattachement (min)",
        compute="_compute_durations",
        store=True,
    )

    duree_traitement_min = fields.Float(
        string="Durée traitement (min)",
        compute="_compute_durations",
        store=True,
    )

    @api.depends("assistant_id", "file_id", "ticket_id")
    def _compute_display_name(self):
        for rec in self:
            assistant = rec.assistant_id.name or ""
            queue = rec.file_id.display_name or ""
            ticket = rec.ticket_id.name or "Sans ticket"
            rec.display_name = f"{assistant} - {queue} - {ticket}"

    @api.depends("date_debut", "date_fin", "date_debut_traitement", "date_fin_traitement")
    def _compute_durations(self):
        for rec in self:
            rec.duree_rattachement_min = 0.0
            rec.duree_traitement_min = 0.0

            if rec.date_debut and rec.date_fin:
                rec.duree_rattachement_min = (
                    (rec.date_fin - rec.date_debut).total_seconds() / 60.0
                )

            if rec.date_debut_traitement and rec.date_fin_traitement:
                rec.duree_traitement_min = (
                    (rec.date_fin_traitement - rec.date_debut_traitement).total_seconds() / 60.0
                )

    def _get_recency_weight(self, now, end_datetime):
        age_days = (now - end_datetime).days

        if age_days <= 7:
            return 3
        elif age_days <= 14:
            return 2
        else:
            return 1

    @api.model
    def get_weighted_service_duration(self, service_id, days=30, min_records=5):
        if not service_id:
            return 0.0

        now = fields.Datetime.now()
        date_limit = now - timedelta(days=days)

        records = self.search([
            ("service_id", "=", service_id),
            ("ticket_id", "!=", False),

            ("date_debut_traitement", "!=", False),
            ("date_fin_traitement", "!=", False),
            ("date_fin_traitement", ">=", date_limit),
        ])

        if len(records) < min_records:
            return 0.0

        total_weighted_duration = 0.0
        total_weight = 0.0

        for rec in records:
            duration_min = (
                rec.date_fin_traitement - rec.date_debut_traitement
            ).total_seconds() / 60.0
            if duration_min < 1 or duration_min > 60:
                continue
            weight = self._get_recency_weight(now, rec.date_fin_traitement)

            total_weighted_duration += duration_min * weight
            total_weight += weight

        if not total_weight:
            return 0.0

        return total_weighted_duration / total_weight

    @api.model
    def get_weighted_assistant_duration(self, assistant_id, service_id, days=30, min_records=5):
        if not assistant_id or not service_id:
            return 0.0

        now = fields.Datetime.now()
        date_limit = now - timedelta(days=days)

        records = self.search([
            ("assistant_id", "=", assistant_id),
            ("service_id", "=", service_id),
            ("ticket_id", "!=", False),

            ("date_debut_traitement", "!=", False),
            ("date_fin_traitement", "!=", False),
            ("date_fin_traitement", ">=", date_limit),
        ])

        if len(records) < min_records:
            return 0.0

        total_weighted_duration = 0.0
        total_weight = 0.0

        for rec in records:
            duration_min = (
                rec.date_fin_traitement - rec.date_debut_traitement
            ).total_seconds() / 60.0
            if duration_min < 1 or duration_min > 60:
                continue
            weight = self._get_recency_weight(now, rec.date_fin_traitement)

            total_weighted_duration += duration_min * weight
            total_weight += weight

        if not total_weight:
            return 0.0

        return total_weighted_duration / total_weight

    @api.model
    def get_assistant_factor(self, assistant_id, service_id, days=30, min_records=5):
        service_duration = self.get_weighted_service_duration(
            service_id,
            days=days,
            min_records=min_records,
        )
        if not service_duration:
            return 1.0

        assistant_duration = self.get_weighted_assistant_duration(
            assistant_id,
            service_id,
            days=days,
            min_records=min_records,
        )
        if not assistant_duration:
            return 1.0

        raw_factor = assistant_duration / service_duration
        if raw_factor < 0.9:
            factor = 0.8
        elif raw_factor <= 1.1:
            factor = 1.0
        else:
            factor = 1.2

        _logger.info(
            "FACTOR assistant=%s service=%s raw=%s final=%s",
            assistant_id,
            service_id,
            round(raw_factor, 2),
            factor
        )

        return factor
    @api.model
    def _clamp_duration(self, value, min_value, max_value):
        return max(min_value, min(max_value, value))


    @api.model
    def _compute_time_factor(self, dt_value=None):
        dt_value = dt_value or fields.Datetime.now()
        factor = 1.0

        weekday = dt_value.weekday()
        hour = dt_value.hour
        month = dt_value.month

        if weekday >= 5:
            factor *= 1.05

        if 8 <= hour <= 10:
            factor *= 1.10
        elif 18 <= hour <= 21:
            factor *= 1.08
        elif 0 <= hour <= 6:
            factor *= 1.07

        if month in [12, 1]:
            factor *= 1.03

        return factor


    @api.model
    def _compute_assistant_count_factor(self, nb_assistants):
        if not nb_assistants or nb_assistants <= 1:
            return 1.0
        elif nb_assistants == 2:
            return 0.97
        return 0.94


    @api.model
    def _get_active_assistant_count_for_service(self, service_id, days=30):
        date_limit = fields.Datetime.now() - timedelta(days=days)
        records = self.search([
            ("service_id", "=", service_id),
            ("ticket_id", "!=", False),
            ("date_debut_traitement", "!=", False),
            ("date_fin_traitement", "!=", False),
            ("date_fin_traitement", ">=", date_limit),
        ])
        return len(records.mapped("assistant_id"))


    @api.model
    def get_intelligent_unit_duration_info(
        self,
        service_id,
        assistant_id=False,
        default_duration=15.0,
        file_id=False,
        mode_rattachement="manuel",
        poste_number="P1",
        service_min_records=5,
        assistant_min_records=5,
    ):
        if not service_id:
            return {
                "duration": default_duration or 15.0,
                "method": "default_no_service",
                "detail": "Aucun service fourni, durée par défaut utilisée.",
            }

        service = self.env["pharmacy.service"].browse(service_id)
        if service.exists() and service.dure_estimee_par_defaut:
            default_duration = float(service.dure_estimee_par_defaut or 15.0)

        if not file_id and service.queue_id:
            file_id = service.queue_id.id

        service_records = self.search_count([
            ("service_id", "=", service_id),
            ("ticket_id", "!=", False),
            ("date_debut_traitement", "!=", False),
            ("date_fin_traitement", "!=", False),
        ])

        if service_records < service_min_records:
            detail_text = (
                f"Historique service insuffisant "
                f"({service_records} ticket(s) < seuil {service_min_records})."
            )
            _logger.info(
                "ESTIMATION service=%s assistant=%s duration=%s method=%s detail=%s",
                service_id,
                assistant_id or False,
                round(default_duration, 2),
                "default_service_insufficient",
                detail_text,
            )
            return {
                "duration": default_duration,
                "method": "default_service_insufficient",
                "detail": detail_text,
            }

        service_duration = self.get_weighted_service_duration(
            service_id,
            days=30,
            min_records=service_min_records,
        )

        if not service_duration:
            detail_text = "Impossible de calculer la moyenne pondérée du service."
            _logger.info(
                "ESTIMATION service=%s assistant=%s duration=%s method=%s detail=%s",
                service_id,
                assistant_id or False,
                round(default_duration, 2),
                "default_service_no_avg",
                detail_text,
            )
            return {
                "duration": default_duration,
                "method": "default_service_no_avg",
                "detail": detail_text,
            }

        confidence_service = min(1.0, service_records / 30.0)
        base_service = ((1.0 - confidence_service) * default_duration) + (confidence_service * service_duration)

        assistant_records = 0
        assistant_duration = 0.0
        facteur_assistant = 1.0

        if assistant_id:
            assistant_records = self.search_count([
                ("assistant_id", "=", assistant_id),
                ("service_id", "=", service_id),
                ("ticket_id", "!=", False),
                ("date_debut_traitement", "!=", False),
                ("date_fin_traitement", "!=", False),
            ])

            assistant_duration = self.get_weighted_assistant_duration(
                assistant_id,
                service_id,
                days=30,
                min_records=assistant_min_records,
            )

            if assistant_records >= assistant_min_records and assistant_duration and service_duration:
                raw_factor = assistant_duration / service_duration
                facteur_assistant = self._clamp_duration(raw_factor, 0.75, 1.25)

        facteur_temps = self._compute_time_factor()
        nb_assistants = self._get_active_assistant_count_for_service(service_id, days=30)
        facteur_nb_assistants = self._compute_assistant_count_factor(nb_assistants)

        estimation_metier = (
            base_service
            * facteur_assistant
            * facteur_temps
            * facteur_nb_assistants
        )

        rf_pred = self.env["pharmacy.rf.predictor"].predict_duration(
            service_id=service_id,
            assistant_id=assistant_id,
            file_id=file_id,
            mode_rattachement=mode_rattachement,
            poste_number=poste_number,
            duree_defaut=default_duration,
        )

        if rf_pred is not None:
            rf_pred = self._clamp_duration(
                rf_pred,
                estimation_metier * 0.70,
                estimation_metier * 1.30,
            )
            final_duration = (0.6 * estimation_metier) + (0.4 * rf_pred)
            method = "hybrid_business_plus_rf"
        else:
            final_duration = estimation_metier
            method = "business_only"

        min_safe = max(1.0, default_duration * 0.5)
        max_safe = max(min_safe, default_duration * 1.8)
        final_duration = self._clamp_duration(final_duration, min_safe, max_safe)

        detail_text = (
            f"default={round(default_duration,2)}, "
            f"service_avg={round(service_duration,2)}, "
            f"assistant_factor={round(facteur_assistant,3)}, "
            f"time_factor={round(facteur_temps,3)}, "
            f"assistant_count_factor={round(facteur_nb_assistants,3)}, "
            f"rf={round(rf_pred,2) if rf_pred is not None else 'None'}"
        )

        _logger.info(
            "ESTIMATION service=%s assistant=%s duration=%s method=%s detail=%s",
            service_id,
            assistant_id or False,
            round(final_duration, 2),
            method,
            detail_text,
        )

        return {
            "duration": round(final_duration, 2),
            "method": method,
            "detail": detail_text,
        }
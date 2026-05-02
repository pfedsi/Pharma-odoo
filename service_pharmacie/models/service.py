# -*- coding: utf-8 -*-
import datetime
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError
import pytz

class PharmacyService(models.Model):
    _name = "pharmacy.service"
    _description = "Service pharmacie"
    _rec_name = "nom"
    _order = "nom asc"

    nom = fields.Char(string="Nom", required=True)
    description = fields.Text(string="Description")
    dure_estimee_par_defaut = fields.Integer(
        string="Durée estimée (min)", default=15, required=True
    )
    active = fields.Boolean(default=True)

    heure_ouverture = fields.Float(
        string="Heure d'ouverture",
        default=8.0,
        required=True,
        help="Pour une pharmacie de nuit, saisissez ex : 22.0 (22h00).",
    )
    heure_fermeture = fields.Float(
        string="Heure de fermeture",
        default=18.0,
        required=True,
        help=(
            "Pour une pharmacie de nuit qui ferme après minuit, "
            "saisissez ex : 6.0 (06h00 du lendemain)."
        ),
    )

    multiplicateur_creneau = fields.Selection(
        [
            ('2',  'pas 0'),
            ('3',  'pas 1'),
            ('4',  'pas 2'),
            ('5',  'pas 3'),
            ('6',  'pas 4'),
            ('7',  'pas 5'),
            ('8',  'pas 6'),
            ('9',  'pas 7'),
            ('10', 'pas 8'),
        ],
        string="Durée de réservation",
        default='2',
        required=True,
        help="Multiplicateur appliqué à la durée estimée pour définir l'intervalle entre réservations.",
    )

    duree_creneau = fields.Integer(
        string="Intervalle entre réservations (min)",
        compute="_compute_duree_creneau",
        store=True,
        readonly=True,
    )

    warning_creneau = fields.Boolean(
        string="Avertissement encombrement",
        compute="_compute_warning_creneau",
        store=True,
    )
    warning_creneau_message = fields.Char(
        string="Message avertissement encombrement",
        compute="_compute_warning_creneau",
        store=True,
    )

    queue_id = fields.Many2one(
        "pharmacy.queue",
        string="File d'attente",
        readonly=True,
        copy=False,
        ondelete="set null",
    )

    overnight = fields.Boolean(
        string="Pharmacie de nuit",
        compute="_compute_overnight",
        store=True,
    )

    horaire_ids = fields.One2many(
        "pharmacy.service.horaire",
        "service_id",
        string="Horaires par jour",
    )

    warning_estimation = fields.Boolean(
        string="Alerte estimation",
        compute="_compute_estimation_warning",
        store=True,                              # ← ajout
    )

    warning_estimation_message = fields.Char(
        string="Message alerte estimation",
        compute="_compute_estimation_warning",
        store=True,                              # ← ajout
    )

    moyenne_reelle_observee = fields.Float(
        string="Moyenne réelle observée",
        compute="_compute_estimation_warning",
        store=True,                              # ← ajout
    )

    type_affichage = fields.Selection(
        [
            ("physique", "Physique"),
            ("virtuel", "Virtuel"),
            ("les_deux", "Les deux"),
        ],
        string="Type d'affichage",
        default="physique",
        required=True,
        help="Indique si ce service est disponible en présentiel, à distance, ou les deux.",
    )

    # ── Compute ───────────────────────────────────────────────────────────────

    @api.depends("heure_ouverture", "heure_fermeture")
    def _compute_overnight(self):
        for rec in self:
            rec.overnight = (
                rec.heure_ouverture is not False
                and rec.heure_fermeture is not False
                and rec.heure_fermeture <= rec.heure_ouverture
            )

    @api.depends("dure_estimee_par_defaut", "multiplicateur_creneau")
    def _compute_duree_creneau(self):
        for rec in self:
            mult = int(rec.multiplicateur_creneau or '2')
            rec.duree_creneau = max(rec.dure_estimee_par_defaut * mult, 1)

    @api.depends("multiplicateur_creneau")
    def _compute_warning_creneau(self):
        for rec in self:
            mult = int(rec.multiplicateur_creneau or '2')
            if mult == 2:
                rec.warning_creneau = True
                rec.warning_creneau_message = (
                    "L'intervalle entre réservations est au minimum (durée estimée × 2). "
                    "En cas de forte affluence, un encombrement de la file d'attente est probable. "
                    "Envisagez d'augmenter le multiplicateur."
                )
            else:
                rec.warning_creneau = False
                rec.warning_creneau_message = False

    # ── Contraintes ───────────────────────────────────────────────────────────

    @api.constrains("heure_ouverture", "heure_fermeture")
    def _check_horaires(self):
        for rec in self:
            if rec.heure_ouverture == rec.heure_fermeture:
                raise ValidationError(
                    _(
                        "L'heure d'ouverture et l'heure de fermeture "
                        "ne peuvent pas être identiques."
                    )
                )

    @api.constrains("duree_creneau")
    def _check_duree_creneau(self):
        for rec in self:
            if rec.duree_creneau <= 0:
                raise ValidationError(_("La durée du créneau doit être positive."))

    # ── ORM hooks ─────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if not record.queue_id:
                record._ensure_queue()
        return records

    def write(self, vals):
        result = super().write(vals)

        for record in self:
            if "heure_ouverture" in vals or "heure_fermeture" in vals:
                record.horaire_ids.write({
                    "heure_ouverture": record.heure_ouverture,
                    "heure_fermeture": record.heure_fermeture,
                })

            if record.queue_id:
                queue_vals = {}
                if "nom" in vals:
                    queue_vals["name"] = f"File – {record.nom}"
                if "active" in vals:
                    queue_vals["active"] = record.active

                if queue_vals:
                    record.queue_id.sudo().with_context(no_recompute=True).write(queue_vals)

        return result

    def unlink(self):
        queues_to_delete = self.env["pharmacy.queue"]

        for record in self:
            reservations_actives = self.env["pharmacy.reservation"].search_count([
                ("service_id", "=", record.id),
                ("statut", "not in", ["annule"]),
            ])

            if reservations_actives:
                raise ValidationError(
                    _(
                        "Impossible de supprimer le service '%s' : "
                        "%d réservation(s) active(s) existent. "
                        "Annulez-les d'abord ou archivez le service."
                    ) % (record.nom, reservations_actives)
                )

            if record.queue_id:
                queues_to_delete |= record.queue_id.sudo()

        result = super().unlink()

        if queues_to_delete:
            queues_to_delete.exists().unlink()

        return result

    # ── Méthodes ──────────────────────────────────────────────────────────────

    def _ensure_queue(self):
        self.ensure_one()

        if self.queue_id:
            return self.queue_id

        queue = self.env["pharmacy.queue"].sudo().create({
            "name": f"File – {self.nom}",
            "service_id": self.id,
            "active": self.active,
        })
        self.sudo().write({"queue_id": queue.id})
        return queue

    def _get_horaire_du_jour(self, date: datetime.date):
        self.ensure_one()
        jour_index = str(date.weekday())

        horaire = self.horaire_ids.filtered(
            lambda h: h.jour_semaine == jour_index and h.actif
        )

        if horaire:
            return horaire[0].heure_ouverture, horaire[0].heure_fermeture

        return self.heure_ouverture, self.heure_fermeture

    def compute_slots(self, date: datetime.date) -> list:
        self.ensure_one()

        h_ouv, h_fer = self._get_horaire_du_jour(date)

        if h_ouv == h_fer:
            return []

        system_tz = (
            self.env["ir.config_parameter"].sudo().get_param("your_module.timezone")
            or self.env.context.get("tz")
            or self.env.user.tz
            or "Africa/Tunis"
        )
        try:
            local_tz = pytz.timezone(system_tz)
        except pytz.UnknownTimeZoneError:
            local_tz = pytz.timezone("Africa/Tunis")

        is_overnight = h_fer < h_ouv
        slots = []

        start_minutes = int(round(h_ouv * 60))
        end_minutes = int(round((h_fer + 24.0) * 60)) if is_overnight else int(round(h_fer * 60))
        step_minutes = max(int(self.duree_creneau or 0), 1)

        cursor_minutes = start_minutes

        while cursor_minutes < end_minutes:
            actual_total_minutes = cursor_minutes
            actual_minutes_in_day = actual_total_minutes if actual_total_minutes < 24 * 60 else actual_total_minutes - 24 * 60

            h = (actual_minutes_in_day // 60) % 24
            m = actual_minutes_in_day % 60

            slot_date = date if actual_total_minutes < 24 * 60 else date + datetime.timedelta(days=1)
            slot_dt_local = datetime.datetime.combine(slot_date, datetime.time(h, m))
            slot_dt_utc = local_tz.localize(slot_dt_local).astimezone(pytz.utc).replace(tzinfo=None)

            booked = self.env["pharmacy.reservation"].search_count([
                ("service_id", "=", self.id),
                ("date_heure_reservation", "=", slot_dt_utc),
                ("statut", "not in", ["annule"]),
            ])

            slots.append({
                "time": f"{h:02d}:{m:02d}",
                "datetime": slot_dt_local.isoformat(),
                "available": booked == 0,
            })

            cursor_minutes += step_minutes

        return slots
    @api.depends("dure_estimee_par_defaut")
    def _compute_estimation_warning(self):
        history_model = self.env["pharmacy.queue.history"]

        min_records = 10
        threshold = 0.20  # 20%

        for rec in self:
            rec.warning_estimation = False
            rec.warning_estimation_message = False
            rec.moyenne_reelle_observee = 0.0

            if not rec.id or not rec.dure_estimee_par_defaut:
                continue

            record_count = history_model.search_count([
                ("service_id", "=", rec.id),
                ("ticket_id", "!=", False),
                ("date_debut_traitement", "!=", False),
                ("date_fin_traitement", "!=", False),
            ])

            if record_count < min_records:
                continue

            moyenne_reelle = history_model.get_weighted_service_duration(
                rec.id,
                days=30,
                min_records=min_records,
            )

            if not moyenne_reelle:
                continue

            rec.moyenne_reelle_observee = moyenne_reelle

            duree_saisie = rec.dure_estimee_par_defaut
            ecart_ratio = (moyenne_reelle - duree_saisie) / duree_saisie

            if abs(ecart_ratio) >= threshold:
                rec.warning_estimation = True

                if ecart_ratio > 0:
                    rec.warning_estimation_message = (
                        f"La durée moyenne réelle observée ({moyenne_reelle:.1f} min) "
                        f"est supérieure à la durée estimée configurée ({duree_saisie:.1f} min). "
                        f"Pensez à réviser cette valeur."
                    )
                else:
                    rec.warning_estimation_message = (
                        f"La durée moyenne réelle observée ({moyenne_reelle:.1f} min) "
                        f"est inférieure à la durée estimée configurée ({duree_saisie:.1f} min). "
                        f"Vous pouvez ajuster cette valeur pour améliorer la précision."
                    )


# ─────────────────────────────────────────────────────────────────────────────


class PharmacyServiceHoraire(models.Model):
    _name = "pharmacy.service.horaire"
    _description = "Horaire journalier d'un service pharmacie"
    _order = "jour_semaine asc"

    service_id = fields.Many2one(
        "pharmacy.service",
        string="Service",
        required=True,
        ondelete="cascade",
    )

    jour_semaine = fields.Selection(
        [
            ("0", "Lundi"),
            ("1", "Mardi"),
            ("2", "Mercredi"),
            ("3", "Jeudi"),
            ("4", "Vendredi"),
            ("5", "Samedi"),
            ("6", "Dimanche"),
        ],
        string="Jour",
        required=True,
    )

    actif = fields.Boolean(string="Ouvert ce jour", default=False)
    heure_ouverture = fields.Float(string="De", required=True)
    heure_fermeture = fields.Float(string="À", required=True)

    overnight = fields.Boolean(
        string="Traverse minuit",
        compute="_compute_overnight",
        store=True,
    )

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        service_id = self.env.context.get("default_service_id")

        if service_id:
            service = self.env["pharmacy.service"].browse(service_id)
            if service.exists():
                if "heure_ouverture" in fields_list:
                    defaults["heure_ouverture"] = service.heure_ouverture
                if "heure_fermeture" in fields_list:
                    defaults["heure_fermeture"] = service.heure_fermeture
        else:
            defaults.setdefault("heure_ouverture", 8.0)
            defaults.setdefault("heure_fermeture", 18.0)

        return defaults

    @api.onchange("service_id")
    def _onchange_service_id(self):
        if self.service_id:
            self.heure_ouverture = self.service_id.heure_ouverture
            self.heure_fermeture = self.service_id.heure_fermeture

    @api.depends("heure_ouverture", "heure_fermeture", "actif")
    def _compute_overnight(self):
        for rec in self:
            rec.overnight = (
                rec.actif
                and rec.heure_ouverture is not False
                and rec.heure_fermeture is not False
                and rec.heure_fermeture < rec.heure_ouverture
            )

    @api.constrains("heure_ouverture", "heure_fermeture", "actif")
    def _check_horaires(self):
        for rec in self:
            if rec.actif and rec.heure_ouverture == rec.heure_fermeture:
                raise ValidationError(
                    _(
                        "L'heure d'ouverture et l'heure de fermeture ne peuvent pas "
                        "être identiques (%s)."
                    ) % dict(rec._fields["jour_semaine"].selection)[rec.jour_semaine]
                )

    @api.constrains("service_id", "jour_semaine")
    def _check_unicite_jour(self):
        for rec in self:
            doublon = self.search([
                ("id", "!=", rec.id),
                ("service_id", "=", rec.service_id.id),
                ("jour_semaine", "=", rec.jour_semaine),
            ])
            if doublon:
                raise ValidationError(
                    _("Un horaire existe déjà pour ce jour dans le service '%s'.")
                    % rec.service_id.nom
                )
# -*- coding: utf-8 -*-
"""MODEL — pharmacy.reservation"""
import math
import datetime
import pytz
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class PharmacyReservation(models.Model):
    _name = "pharmacy.reservation"
    _description = "Réservation pharmacie"
    _rec_name = "display_name"
    _order = "date_heure_reservation asc"
    _inherit = ["mail.thread"]

    display_name = fields.Char(compute="_compute_display_name", store=True)

    user_id = fields.Many2one(
        "res.users", string="Client",
        required=True, ondelete="cascade",
        domain=[("user_role", "=", "client")],
    )
    service_id = fields.Many2one(
        "pharmacy.service", string="Service",
        required=True, ondelete="restrict",
    )
    queue_id = fields.Many2one(
        "pharmacy.queue",
        related="service_id.queue_id",
        store=True, readonly=True,
    )

    localisation_id = fields.Many2one(
        "pharmacy.localization",
        string="Localisation",
        ondelete="set null",
        index=True,
    )

    pharmacie_lat    = fields.Float(digits=(10, 7), default=36.8065)
    pharmacie_lon    = fields.Float(digits=(10, 7), default=10.1815)
    rayon_validation = fields.Integer(string="Rayon GPS (m)", default=200)

    date_heure_reservation = fields.Datetime(
        string="Créneau réservé", required=True,
    )
    statut = fields.Selection(
        [("en_attente", "En attente"), ("arrive", "Arrivé – ticket attribué"), ("annule", "Annulé")],
        default="en_attente", required=True, tracking=True,
    )
    ticket_id = fields.Many2one("pharmacy.ticket", readonly=True, copy=False)
    notes = fields.Text()

    # ── Computed ──────────────────────────────────────────────────────────────

    @api.depends("user_id.name", "service_id.nom", "date_heure_reservation")
    def _compute_display_name(self):
        for rec in self:
            user    = rec.user_id.name or "Client"
            service = rec.service_id.nom or "Service"
            date    = rec.date_heure_reservation.strftime("%d/%m %H:%M") if rec.date_heure_reservation else ""
            rec.display_name = f"{user} – {service} ({date})"

    # ── ORM hooks ─────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        loc = self.env["pharmacy.localization"].get_singleton()
        for vals in vals_list:
            if loc and not vals.get("localisation_id"):
                vals["localisation_id"] = loc.id
            if loc:
                vals.setdefault("pharmacie_lat",    loc.pharmacie_lat)
                vals.setdefault("pharmacie_lon",    loc.pharmacie_lon)
                vals.setdefault("rayon_validation", loc.rayon_validation)
        return super().create(vals_list)

    # ── Contraintes ───────────────────────────────────────────────────────────

    @api.constrains("date_heure_reservation", "service_id")
    def _check_creneau_disponible(self):
        for rec in self:
            if not rec.date_heure_reservation or not rec.service_id:
                continue
            conflit = self.search([
                ("id", "!=", rec.id),
                ("service_id", "=", rec.service_id.id),
                ("date_heure_reservation", "=", rec.date_heure_reservation),
                ("statut", "not in", ["annule"]),
            ])
            if conflit:
                raise ValidationError(_("Ce créneau est déjà pris pour '%s'.") % rec.service_id.nom)

    @api.constrains("date_heure_reservation", "service_id")
    def _check_dans_horaires(self):
        for rec in self:
            if not rec.date_heure_reservation or not rec.service_id:
                continue
            s            = rec.service_id
            # ✅ Convertit en heure locale pour comparer avec les horaires du service
            dt_local     = _utc_to_local(rec.date_heure_reservation, rec.env)
            date         = dt_local.date()
            h_ouv, h_fer = s._get_horaire_du_jour(date)
            h = dt_local.hour + dt_local.minute / 60.0
            if h_fer > h_ouv:
                valide = h_ouv <= h < h_fer
            else:
                valide = h >= h_ouv or h < h_fer
            if not valide:
                raise ValidationError(
                    _("Le créneau %s est hors des horaires de '%s' (%s–%s).")
                    % (dt_local.strftime("%H:%M"), s.nom, _fmt_time(h_ouv), _fmt_time(h_fer))
                )

    # ── Action "Je suis là" ───────────────────────────────────────────────────

    def action_je_suis_la(self, latitude: float, longitude: float) -> dict:
        self.ensure_one()

        if self.statut == "annule":
            return {"success": False, "error": "reservation_annulee",
                    "message": _("Cette réservation a été annulée.")}
        if self.statut == "arrive":
            return {"success": False, "error": "ticket_deja_attribue",
                    "message": _("Ticket déjà attribué : %s.") % self.ticket_id.name,
                    "ticket_id": self.ticket_id.id}
        if not self.queue_id:
            return {"success": False, "error": "no_queue",
                    "message": _("Aucune file d'attente pour ce service.")}

        # ── Vérification fenêtre horaire ──────────────────────────────────────
        # date_heure_reservation est en UTC dans Odoo.
        # now_utc est aussi en UTC → comparaison cohérente.
        duree_estimee = self.service_id.dure_estimee_par_defaut or 15
        now_utc       = fields.Datetime.now()   # UTC naïf
        delta         = datetime.timedelta(minutes=duree_estimee)
        fenetre_debut_utc = self.date_heure_reservation - delta
        fenetre_fin_utc   = self.date_heure_reservation + delta

        if not (fenetre_debut_utc <= now_utc <= fenetre_fin_utc):
            fenetre_debut_local = _utc_to_local(fenetre_debut_utc, self.env)
            fenetre_fin_local   = _utc_to_local(fenetre_fin_utc,   self.env)
            return {
                "success": False,
                "error":   "hors_fenetre",
                "message": _(
                    "Le bouton « Je suis là » n'est disponible que de %s à %s."
                ) % (
                    fenetre_debut_local.strftime("%H:%M"),
                    fenetre_fin_local.strftime("%H:%M"),
                ),
                # ISO sans Z → interprété comme heure locale par le client mobile
                "fenetre_debut": fenetre_debut_local.strftime("%Y-%m-%dT%H:%M:%S"),
                "fenetre_fin":   fenetre_fin_local.strftime("%Y-%m-%dT%H:%M:%S"),
            }

        if self.localisation_id:
            rayon     = self.localisation_id.rayon_validation
            pharm_lat = self.localisation_id.pharmacie_lat
            pharm_lon = self.localisation_id.pharmacie_lon
        else:
            rayon     = self.rayon_validation
            pharm_lat = self.pharmacie_lat
            pharm_lon = self.pharmacie_lon

        distance = _haversine(latitude, longitude, pharm_lat, pharm_lon)

        if distance > rayon:
            return {
                "success": False, "error": "trop_loin",
                "message": _(
                    "Vous êtes à %.0fm de la pharmacie. "
                    "Rapprochez-vous à moins de %dm."
                ) % (distance, rayon),
                "distance_metres": round(distance, 1),
                "rayon_metres":    rayon,
            }

        # ── Création du ticket ────────────────────────────────────────────────
        ticket = self.env["pharmacy.ticket"].create({
            "queue_id":       self.queue_id.id,
            "user_id":        self.user_id.id,
            "reservation_id": self.id,
            "type_ticket":    "virtuel",
        })
        self.write({"statut": "arrive", "ticket_id": ticket.id})

        return {
            "success": True,
            "ticket": {
                "id":                   ticket.id,
                "numero":               ticket.name,
                "position":             ticket.position,
                "temps_attente_estime": self.queue_id.temps_attente_estime,
                "service":              self.service_id.nom,
                "queue_id":             self.queue_id.id,
                "queue":                self.queue_id.display_name,
            },
            "distance_metres": round(distance, 1),
        }


# ── Helpers module-level ──────────────────────────────────────────────────────

def _utc_to_local(dt_utc, env) -> datetime.datetime:
    """
    Convertit un datetime UTC naïf en datetime local naïf.
    Utilise le timezone de l'utilisateur courant, sinon Africa/Tunis.
    """
    tz_name = (
        env.user.tz
        or env["ir.config_parameter"].sudo().get_param("your_module.timezone")
        or "Africa/Tunis"
    )
    try:
        local_tz = pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        local_tz = pytz.timezone("Africa/Tunis")

    dt_aware = pytz.utc.localize(dt_utc)
    return dt_aware.astimezone(local_tz).replace(tzinfo=None)


def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _fmt_time(val: float) -> str:
    h = int(val)
    m = int(round((val - h) * 60))
    return f"{h:02d}:{m:02d}"
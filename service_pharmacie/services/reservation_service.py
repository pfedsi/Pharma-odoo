# -*- coding: utf-8 -*-
"""SERVICE — ReservationService"""
import datetime
import pytz
from odoo.exceptions import AccessError, UserError
from odoo.fields import Datetime


class ReservationService:

    def __init__(self, env):
        self.env = env

    # ── API publique ──────────────────────────────────────────────────────────

    def create(self, user_id: int, service_id: int, date_heure: str, notes: str = "") -> dict:
        service = self.env["pharmacy.service"].sudo().browse(service_id)
        if not service.exists() or not service.active:
            raise UserError(f"Service {service_id} introuvable ou inactif.")

        if isinstance(date_heure, str):
            date_heure = date_heure.replace("T", " ")

        # ✅ FIX TIMEZONE : la date envoyée par le client est en heure locale
        # (ex: "2026-03-18 17:00:00" = heure Tunisie UTC+1).
        # Odoo stocke les Datetime en UTC. On convertit explicitement.
        tz_name = self.env["res.lang"].sudo().search(
            [("active", "=", True)], limit=1
        ).mapped("name")
        # Récupère le timezone depuis les paramètres système Odoo
        system_tz = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("your_module.timezone")
            or self.env.context.get("tz")
            or self.env.user.tz
            or "Africa/Tunis"
        )

        date_heure_naive = Datetime.to_datetime(date_heure)
        if not date_heure_naive:
            raise UserError("Format de date invalide. Utiliser YYYY-MM-DDTHH:MM:SS.")

        # Localise en heure locale puis convertit en UTC pour le stockage
        try:
            local_tz = pytz.timezone(system_tz)
        except pytz.UnknownTimeZoneError:
            local_tz = pytz.timezone("Africa/Tunis")

        # date_heure_naive est naïve (sans timezone) → on l'interprète comme locale
        date_heure_local = local_tz.localize(date_heure_naive)
        # Conversion en UTC pour le stockage Odoo
        date_heure_utc = date_heure_local.astimezone(pytz.utc).replace(tzinfo=None)

        conflit = self.env["pharmacy.reservation"].sudo().search_count([
            ("user_id",                "=", user_id),
            ("service_id",             "=", service_id),
            ("date_heure_reservation", "=", date_heure_utc),
            ("statut",                 "not in", ["annule"]),
        ])
        if conflit:
            raise UserError(
                "Vous avez déjà une réservation active sur ce service à ce créneau."
            )

        reservation = self.env["pharmacy.reservation"].sudo().create({
            "user_id":                user_id,
            "service_id":             service_id,
            "date_heure_reservation": date_heure_utc,
            "notes":                  notes,
        })
        return self._to_dict(reservation)

    def list_for_user(self, user_id: int, statut: str | None = None) -> list:
        domain = [("user_id", "=", user_id)]
        if statut:
            domain.append(("statut", "=", statut))
        reservations = self.env["pharmacy.reservation"].sudo().search(
            domain,
            order="date_heure_reservation desc",
        )
        return [self._to_dict(r) for r in reservations]

    def get_by_id(self, reservation_id: int, user_id: int) -> dict:
        return self._to_dict(self._fetch_owned(reservation_id, user_id))

    def annuler(self, reservation_id: int, user_id: int) -> dict:
        reservation = self._fetch_owned(reservation_id, user_id)
        if reservation.statut == "annule":
            raise UserError("Cette réservation est déjà annulée.")
        if reservation.statut == "arrive":
            raise UserError(
                "Impossible d'annuler une réservation arrivée. "
                "Contactez la pharmacie."
            )
        reservation.write({"statut": "annule"})
        return {
            "success":        True,
            "message":        "Réservation annulée avec succès.",
            "reservation_id": reservation_id,
        }

    def je_suis_la(
        self,
        reservation_id: int,
        user_id: int,
        latitude: float,
        longitude: float,
    ) -> dict:
        reservation = self._fetch_owned(reservation_id, user_id)
        return reservation.action_je_suis_la(latitude, longitude)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _fetch_owned(self, reservation_id: int, user_id: int):
        reservation = self.env["pharmacy.reservation"].sudo().browse(reservation_id)
        if not reservation.exists():
            raise UserError(f"Réservation {reservation_id} introuvable.")

        public_user = self.env.ref("base.public_user")

        # Autoriser les réservations créées via le flux mobile public
        if reservation.user_id.id == public_user.id:
            return reservation

        if reservation.user_id.id != user_id:
            raise AccessError("Accès refusé à cette réservation.")

        return reservation

    def _utc_to_local(self, dt_utc) -> datetime.datetime:
        """Convertit un datetime UTC naïf en datetime local naïf (pour l'affichage)."""
        if not dt_utc:
            return dt_utc
        system_tz = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("your_module.timezone")
            or self.env.user.tz
            or "Africa/Tunis"
        )
        try:
            local_tz = pytz.timezone(system_tz)
        except pytz.UnknownTimeZoneError:
            local_tz = pytz.timezone("Africa/Tunis")

        dt_aware = pytz.utc.localize(dt_utc)
        return dt_aware.astimezone(local_tz).replace(tzinfo=None)

    def _to_dict(self, r) -> dict:
        service = r.service_id

        # Coordonnées GPS
        if r.localisation_id:
            pharmacie_lat = r.localisation_id.pharmacie_lat
            pharmacie_lon = r.localisation_id.pharmacie_lon
            rayon         = r.localisation_id.rayon_validation
        else:
            pharmacie_lat = r.pharmacie_lat
            pharmacie_lon = r.pharmacie_lon
            rayon         = r.rayon_validation

        # File d'attente active
        queue = r.queue_id
        queue_info = None
        if queue and queue.active:
            queue_info = {
                "id":                   queue.id,
                "nom":                  queue.display_name,
                "en_attente":           queue.nb_en_attente,
                "temps_attente_estime": queue.temps_attente_estime,
            }

        # ✅ FIX TIMEZONE : fenetre_je_suis_la en heure LOCALE pour le client
        # date_heure_reservation est stockée UTC dans Odoo
        # → on convertit en local avant de calculer et sérialiser la fenêtre
        fenetre_je_suis_la = None
        if r.date_heure_reservation and service:
            duree = service.dure_estimee_par_defaut or 15
            delta = datetime.timedelta(minutes=duree)

            # Convertit l'heure UTC stockée → heure locale
            dt_local = self._utc_to_local(r.date_heure_reservation)

            fenetre_je_suis_la = {
                # ISO sans 'Z' → le client l'interprète comme heure locale
                "debut": (dt_local - delta).strftime("%Y-%m-%dT%H:%M:%S"),
                "fin":   (dt_local + delta).strftime("%Y-%m-%dT%H:%M:%S"),
            }

        # ✅ FIX TIMEZONE : date_heure renvoyée en heure locale (pas UTC)
        date_heure_local = self._utc_to_local(r.date_heure_reservation)

        return {
            "id":         r.id,
            "service_id": service.id  if service else None,
            "service":    service.nom if service else None,
            "queue":      queue_info,
            # Heure locale pour l'affichage dans l'app
            "date_heure": (
                date_heure_local.strftime("%Y-%m-%dT%H:%M:%S")
                if date_heure_local else None
            ),
            "statut":           r.statut,
            "notes":            r.notes or "",
            "pharmacie_lat":    pharmacie_lat,
            "pharmacie_lon":    pharmacie_lon,
            "rayon_validation": rayon,
            "fenetre_je_suis_la": fenetre_je_suis_la,
            "ticket": {
                "id":       r.ticket_id.id,
                "numero":   r.ticket_id.name,
                "etat":     r.ticket_id.etat,
                "position": r.ticket_id.position,
            } if r.ticket_id else None,
        }
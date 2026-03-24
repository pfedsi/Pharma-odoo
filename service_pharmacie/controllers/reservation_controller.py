# -*- coding: utf-8 -*-
"""CONTROLLER — ReservationController"""
from odoo import http
from ..services import ReservationService
from ._base import ok, error, parse_body, handle_service_errors, current_uid


class ReservationController(http.Controller):

    # ── 1. Créer une réservation ──────────────────────────────────────────────

    @http.route("/api/pharmacy/reservations",
                auth="user", methods=["POST"], csrf=False)
    @handle_service_errors
    def create_reservation(self):
        """
        POST /api/pharmacy/reservations
        Body  : { "service_id": int, "date_heure_reservation": str, "notes"?: str }
        201   : { "reservation": Reservation }
        400   : { "error": "créneau indisponible / hors horaires" }
        401   : { "error": "Authentification requise." }
        """
        uid = current_uid()
        if not uid:
            return error("Authentification requise.", 401)

        body, err = parse_body()
        if err:
            return err

        service_id = body.get("service_id")
        date_heure = body.get("date_heure_reservation")
        if not service_id or not date_heure:
            return error("service_id et date_heure_reservation sont requis.", 400)

        svc = ReservationService(http.request.env)
        return ok(
            {"reservation": svc.create(
                uid,
                service_id,
                date_heure,
                body.get("notes", ""),
            )},
            201,
        )

    # ── 2. Mes réservations ───────────────────────────────────────────────────

    @http.route("/api/pharmacy/reservations/mes-reservations",
                auth="user", methods=["GET"], csrf=False)
    @handle_service_errors
    def mes_reservations(self):
        """
        GET /api/pharmacy/reservations/mes-reservations
        Query : ?statut=en_attente|arrive|annule
        200   : { "reservations": [ Reservation, ... ] }
        400   : { "error": "Valeur de statut invalide." }
        401   : { "error": "Authentification requise." }
        """
        uid = current_uid()
        if not uid:
            return error("Authentification requise.", 401)

        statut = http.request.params.get("statut")
        STATUTS_VALIDES = {"en_attente", "arrive", "annule"}
        if statut and statut not in STATUTS_VALIDES:
            return error(
                f"Valeur de statut invalide. Valeurs acceptées : {', '.join(STATUTS_VALIDES)}.",
                400,
            )

        svc = ReservationService(http.request.env)
        return ok({"reservations": svc.list_for_user(uid, statut=statut)})

    # ── 3. Détail d'une réservation ───────────────────────────────────────────

    @http.route("/api/pharmacy/reservations/<int:reservation_id>",
                auth="user", methods=["GET"], csrf=False)
    @handle_service_errors
    def get_reservation(self, reservation_id):
        """
        GET /api/pharmacy/reservations/<id>
        200 : { "reservation": Reservation }
        403 : { "error": "Accès refusé." }
        404 : { "error": "Réservation introuvable." }
        """
        uid = current_uid()
        if not uid:
            return error("Authentification requise.", 401)

        svc = ReservationService(http.request.env)
        return ok({"reservation": svc.get_by_id(reservation_id, uid)})

    # ── 4. Je suis là (validation GPS) ───────────────────────────────────────

    @http.route("/api/pharmacy/reservations/<int:reservation_id>/je-suis-la",
                auth="user", methods=["POST"], csrf=False)
    @handle_service_errors
    def je_suis_la(self, reservation_id):
        """
        POST /api/pharmacy/reservations/<id>/je-suis-la
        Body    : { "latitude": float, "longitude": float }
        200 ok  : { "success": true,  "ticket": {...}, "distance_metres": float }
        200 loin: { "success": false, "error": "trop_loin", "message": "...",
                    "distance_metres": float, "rayon_metres": int }
        400     : { "error": "latitude et longitude sont requis." }
        401     : { "error": "Authentification requise." }
        403     : { "error": "Accès refusé." }
        """
        uid = current_uid()
        if not uid:
            return error("Authentification requise.", 401)

        body, err = parse_body()
        if err:
            return err

        lat = body.get("latitude")
        lon = body.get("longitude")
        if lat is None or lon is None:
            return error("latitude et longitude sont requis.", 400)

        try:
            lat = float(lat)
            lon = float(lon)
        except (TypeError, ValueError):
            return error("latitude et longitude doivent être des nombres.", 400)

        svc = ReservationService(http.request.env)
        return ok(svc.je_suis_la(reservation_id, uid, lat, lon))

    # ── 5. Annuler une réservation ────────────────────────────────────────────

    @http.route("/api/pharmacy/reservations/<int:reservation_id>/annuler",
                auth="user", methods=["POST"], csrf=False)
    @handle_service_errors
    def annuler_reservation(self, reservation_id):
        """
        POST /api/pharmacy/reservations/<id>/annuler
        200 : { "success": true, "message": "...", "reservation_id": int }
        400 : { "error": "Impossible d'annuler une réservation arrivée." }
        401 : { "error": "Authentification requise." }
        403 : { "error": "Accès refusé." }
        """
        uid = current_uid()
        if not uid:
            return error("Authentification requise.", 401)

        svc = ReservationService(http.request.env)
        return ok(svc.annuler(reservation_id, uid))
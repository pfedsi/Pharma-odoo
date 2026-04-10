# -*- coding: utf-8 -*-
"""CONTROLLER — ServiceController (mis à jour)
Ajout : GET /api/pharmacy/services/<id>/horaires
"""
from odoo import http
from ..services import ServiceService
from ._base import ok, error, handle_service_errors


class ServiceController(http.Controller):

    # ── 1. Liste des services actifs ──────────────────────────────────────────

    @http.route("/api/pharmacy/services", auth="public", methods=["GET"], csrf=False)
    @handle_service_errors
    def list_services(self):
        type_affichage = http.request.params.get("type_affichage") or None
        svc = ServiceService(http.request.env)
        return ok({"services": svc.list_active(type_affichage=type_affichage)})

    # ── 2. Détail d'un service ────────────────────────────────────────────────

    @http.route("/api/pharmacy/services/<int:service_id>",
                auth="public", methods=["GET"], csrf=False)
    @handle_service_errors
    def get_service(self, service_id):
        """
        GET /api/pharmacy/services/3

        Response 200 : { "service": Service }
        Response 404 : { "error": "..." }
        """
        svc = ServiceService(http.request.env)
        return ok({"service": svc.get_by_id(service_id)})

    # ── 3. Horaires journaliers d'un service ──────────────────────────────────

    @http.route("/api/pharmacy/services/<int:service_id>/horaires",
                auth="public", methods=["GET"], csrf=False)
    @handle_service_errors
    def get_horaires(self, service_id):
        """
        GET /api/pharmacy/services/3/horaires

        Retourne les horaires journaliers configurés pour ce service.
        Les jours sans entrée utilisent les horaires par défaut du service.

        Response 200 :
        {
          "service_id": 3,
          "nom": "Ordonnances",
          "horaires_par_defaut": {
            "ouverture": "08:00",
            "fermeture": "18:00",
            "intervalle_minutes": 30
          },
          "horaires": [
            { "jour_index": "0", "jour": "Lundi",    "actif": true,  "ouverture": "08:00", "fermeture": "17:00" },
            { "jour_index": "1", "jour": "Mardi",    "actif": true,  "ouverture": "08:00", "fermeture": "17:00" },
            { "jour_index": "5", "jour": "Samedi",   "actif": true,  "ouverture": "09:00", "fermeture": "13:00" },
            { "jour_index": "6", "jour": "Dimanche", "actif": false, "ouverture": null,    "fermeture": null    }
          ]
        }

        Response 404 : { "error": "Service introuvable." }
        """
        svc = ServiceService(http.request.env)
        return ok(svc.get_horaires(service_id))

    # ── 4. Créneaux disponibles ───────────────────────────────────────────────

    @http.route("/api/pharmacy/services/<int:service_id>/slots",
                auth="public", methods=["GET"], csrf=False)
    @handle_service_errors
    def get_slots(self, service_id):
        """
        GET /api/pharmacy/services/3/slots?date=2026-03-17

        Response 200 : { "service_id": ..., "slots": [ ... ] }
        Response 400 : { "error": "Format de date invalide." }
        Response 404 : { "error": "Service introuvable." }
        """
        date_str = http.request.params.get("date") or __import__("datetime").date.today().isoformat()
        svc = ServiceService(http.request.env)
        return ok(svc.get_slots(service_id, date_str))
      
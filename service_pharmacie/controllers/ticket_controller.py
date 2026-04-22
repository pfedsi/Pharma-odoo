# -*- coding: utf-8 -*-
"""CONTROLLER — TicketController (Odoo 19)"""
from odoo import http
from ..services import TicketService
from ._base import ok, error, handle_service_errors, current_uid


class TicketController(http.Controller):

    # ── 1. Détail d'un ticket ─────────────────────────────────────────────────

    @http.route("/api/pharmacy/tickets/<int:ticket_id>",
                auth="user", methods=["GET"], csrf=False)
    @handle_service_errors
    def get_ticket(self, ticket_id):
        """
        GET /api/pharmacy/tickets/12

        Response 200 :
        {
          "id": 12, "numero": "File-001", "etat": "en_attente",
          "position": 3, "type_ticket": "virtuel",
          "service": "Ordonnances", "queue_id": 1,
          "temps_attente_estime": 45,
          "heure_creation": "2026-03-18T10:00:00",
          "heure_appel": null, "heure_fin": null, "reservation_id": 5
        }
        """
        uid = current_uid()
        if not uid:
            return error("Authentification requise.", 401)
        svc = TicketService(http.request.env)
        return ok(svc.get_by_id(ticket_id))

    # ── 2. Mes tickets ────────────────────────────────────────────────────────

    @http.route("/api/pharmacy/tickets/mine",
                auth="user", methods=["GET"], csrf=False)
    @handle_service_errors
    def list_my_tickets(self):
        """
        GET /api/pharmacy/tickets/mine
        GET /api/pharmacy/tickets/mine?statut=en_attente

        Paramètre optionnel : statut = en_attente | appele | termine | annule

        Response 200 : { "tickets": [...], "total": 2 }
        """
        uid = current_uid()
        if not uid:
            return error("Authentification requise.", 401)

        statut  = http.request.params.get("statut") or None
        svc     = TicketService(http.request.env)
        tickets = svc.list_mine(uid, statut=statut)
        return ok({"tickets": tickets, "total": len(tickets)})


    @http.route("/api/pharmacy/tickets", auth="public", methods=["POST"], csrf=False, type="http")
    @handle_service_errors
    def create_ticket(self, **post):
            params = http.request.params
    
            try:
                queue_id = int(params.get("queue_id", 0))
            except (TypeError, ValueError):
                queue_id = 0
    
            if not queue_id:
                return error("queue_id est requis.", 400)
    
            type_ticket = params.get("type_ticket", "physique")
            if type_ticket not in ("physique", "virtuel"):
                return error("type_ticket doit être 'physique' ou 'virtuel'.", 400)
    
            reservation_id = params.get("reservation_id")
            if reservation_id:
                try:
                    reservation_id = int(reservation_id)
                except (TypeError, ValueError):
                    return error("reservation_id invalide.", 400)
            else:
                reservation_id = None
    
            # Règles métier
            if type_ticket == "virtuel" and not reservation_id:
                return error("reservation_id est requis pour un ticket virtuel.", 400)
    
            if type_ticket == "physique" and reservation_id:
                return error("Un ticket physique ne doit pas avoir de reservation_id.", 400)
    
            uid = http.request.env.ref("base.public_user").id
    
            svc = TicketService(http.request.env)
            ticket = svc.create_ticket(
                queue_id=queue_id,
                uid=uid,
                type_ticket=type_ticket,
                reservation_id=reservation_id,
            )
            return ok({"ticket": ticket})
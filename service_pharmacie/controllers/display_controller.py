# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request, Response
import json
import logging

_logger = logging.getLogger(__name__)


class DisplayController(http.Controller):

    @http.route("/pharmacy/display", type="http", auth="public")
    def pharmacy_display_page(self, **kwargs):
        return request.render("service_pharmacie.pharmacy_display_page")

    @http.route("/pharmacy/display/data", type="http", auth="public", methods=["POST"], csrf=False)
    def pharmacy_display_data(self, **kwargs):
        Queue        = request.env["pharmacy.queue"].sudo()
        Ticket       = request.env["pharmacy.ticket"].sudo()
        Rattachement = request.env["pharmacy.rattachement"].sudo()

        queues = Queue.search([("active", "=", True)], order="id asc")

        result = []
        for queue in queues:

            # ── Tickets appelés (au guichet) ──────────────────────────────────
            rattachements = Rattachement.search([
                ("active", "=", True),
                ("file_id", "=", queue.id),
            ], order="poste_number asc, id asc")

            appeles = []
            for r in rattachements:
                if r.current_ticket_id and r.current_ticket_id.etat == "appele":
                    appeles.append({
                        "rattachement_id": r.id,
                        "ticket_id":       r.current_ticket_id.id,
                        "ticket_name":     r.current_ticket_id.name or "--",
                        "poste_number":    str(r.poste_number) if r.poste_number else "--",
                        "etat":            "appele",
                    })

            # ── Tickets en attente ────────────────────────────────────────────
            tickets_attente = Ticket.search([
                ("queue_id", "=", queue.id),
                ("etat",     "=", "en_attente"),
            ], order="priorite desc, heure_creation asc", limit=10)

            en_attente = []
            for t in tickets_attente:
                en_attente.append({
                    "rattachement_id": t.id,
                    "ticket_id":       t.id,
                    "ticket_name":     t.name or "--",
                    "poste_number":    "--",
                    "etat":            "en_attente",
                })

            result.append({
                "queue_id":   queue.id,
                "queue_name": queue.display_name or queue.name or "--",
                "appeles":    appeles,
                "en_attente": en_attente,
            })

        payload = {"success": True, "queues": result}

        return Response(
            json.dumps(payload),
            content_type="application/json;charset=utf-8",
            status=200,
        )
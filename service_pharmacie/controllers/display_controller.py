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

    @http.route(
        "/pharmacy/display/data",
        type="http",
        auth="public",
        methods=["POST", "GET"],
        csrf=False,
    )
    def pharmacy_display_data(self, **kwargs):
        try:
            Queue        = request.env["pharmacy.queue"].sudo()
            Ticket       = request.env["pharmacy.ticket"].sudo()
            Rattachement = request.env["pharmacy.rattachement"].sudo()

            queues = Queue.search([("active", "=", True)], order="id asc")
            result = []

            for queue in queues:
                # ── Tickets appelés ───────────────────────────────────────────
                # En mode prioritaire un opérateur peut être basculé sur une
                # autre file (file_id ≠ file_prioritaire_id).  On cherche donc
                # les rattachements dont le ticket en cours appartient à cette
                # file, quel que soit file_id courant.
                rattachements_appeles = Rattachement.search([
                    ("active",            "=", True),
                    ("current_ticket_id", "!=", False),
                ], order="poste_number asc, id asc")

                appeles = []
                for r in rattachements_appeles:
                    ticket = r.current_ticket_id
                    if ticket and ticket.etat == "appele" and ticket.queue_id.id == queue.id:
                        appeles.append({
                            "rattachement_id": r.id,
                            "ticket_id":       ticket.id,
                            "ticket_name":     ticket.name or "--",
                            "poste_number":    str(r.poste_number) if r.poste_number else "--",
                            "etat":            "appele",
                            "priorite":        ticket.priorite or 1,
                        })

                # ── Tickets en attente ────────────────────────────────────────
                tickets_attente = Ticket.search([
                    ("queue_id", "=", queue.id),
                    ("etat",     "=", "en_attente"),
                    ("priorite", "in", [1, 2]),
                ], order="priorite desc, heure_creation asc", limit=10)

                en_attente = []
                for t in tickets_attente:
                    en_attente.append({
                        "ticket_id":    t.id,
                        "ticket_name":  t.name or "--",
                        "poste_number": "--",
                        "etat":         "en_attente",
                        "priorite":     t.priorite or 1,
                    })

                result.append({
                    "queue_id":   queue.id,
                    "queue_name": queue.display_name or queue.name or "--",
                    "appeles":    appeles,
                    "en_attente": en_attente,
                })

            payload = {"success": True, "queues": result}

        except Exception as e:
            _logger.exception("[DisplayController] /pharmacy/display/data error")
            payload = {"success": False, "error": str(e)}

        return Response(
            json.dumps(payload, ensure_ascii=False),
            content_type="application/json; charset=utf-8",
            status=200,
        )
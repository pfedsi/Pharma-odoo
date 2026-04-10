# -*- coding: utf-8 -*-
"""CONTROLLER — QueueController"""
from odoo import http
from ..services import QueueService
from ._base import ok, handle_service_errors


class QueueController(http.Controller):

    # ── 1. Liste des files actives ────────────────────────────────────────────

    @http.route("/api/pharmacy/queues", auth="public", methods=["GET"], csrf=False)
    @handle_service_errors
    def get_queues(self):
            type_affichage = http.request.params.get("type_affichage") or None
            svc = QueueService(http.request.env)
            return ok({"queues": svc.list_active(type_affichage=type_affichage)})

    # ── 2. Détail d'une file ──────────────────────────────────────────────────

    @http.route("/api/pharmacy/queues/<int:queue_id>",
                auth="public", methods=["GET"], csrf=False)
    @handle_service_errors
    def get_queue(self, queue_id):
        """
        GET /api/pharmacy/queues/<id>

        200 : { "queue": Queue }
        404 : { "error": "File d'attente introuvable." }
        """
        svc = QueueService(http.request.env)
        return ok({"queue": svc.get_by_id(queue_id)})
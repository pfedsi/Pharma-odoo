# -*- coding: utf-8 -*-
"""CONTROLLER — RattachementController"""
from odoo import http
from ..services import RattachementService
from ._base import ok, error, handle_service_errors, current_uid
from odoo.http import request


class RattachementController(http.Controller):

    @http.route("/api/pharmacy/rattachements",
                auth="user", methods=["GET"], csrf=False)
    @handle_service_errors
    def get_rattachements(self):
        if not current_uid():
            return error("Authentification requise.", 401)
        svc = RattachementService(request.env)
        return ok({"rattachements": svc.list_active()})

    @http.route("/api/pharmacy/rattachements/<int:rattachement_id>/appeler-prochain",
                auth="user", methods=["POST"], csrf=False)
    @handle_service_errors
    def appeler_prochain(self, rattachement_id):
        if not current_uid():
            return error("Authentification requise.", 401)
        svc = RattachementService(request.env)
        return ok(svc.appeler_prochain(rattachement_id))

    @http.route("/pos/rattachement/current", type="jsonrpc", auth="user")
    def get_current_rattachement(self):
        return request.env["pharmacy.rattachement"].pos_get_my_rattachement()

    @http.route("/pos/rattachement/get_queues", type="jsonrpc", auth="user")
    def get_queues(self):
        queues = request.env["pharmacy.queue"].search([("active", "=", True)])
        return [{"id": q.id, "name": q.display_name} for q in queues]

    @http.route("/pos/rattachement/get_services", type="jsonrpc", auth="user")
    def get_services(self):
        services = request.env["pharmacy.service"].search([("active", "=", True)])
        return [{"id": s.id, "name": s.nom} for s in services]

    @http.route("/pos/rattachement/set", type="jsonrpc", auth="user")
    def set_rattachement(
        self,
        mode_rattachement,
        file_id=False,
        service_prioritaire_id=False,
        poste_number=False,
    ):
        return request.env["pharmacy.rattachement"].pos_set_my_rattachement(
            mode_rattachement=mode_rattachement,
            file_id=file_id,
            service_prioritaire_id=service_prioritaire_id,
            poste_number=poste_number,
        )

    @http.route("/pos/rattachement/call_next", type="jsonrpc", auth="user")
    def call_next_ticket(self):
        return request.env["pharmacy.rattachement"].pos_call_next_ticket()

    @http.route("/pos/rattachement/finish_current", type="jsonrpc", auth="user")
    def finish_current_ticket(self):
        return request.env["pharmacy.rattachement"].pos_finish_current_ticket()
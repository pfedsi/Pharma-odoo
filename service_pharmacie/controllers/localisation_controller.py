# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request


class PharmacyLocalizationController(http.Controller):

    @http.route(
        "/api/pharmacy/localisation",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def get_pharmacy_localisation(self, **kwargs):
        localisation = request.env["pharmacy.localization"].sudo().get_singleton()

        if not localisation:
            return {
                "success": False,
                "message": "Localisation pharmacie introuvable.",
            }

        return {
            "success": True,
            "data": localisation.export_mobile_payload(),
        }
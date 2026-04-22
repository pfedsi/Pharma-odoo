# -*- coding: utf-8 -*-

import logging

from odoo import http

from ..services.chatbot_service import ChatbotService
from ..utils.http_utils import get_json_payload

_logger = logging.getLogger(__name__)


class QPharmaBotController(http.Controller):

    @http.route(
        "/api/chatbot/message",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def chatbot_message(self, **kwargs):
        try:
            payload = get_json_payload(kwargs)
            _logger.info("QPharmaBot /message payload: %s", payload)

            result = ChatbotService.handle_message(payload)

            if not isinstance(result, dict):
                _logger.error("QPharmaBot /message invalid result type: %s", type(result))
                return {
                    "success": False,
                    "error": "Réponse invalide du service chatbot.",
                }

            _logger.info("QPharmaBot /message result keys: %s", list(result.keys()))
            return result

        except Exception as e:
            _logger.exception("QPharmaBot /message unexpected error")
            return {
                "success": False,
                "error": f"Erreur serveur chatbot: {str(e)}",
            }

    @http.route(
        "/api/chatbot/stock",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def get_stock(self, **kwargs):
        try:
            payload = get_json_payload(kwargs)
            return ChatbotService.get_stock(payload)
        except Exception as e:
            _logger.exception("QPharmaBot /stock error")
            return {
                "success": False,
                "error": f"Erreur serveur stock: {str(e)}",
            }

    @http.route(
        "/api/chatbot/panier",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def panier_get(self, **kwargs):
        try:
            payload = get_json_payload(kwargs)
            return ChatbotService.get_panier(payload)
        except Exception as e:
            _logger.exception("QPharmaBot /panier error")
            return {
                "success": False,
                "error": f"Erreur serveur panier: {str(e)}",
            }

    @http.route(
        "/api/chatbot/panier/ajouter",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def panier_ajouter(self, **kwargs):
        try:
            payload = get_json_payload(kwargs)
            return ChatbotService.add_to_panier(payload)
        except Exception as e:
            _logger.exception("QPharmaBot /panier/ajouter error")
            return {
                "success": False,
                "error": f"Erreur serveur ajout panier: {str(e)}",
            }

    @http.route(
        "/api/chatbot/panier/modifier",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def panier_modifier(self, **kwargs):
        try:
            payload = get_json_payload(kwargs)
            return ChatbotService.modify_panier(payload)
        except Exception as e:
            _logger.exception("QPharmaBot /panier/modifier error")
            return {
                "success": False,
                "error": f"Erreur serveur modification panier: {str(e)}",
            }

    @http.route(
        "/api/chatbot/panier/vider",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def panier_vider(self, **kwargs):
        try:
            payload = get_json_payload(kwargs)
            return ChatbotService.clear_panier(payload)
        except Exception as e:
            _logger.exception("QPharmaBot /panier/vider error")
            return {
                "success": False,
                "error": f"Erreur serveur vider panier: {str(e)}",
            }

    @http.route(
        "/api/chatbot/panier/confirmer",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def panier_confirmer(self, **kwargs):
        try:
            payload = get_json_payload(kwargs)
            return ChatbotService.confirm_panier(payload)
        except Exception as e:
            _logger.exception("QPharmaBot /panier/confirmer error")
            return {
                "success": False,
                "error": f"Erreur serveur confirmation panier: {str(e)}",
            }
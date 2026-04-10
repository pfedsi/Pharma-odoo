# -*- coding: utf-8 -*-
"""
Q-Pharma OCR — Controller Odoo 19
===================================
Architecture retenue :
  L'app mobile ne peut pas contenir la clé OpenAI en clair.
  Odoo la stocke côté serveur et la délivre uniquement aux utilisateurs
  authentifiés via leur token de session Odoo.

  Flow :
    1. App mobile → POST /web/session/authenticate  (login Odoo)
    2. App mobile → GET  /qpharma/ocr/apikey        (récupère la clé)
    3. App mobile → POST api.openai.com/v1/chat/completions  (OCR direct)
"""
import json
import logging

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


def _get_param(key: str, default: str = '') -> str:
    return request.env['ir.config_parameter'].sudo().get_param(key, default=default).strip()


class QpharmaOcrController(http.Controller):

    # ── GET /qpharma/ocr/apikey ───────────────────────────────────
    @http.route(
        '/qpharma/ocr/apikey',
        type='http',
        auth='user',          # ← doit être connecté à Odoo
        methods=['GET'],
        csrf=False,
        cors='*',
    )
    def get_api_key(self, **kwargs):
        """
        Retourne la clé OpenAI à l'app mobile authentifiée.

        Réponse :
        ---------
        200 OK
        {
            "success": true,
            "api_key": "sk-...",
            "model":   "gpt-4o"
        }

        401 si non authentifié (géré par Odoo automatiquement).
        """
        api_key = _get_param('qpharma_ocr.openai_api_key')
        model   = _get_param('qpharma_ocr.openai_model', default='gpt-4o')

        if not api_key:
            return Response(
                json.dumps({
                    "success": False,
                    "error": (
                        "Clé OpenAI non configurée dans Odoo. "
                        "Paramètres → Technique → Paramètres système → "
                        "qpharma_ocr.openai_api_key"
                    ),
                }),
                content_type='application/json',
                status=503,
            )

        _logger.info("Clé OpenAI délivrée à l'utilisateur %s", request.env.user.login)
        return Response(
            json.dumps({
                "success": True,
                "api_key": api_key,
                "model":   model,
            }),
            content_type='application/json',
            status=200,
        )

    # ── GET /qpharma/ocr/ping ─────────────────────────────────────
    @http.route(
        '/qpharma/ocr/ping',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
        cors='*',
    )
    def ping(self, **kwargs):
        """Health-check public."""
        api_key = _get_param('qpharma_ocr.openai_api_key')
        return Response(
            json.dumps({
                "status":            "ok",
                "module":            "qpharma_ocr",
                "openai_configured": bool(api_key),
            }),
            content_type='application/json',
            status=200,
        )
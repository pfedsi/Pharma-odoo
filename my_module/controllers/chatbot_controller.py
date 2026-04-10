# -*- coding: utf-8 -*-
"""
Q-Pharma Chatbot Didier — Controller Odoo 19
=============================================
Corrections appliquées :
  - request.get_json_data() → kwargs (type='json' injecte les params dans kwargs)
  - Validation du format des messages
  - Suppression cors='*' sur endpoint authentifié
  - Limit de sécurité sur le nombre de messages
"""
import logging
import requests
from odoo import http
from odoo.http import request, Response
import json

_logger = logging.getLogger(__name__)


def _get_param(key: str, default: str = '') -> str:
    return request.env['ir.config_parameter'].sudo().get_param(
        key, default=default
    ).strip()


SYSTEM_PROMPT = (
    "Tu es Didier, un pharmacien virtuel expert et bienveillant de Q-Pharma TN (Tunisie). "
    "Tu réponds en français de façon claire, chaleureuse et professionnelle. "
    "Tu peux répondre aux questions sur les médicaments (indications, contre-indications, "
    "effets secondaires, interactions), les posologies et modes d'administration, "
    "les équivalents génériques disponibles en Tunisie, les conseils de conservation "
    "et de bon usage, et les interactions médicamenteuses. "
    "Règles IMPORTANTES : "
    "Tu n'établis JAMAIS de diagnostic médical. "
    "Tu recommandes toujours de consulter un médecin pour toute prescription. "
    "Tu es concis (3-5 phrases max sauf si explication technique nécessaire). "
    "Tu signes parfois tes réponses par '— Didier, votre pharmacien Q-Pharma'. "
    "Si la question ne concerne pas la pharmacie/santé, tu expliques poliment "
    "que tu es spécialisé en pharmacie."
)

ALLOWED_ROLES = {'user', 'assistant'}
MAX_MESSAGES = 40  # limite de contexte (sécurité + coût)


class QpharmaChatbotController(http.Controller):

    @http.route(
        '/qpharma/chatbot/message',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
        # ← CORRECTION : pas de cors='*' sur un endpoint authentifié
    )
    def chatbot_message(self, messages=None, **kwargs):
        """
        Proxy OpenAI côté serveur Odoo.

        Body JSON :
        -----------
        {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "messages": [
                    {"role": "user",      "content": "Bonjour"},
                    {"role": "assistant", "content": "Bonjour !"},
                    {"role": "user",      "content": "Effets Paracétamol ?"}
                ]
            }
        }

        Réponse :
        ---------
        { "success": true, "reply": "..." }
        """
        # ── Validation ────────────────────────────────────────────
        if not messages or not isinstance(messages, list):
            return {"success": False, "error": "Paramètre 'messages' manquant ou invalide."}

        # Tronquer si trop long
        messages = messages[-MAX_MESSAGES:]

        # Valider chaque message
        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                return {"success": False, "error": f"Message #{i} invalide (doit être un objet)."}
            role = msg.get('role', '')
            content = msg.get('content', '')
            if role not in ALLOWED_ROLES:
                return {"success": False, "error": f"Rôle invalide '{role}' au message #{i}."}
            if not isinstance(content, str) or not content.strip():
                return {"success": False, "error": f"Contenu vide au message #{i}."}

        # ── Clé & modèle ──────────────────────────────────────────
        api_key = _get_param('qpharma_ocr.openai_api_key')
        model   = _get_param('qpharma_ocr.openai_model') or 'gpt-4o'

        if not api_key:
            return {
                "success": False,
                "error": (
                    "Clé OpenAI non configurée. "
                    "Paramètres → Technique → Paramètres système → "
                    "qpharma_ocr.openai_api_key"
                )
            }

        # ── Appel OpenAI ──────────────────────────────────────────
        payload_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                json={
                    "model": model,
                    "max_tokens": 800,
                    "messages": payload_messages,
                },
                timeout=30,
            )
        except requests.Timeout:
            _logger.error("Timeout OpenAI chatbot pour %s", request.env.user.login)
            return {"success": False, "error": "Délai d'attente dépassé (OpenAI)."}
        except requests.RequestException as e:
            _logger.error("Erreur réseau OpenAI chatbot : %s", e)
            return {"success": False, "error": f"Erreur réseau : {e}"}

        # ── Traitement réponse ────────────────────────────────────
        try:
            data = resp.json()
        except ValueError:
            _logger.error("Réponse OpenAI non-JSON : %s", resp.text[:200])
            return {"success": False, "error": "Réponse inattendue d'OpenAI."}

        if not resp.ok:
            msg = data.get("error", {}).get("message", f"HTTP {resp.status_code}")
            _logger.error("OpenAI chatbot erreur : %s", msg)
            return {"success": False, "error": f"OpenAI : {msg}"}

        reply = (
            data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
        )
        if not reply:
            return {"success": False, "error": "Réponse vide de GPT."}

        _logger.info(
            "Chatbot Didier — %s | %d tokens",
            request.env.user.login,
            data.get("usage", {}).get("total_tokens", 0),
        )
        return {"success": True, "reply": reply}

    # ── Health-check ──────────────────────────────────────────────
    @http.route(
        '/qpharma/chatbot/ping',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
        cors='*',
    )
    def ping(self, **kwargs):
        api_key = _get_param('qpharma_ocr.openai_api_key')
        return Response(
            json.dumps({
                "status":            "ok",
                "module":            "qpharma_chatbot",
                "openai_configured": bool(api_key),
            }),
            content_type='application/json',
            status=200,
        )
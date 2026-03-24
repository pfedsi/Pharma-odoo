# -*- coding: utf-8 -*-
"""
CONTROLLER BASE — helpers HTTP partagés.
"""
import json
from functools import wraps
from odoo.http import request
from odoo.exceptions import AccessError, UserError, ValidationError

# Headers CORS — autorise les appels depuis React Native / navigateur mobile
_CORS_HEADERS = [
    ("Access-Control-Allow-Origin",  "*"),
    ("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS"),
    ("Access-Control-Allow-Headers", "Content-Type, X-Session-Id, Accept"),
]


def ok(data: dict, status: int = 200):
    """Réponse JSON succès avec headers CORS."""
    return request.make_response(
        json.dumps(data, default=str),
        headers=[("Content-Type", "application/json")] + _CORS_HEADERS,
        status=status,
    )


def error(message: str, status: int = 400):
    """Réponse JSON erreur avec headers CORS."""
    return ok({"error": message}, status)


def parse_body() -> tuple:
    try:
        body = json.loads(request.httprequest.data or "{}")
        return body, None
    except Exception:
        return {}, error("Corps de requête JSON invalide.", 400)


def current_uid():
    return request.session.uid


def handle_service_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AccessError as e:
            return error(str(e), 403)
        except UserError as e:
            msg = str(e)
            status = 404 if "introuvable" in msg.lower() else 400
            return error(msg, status)
        except ValidationError as e:
            return error(str(e), 400)
    return wrapper
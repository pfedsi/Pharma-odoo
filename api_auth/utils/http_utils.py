import json
import logging

from odoo.http import Response, request

_logger = logging.getLogger(__name__)

_CORS_ALLOWED_ORIGINS = {
    'http://localhost:8081',
    'http://localhost:3000',
    'http://localhost:8069',
    'https://demopharma.eprswarm.com',
}


def cors_headers():
    origin = request.httprequest.headers.get('Origin', '')
    allowed_origin = origin if origin in _CORS_ALLOWED_ORIGINS else 'null'
    return [
        ('Access-Control-Allow-Origin', allowed_origin),
        ('Access-Control-Allow-Credentials', 'true'),
        ('Access-Control-Allow-Methods', 'GET, POST, PUT, OPTIONS'),
        ('Access-Control-Allow-Headers', 'Content-Type, Authorization, Cookie, X-Session-Id'),
        ('Content-Length', '0'),
    ]


def json_response(payload, status=200):
    return Response(
        json.dumps(payload),
        status=status,
        content_type='application/json',
        headers=cors_headers(),
    )


def preflight_response():
    return Response(status=200, headers=cors_headers())


def parse_json_body():
    try:
        raw = request.httprequest.data or b''
        text = raw.decode('utf-8') if isinstance(raw, (bytes, bytearray)) else str(raw)
        parsed = json.loads(text) if text else {}
        if isinstance(parsed, dict) and isinstance(parsed.get('params'), dict):
            return parsed['params']
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, UnicodeDecodeError) as exc:
        _logger.debug("JSON body parse failed: %s", exc)
        return {}


def require_session():
    """
    Resolves the authenticated uid from:
    1. Standard Odoo session cookie
    2. X-Session-Id header in "uid:sid" format
    """
    uid = request.session.uid
    if uid:
        return int(uid)

    token = request.httprequest.headers.get('X-Session-Id', '').strip()
    if not token:
        return None

    try:
        if ':' in token:
            uid_part, _sid_part = token.split(':', 1)
            uid = int(uid_part)
            if uid > 0:
                user = request.env['res.users'].sudo().browse(uid)
                if user.exists() and user.active:
                    _logger.debug("X-Session-Id resolved uid=%s", uid)
                    return uid
    except Exception as exc:
        _logger.debug("X-Session-Id token parse failed: %s", exc)

    return None
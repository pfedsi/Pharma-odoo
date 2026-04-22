import logging

from odoo import http
from odoo.http import request

from ..services.auth_service import AuthService
from ..utils.http_utils import json_response, preflight_response, parse_json_body

_logger = logging.getLogger(__name__)


class AuthController(http.Controller):



    @http.route('/api/auth/register', type='http', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    def register(self, **kw):
        if request.httprequest.method == 'OPTIONS':
            return preflight_response()
        try:
            result = AuthService.register(parse_json_body())
            return json_response(result, status=result.pop('status', 200))
        except Exception:
            _logger.exception("register error")
            return json_response({'success': False, 'error': 'Internal server error'}, status=500)

    @http.route('/api/auth/login', type='http', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    def login(self, **kw):
        if request.httprequest.method == 'OPTIONS':
            return preflight_response()
        try:
            result = AuthService.login(parse_json_body())
            return json_response(result, status=result.pop('status', 200))
        except Exception:
            _logger.exception("login error")
            return json_response({'success': False, 'error': 'Internal server error'}, status=500)

    @http.route('/api/auth/logout', type='http', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    def logout(self, **kw):
        if request.httprequest.method == 'OPTIONS':
            return preflight_response()
        try:
            result = AuthService.logout()
            return json_response(result, status=result.pop('status', 200))
        except Exception:
            _logger.exception("logout error")
            return json_response({'success': False, 'error': 'Internal server error'}, status=500)

    @http.route('/api/auth/google', type='http', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    def google_auth(self, **kw):
        if request.httprequest.method == 'OPTIONS':
            return preflight_response()
        try:
            result = AuthService.google_login(parse_json_body())
            return json_response(result, status=result.pop('status', 200))
        except Exception:
            _logger.exception("google_auth error")
            return json_response({'success': False, 'error': 'Internal server error'}, status=500)

    # ------------------------------------------------------------------
    # Password reset
    # ------------------------------------------------------------------

    @http.route('/api/auth/send_reset_code', type='http', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    def send_reset_code(self, **kw):
        if http.request.httprequest.method == 'OPTIONS':
            return preflight_response()
        try:
            result = AuthService.send_reset_code(parse_json_body())
            return json_response(result, status=result.pop('status', 200))
        except Exception:
            _logger.exception("send_reset_code error")
            return json_response({'success': False, 'error': 'Internal server error'}, status=500)

    @http.route('/api/auth/verify_reset_code', type='http', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    def verify_reset_code(self, **kw):
        if http.request.httprequest.method == 'OPTIONS':
            return preflight_response()
        try:
            result = AuthService.verify_reset_code(parse_json_body())
            return json_response(result, status=result.pop('status', 200))
        except Exception:
            _logger.exception("verify_reset_code error")
            return json_response({'success': False, 'error': 'Internal server error'}, status=500)

    @http.route('/api/auth/reset_password_with_code', type='http', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    def reset_password_with_code(self, **kw):
        if http.request.httprequest.method == 'OPTIONS':
            return preflight_response()
        try:
            result = AuthService.reset_password_with_code(parse_json_body())
            return json_response(result, status=result.pop('status', 200))
        except Exception:
            _logger.exception("reset_password_with_code error")
            return json_response({'success': False, 'error': 'Internal server error'}, status=500)
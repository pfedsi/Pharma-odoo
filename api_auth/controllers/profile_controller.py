import logging

from odoo import http

from ..services.profile_service import ProfileService
from ..utils.http_utils  import json_response, preflight_response, parse_json_body, require_session

_logger = logging.getLogger(__name__)


class ProfileController(http.Controller):

    @http.route('/api/me', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    def get_me(self, **kw):
        if http.request.httprequest.method == 'OPTIONS':
            return preflight_response()

        uid = require_session()
        if not uid:
            return json_response({'success': False, 'error': 'Not authenticated'}, status=401)

        try:
            result = ProfileService.get_profile(uid)
            return json_response(result, status=result.pop('status', 200))
        except Exception:
            _logger.exception("get_me error")
            return json_response({'success': False, 'error': 'Internal server error'}, status=500)

    @http.route('/api/profile/<int:user_id>', type='http', auth='public', methods=['PUT', 'OPTIONS'], csrf=False)
    def update_profile(self, user_id, **kw):
        if http.request.httprequest.method == 'OPTIONS':
            return preflight_response()

        uid = require_session()
        if not uid:
            return json_response({'success': False, 'error': 'Not authenticated'}, status=401)

        try:
            result = ProfileService.update_profile(uid, user_id, parse_json_body())
            return json_response(result, status=result.pop('status', 200))
        except Exception:
            _logger.exception("update_profile error")
            return json_response({'success': False, 'error': 'Internal server error'}, status=500)
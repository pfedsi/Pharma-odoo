import json
import logging

from odoo import http
from odoo.http import Response, request

from ..swagger.spec import build_spec
from ..utils.http_utils import cors_headers, preflight_response

_logger = logging.getLogger(__name__)


class DocsController(http.Controller):

    @http.route('/api/docs', type='http', auth='public')
    def swagger_ui(self, **kw):
        return request.render('api_auth.swagger_template')

    @http.route('/api/swagger.json', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    def swagger_spec(self, **kw):
        if request.httprequest.method == 'OPTIONS':
            return preflight_response()

        return Response(
            json.dumps(build_spec(), indent=2),
            content_type='application/json',
            status=200,
            headers=cors_headers(),
        )
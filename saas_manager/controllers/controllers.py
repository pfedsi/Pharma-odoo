from odoo import http
from odoo.http import request


class SaasPublicController(http.Controller):

    @http.route(
        '/saas/pharmacies',
        type='jsonrpc',
        auth='public',
        methods=['POST'],
        csrf=False
    )
    def list_pharmacies(self):
        pharmacies = request.env['saas.client'].sudo().search([])

        return [{
            'id': p.id,
            'name': p.name,
            'subdomain': p.subdomain,
            'db_name': p.db_name,
            'state': p.state,
        } for p in pharmacies]

    @http.route(
        '/saas/create',
        type='jsonrpc',
        auth='public',
        methods=['POST'],
        csrf=False
    )
    def create_pharmacy(self, **kwargs):
        vals = {
            'name': kwargs.get('name'),
            'subdomain': kwargs.get('subdomain'),
            'db_name': kwargs.get('db_name'),
            'admin_email': kwargs.get('admin_email'),
        }

        rec = request.env['saas.client'].sudo().create(vals)

        return {
            'status': 'ok',
            'id': rec.id,
            'name': rec.name,
        }
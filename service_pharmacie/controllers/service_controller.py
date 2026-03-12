from odoo import http
from odoo.http import request, Response
import json


class PharmacyServiceController(http.Controller):

    def _serialize_service(self, service):
        return {
            "id": service.id,
            "nom": service.nom,
            "description": service.description or "",
            "dure_estimee_par_defaut": service.dure_estimee_par_defaut or 0,
            "active": service.active,
        }

    def _json_response(self, data, status=200):
        return Response(
            json.dumps(data),
            status=status,
            content_type='application/json;charset=utf-8'
        )

    @http.route('/api/services', type='http', auth='public', methods=['GET'], csrf=False)
    def get_services(self, **kwargs):
        domain = []
        active = kwargs.get('active')

        if active is None:
            domain.append(('active', '=', True))
        else:
            active_bool = str(active).lower() in ('true', '1', 'yes')
            domain.append(('active', '=', active_bool))

        services = request.env['pharmacy.service'].sudo().search(domain)

        return self._json_response({
            "success": True,
            "services": [self._serialize_service(s) for s in services]
        }, 200)

    @http.route('/api/services/<int:service_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_service(self, service_id, **kwargs):
        service = request.env['pharmacy.service'].sudo().browse(service_id)

        if not service.exists():
            return self._json_response({
                "success": False,
                "message": "Service introuvable"
            }, 404)

        return self._json_response({
            "success": True,
            "service": self._serialize_service(service)
        }, 200)

    @http.route('/api/services', type='http', auth='user', methods=['POST'], csrf=False)
    def create_service(self, **kwargs):
        data = json.loads(request.httprequest.data or b"{}")

        if not data.get("nom"):
            return self._json_response({
                "success": False,
                "message": "Le champ nom est obligatoire"
            }, 400)

        service = request.env['pharmacy.service'].sudo().create({
            "nom": data.get("nom"),
            "description": data.get("description"),
            "dure_estimee_par_defaut": data.get("dure_estimee_par_defaut", 0),
            "active": data.get("active", True),
        })

        return self._json_response({
            "success": True,
            "service": self._serialize_service(service)
        }, 201)

    @http.route('/api/services/<int:service_id>', type='http', auth='user', methods=['PUT'], csrf=False)
    def update_service(self, service_id, **kwargs):
        service = request.env['pharmacy.service'].sudo().browse(service_id)
        if not service.exists():
            return self._json_response({
                "success": False,
                "message": "Service introuvable"
            }, 404)

        data = json.loads(request.httprequest.data or b"{}")
        vals = {}

        for field in ['nom', 'description', 'dure_estimee_par_defaut', 'active']:
            if field in data:
                vals[field] = data[field]

        service.write(vals)

        return self._json_response({
            "success": True,
            "service": self._serialize_service(service)
        }, 200)

    @http.route('/api/services/<int:service_id>', type='http', auth='user', methods=['DELETE'], csrf=False)
    def delete_service(self, service_id, **kwargs):
        service = request.env['pharmacy.service'].sudo().browse(service_id)
        if not service.exists():
            return self._json_response({
                "success": False,
                "message": "Service introuvable"
            }, 404)

        service.write({"active": False})

        return self._json_response({
            "success": True,
            "message": "Service désactivé"
        }, 200)
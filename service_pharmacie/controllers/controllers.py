# from odoo import http


# class Service(http.Controller):
#     @http.route('/service/service', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/service/service/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('service.listing', {
#             'root': '/service/service',
#             'objects': http.request.env['service.service'].search([]),
#         })

#     @http.route('/service/service/objects/<model("service.service"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('service.object', {
#             'object': obj
#         })


from odoo import models, fields

class PharmacyService(models.Model):
    _name = 'pharmacy.service'
    _description = 'Service'
    _rec_name = 'nom'

    nom = fields.Char(string="Nom", required=True)
    dure_estimee_par_defaut = fields.Integer(string="Durée estimée par défaut (min)")
    description = fields.Text(string="Description")
    active = fields.Boolean(string="Actif", default=True)
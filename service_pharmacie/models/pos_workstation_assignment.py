# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PharmacyPosWorkstationAssignment(models.Model):
    _name = "pharmacy.pos.workstation.assignment"
    _description = "Affectation employé POS"
    _rec_name = "display_name"
    _order = "poste_number, employee_id"

    display_name = fields.Char(compute="_compute_display_name", store=True)
    employee_id = fields.Many2one(
        "hr.employee",
        string="Employé",
        required=True,
        domain=[("user_id", "!=", False)],
    )
    user_id = fields.Many2one(
        "res.users",
        string="Utilisateur",
        related="employee_id.user_id",
        store=True,
        readonly=True,
    )
    pos_config_id = fields.Many2one(
        "pos.config",
        string="Point de vente",
        required=True,
    )
    poste_number = fields.Char(
        string="Numéro de poste de travail",
        required=True,
        default="1",
    )
    active = fields.Boolean(default=True)
    note = fields.Text(string="Note")

    @api.depends("employee_id", "pos_config_id", "poste_number")
    def _compute_display_name(self):
        for rec in self:
            parts = [
                rec.employee_id.name or _("Employé"),
                rec.pos_config_id.name or _("Point de vente"),
                _("Poste %s") % (rec.poste_number or "-"),
            ]
            rec.display_name = " - ".join(parts)

    @api.constrains("employee_id", "active")
    def _check_unique_active_employee(self):
        for rec in self:
            if not rec.active or not rec.employee_id:
                continue
            count = self.search_count([
                ("employee_id", "=", rec.employee_id.id),
                ("active", "=", True),
                ("id", "!=", rec.id),
            ])
            if count:
                raise ValidationError(
                    _("Cet employé possède déjà une affectation POS active.")
                )

    @api.constrains("pos_config_id", "poste_number", "active")
    def _check_unique_active_poste(self):
        for rec in self:
            if not rec.active or not rec.pos_config_id or not rec.poste_number:
                continue
            count = self.search_count([
                ("pos_config_id", "=", rec.pos_config_id.id),
                ("poste_number", "=", rec.poste_number),
                ("active", "=", True),
                ("id", "!=", rec.id),
            ])
            if count:
                raise ValidationError(
                    _("Ce numéro de poste est déjà affecté à ce point de vente.")
                )

    @api.constrains("employee_id")
    def _check_employee_has_user(self):
        for rec in self:
            if rec.employee_id and not rec.employee_id.user_id:
                raise ValidationError(
                    _("L'employé doit être lié à un utilisateur Odoo.")
                )

    def _sync_pos_access(self):
        pos_user_group = self.env.ref(
            "point_of_sale.group_pos_user",
            raise_if_not_found=False,
        )
        for rec in self.filtered("active"):
            if rec.user_id and pos_user_group:
                groups_field = (
                    "groups_id"
                    if "groups_id" in rec.user_id._fields
                    else "group_ids"
                    if "group_ids" in rec.user_id._fields
                    else False
                )
                if groups_field and pos_user_group not in rec.user_id[groups_field]:
                    rec.user_id.sudo().write({
                        groups_field: [(4, pos_user_group.id)],
                    })

            config = rec.pos_config_id.sudo()
            for field_name in ("employee_ids", "basic_employee_ids", "advanced_employee_ids"):
                if field_name in config._fields:
                    config.write({field_name: [(4, rec.employee_id.id)]})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_pos_access()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {"employee_id", "pos_config_id", "active"} & set(vals):
            self._sync_pos_access()
        return result

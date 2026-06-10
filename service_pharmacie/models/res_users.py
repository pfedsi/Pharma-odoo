# -*- coding: utf-8 -*-
from odoo import api, models


class ResUsers(models.Model):
    _inherit = "res.users"

    def _should_create_employee_from_user(self):
        self.ensure_one()
        if self.env.context.get("skip_auto_employee"):
            return False
        if self.share:
            return False
        public_user = self.env.ref("base.public_user", raise_if_not_found=False)
        if public_user and self.id == public_user.id:
            return False
        return True

    def _employee_vals_from_user(self):
        self.ensure_one()
        vals = {
            "name": self.name or self.login,
            "user_id": self.id,
        }
        if "work_email" in self.env["hr.employee"]._fields:
            vals["work_email"] = self.email or self.login
        if "company_id" in self.env["hr.employee"]._fields and self.company_id:
            vals["company_id"] = self.company_id.id
        if "resource_calendar_id" in self.env["hr.employee"]._fields and self.company_id.resource_calendar_id:
            vals["resource_calendar_id"] = self.company_id.resource_calendar_id.id
        return vals

    def _sync_employee_from_user(self):
        Employee = self.env["hr.employee"].sudo().with_context(active_test=False)
        for user in self.sudo():
            if not user._should_create_employee_from_user():
                continue

            employee = Employee.search([("user_id", "=", user.id)], limit=1)
            vals = user._employee_vals_from_user()
            if employee:
                update_vals = {}
                if vals.get("name") and employee.name != vals["name"]:
                    update_vals["name"] = vals["name"]
                if "work_email" in vals and employee.work_email != vals["work_email"]:
                    update_vals["work_email"] = vals["work_email"]
                if "company_id" in vals and employee.company_id.id != vals["company_id"]:
                    update_vals["company_id"] = vals["company_id"]
                if update_vals:
                    employee.with_context(skip_auto_employee=True).write(update_vals)
            else:
                Employee.with_context(skip_auto_employee=True).create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._sync_employee_from_user()
        return users

    def write(self, vals):
        result = super().write(vals)
        if {"name", "email", "login", "share", "company_id", "company_ids"} & set(vals):
            self._sync_employee_from_user()
        return result

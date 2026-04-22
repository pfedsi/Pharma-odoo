from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    # ----------------------------------------------------------------
    # Personal Information
    # ----------------------------------------------------------------
    first_name = fields.Char(string='First Name', tracking=True)
    last_name = fields.Char(string='Last Name', tracking=True)
    cin = fields.Char(string='CIN', size=8)
    birth_date = fields.Date(string='Date of Birth')
    phone_number = fields.Char(string='Phone Number')

    # ----------------------------------------------------------------
    # Role
    # ----------------------------------------------------------------
    user_role = fields.Selection(
        selection=[
            ('assistant', 'Assistant'),
            ('pharmacien', 'Pharmacien'),
            ('client', 'Client'),
        ],
        string='Role',
        default='client',
        required=True,
        tracking=True,
    )

    # ----------------------------------------------------------------
    # OTP / Password Reset
    # ----------------------------------------------------------------
    reset_otp_code = fields.Char(
        string='Reset OTP Code',
        copy=False,
        groups='base.group_system',
    )
    reset_otp_expiration = fields.Datetime(
        string='OTP Expiration',
        copy=False,
        groups='base.group_system',
    )

    # ----------------------------------------------------------------
    # Computed full name sync
    # ----------------------------------------------------------------
    def _sync_name(self):
        for user in self:
            parts = [user.first_name or '', user.last_name or '']
            full = ' '.join(p.strip() for p in parts if p.strip())
            if full:
                user.name = full
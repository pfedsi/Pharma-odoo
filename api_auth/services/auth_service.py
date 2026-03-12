import logging
import random
import time
from datetime import timedelta
from odoo import SUPERUSER_ID
import requests as http_requests

from odoo import fields
from odoo.exceptions import AccessDenied
from odoo.http import request

_logger = logging.getLogger(__name__)

_GOOGLE_CLIENT_ID = '642092208722-1efjare704tbv1r7rreqpstf4iuhu46d.apps.googleusercontent.com'
_OTP_TTL_MINUTES  = 3


class AuthService:

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    @staticmethod
    def register(data: dict) -> dict:
        email      = (data.get('email') or '').strip().lower()
        password   = data.get('password', '').strip()
        first_name = (data.get('first_name') or '').strip()
        last_name  = (data.get('last_name') or '').strip()

        if not email or not password:
            return {'success': False, 'error': 'Email and password are required', 'status': 400}
        if not first_name or not last_name:
            return {'success': False, 'error': 'First name and last name are required', 'status': 400}

        Users = request.env['res.users'].sudo()
        if Users.search([('login', '=', email)], limit=1):
            return {'success': False, 'error': 'An account with this email already exists', 'status': 409}

        user = Users.create({
            'name':         f'{first_name} {last_name}',
            'login':        email,
            'password':     password,
            'first_name':   first_name,
            'last_name':    last_name,
            'cin':          data.get('cin') or '',
            'birth_date':   data.get('birth_date') or False,
            'phone_number': data.get('phone_number') or '',
            'user_role':    'client',
        })
        return {'success': True, 'user_id': user.id, 'message': 'Registration successful', 'status': 201}

    # ------------------------------------------------------------------
    # Login / logout
    # ------------------------------------------------------------------

    @staticmethod
    def login(data: dict) -> dict:
        try:
            request.session.logout(keep_db=True)
        except Exception:
            pass

        login_value = (
            data.get('login') or data.get('email') or data.get('username') or ''
        ).strip().lower()
        password = data.get('password', '').strip()

        if not login_value or not password:
            return {'success': False, 'error': 'Login and password are required', 'status': 400}

        try:
            uid = request.env['res.users'].sudo()._login(
                {'type': 'password', 'login': login_value, 'password': password},
                request.httprequest.environ or {},
            )
            if isinstance(uid, dict):
                uid = uid.get('uid') or uid.get('user_id') or uid.get('id')
        except AccessDenied:
            return {'success': False, 'error': 'Invalid credentials', 'status': 401}

        if not uid:
            return {'success': False, 'error': 'Authentication failed', 'status': 401}

        uid = int(uid)
        request.session.uid   = uid
        request.session.login = login_value

        user = request.env['res.users'].sudo().browse(uid)
        request.session.session_token = user._compute_session_token(request.session.sid)
        token = f"{uid}:{request.session.sid}"

        return {
            'success': True,
            'session_id': token,
            'status': 200,
            'user': {
                'id':         user.id,
                'email':      user.login,
                'name':       user.name,
                'first_name': user.first_name or '',
                'last_name':  user.last_name  or '',
                'user_role':  user.user_role  or 'client',
            },
        }

    @staticmethod
    def logout() -> dict:
        try:
            request.session.logout()
        except Exception:
            pass
        return {'success': True, 'status': 200}

    # ------------------------------------------------------------------
    # Google OAuth2
    # ------------------------------------------------------------------

    @staticmethod
    def google_login(data: dict) -> dict:
        try:
            request.session.logout(keep_db=True)
        except Exception:
            pass

        id_token = (data.get('id_token') or '').strip()
        if not id_token:
            return {'success': False, 'error': 'ID token is required', 'status': 400}

        resp = http_requests.get(
            'https://oauth2.googleapis.com/tokeninfo',
            params={'id_token': id_token},
            timeout=10,
        )
        if resp.status_code != 200:
            return {'success': False, 'error': 'Invalid ID token', 'status': 401}

        token_data = resp.json()

        if token_data.get('aud') != _GOOGLE_CLIENT_ID:
            return {'success': False, 'error': 'Token audience mismatch', 'status': 401}
        if int(token_data.get('exp', 0)) < int(time.time()):
            return {'success': False, 'error': 'Token has expired', 'status': 401}
        if token_data.get('email_verified') != 'true':
            return {'success': False, 'error': 'Email address not verified', 'status': 401}

        email = (token_data.get('email') or '').strip().lower()
        if not email:
            return {'success': False, 'error': 'Email not provided by Google', 'status': 400}

        Users = request.env['res.users'].with_user(SUPERUSER_ID).sudo()        
        user  = Users.search([('login', '=', email)], limit=1)
        if not user:
            first_name = (token_data.get('given_name') or '').strip()
            last_name = (token_data.get('family_name') or '').strip()
            full_name = (token_data.get('name') or '').strip()

            if not first_name and full_name:
                parts = full_name.split(' ', 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else 'Google'

            if not first_name:
                first_name = 'Google'
            if not last_name:
                last_name = 'User'
            company = request.env['res.company'].with_user(SUPERUSER_ID).sudo().search([], limit=1)
            if not company:
                return {'success': False, 'error': 'No company found', 'status': 500}
        
            _logger.error("Google create user company_id=%s", company.id)
            user = Users.create({
                'name': f'{first_name} {last_name}'.strip(),
                'login': email,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'cin': '',
                'birth_date': False,
                'phone_number': '',
                'user_role': 'client',
                'active': True,
                'company_id': company.id,
                'company_ids': [(6, 0, [company.id])],

            })



        request.session.uid           = user.id
        request.session.login         = user.login
        request.session.session_token = user._compute_session_token(request.session.sid)
        Users.browse(user.id)._update_last_login()

        token = f"{user.id}:{request.session.sid}"

        return {
            'success':    True,
            'message':    'Login successful',
            'session_id': token,
            'status':     200,
            'user': {
                'id':    user.id,
                'name':  user.name,
                'email': user.email,
                'role':  user.user_role,
            },
        }

    # ------------------------------------------------------------------
    # Password reset (OTP flow)
    # ------------------------------------------------------------------

    @staticmethod
    def send_reset_code(data: dict) -> dict:
        login_value = (data.get('login') or data.get('email') or '').strip().lower()
        if not login_value:
            return {'success': False, 'error': 'Login is required', 'status': 400}

        user = request.env['res.users'].sudo().search(
            [('login', '=', login_value)], limit=1)
        if not user:
            # Silent success to avoid user enumeration
            return {'success': True, 'message': 'If that account exists, a code has been sent.', 'status': 200}

        email = user.email or user.partner_id.email or user.login
        if not email or '@' not in email:
            return {'success': False, 'error': 'No valid email address on file', 'status': 400}

        otp    = str(random.randint(100_000, 999_999))
        expiry = fields.Datetime.now() + timedelta(minutes=_OTP_TTL_MINUTES)
        user.sudo().write({'reset_otp_code': otp, 'reset_otp_expiration': expiry})

        request.env['mail.mail'].sudo().create({
            'subject':   'Your Password Reset Code',
            'email_to':  email,
            'body_html': (
                f'<p>Hello {user.name},</p>'
                f'<p>Your verification code is:</p>'
                f'<h2 style="letter-spacing:4px">{otp}</h2>'
                f'<p>This code expires in {_OTP_TTL_MINUTES} minutes. '
                f'If you did not request this, please ignore this email.</p>'
            ),
        }).send()

        return {'success': True, 'message': f'Code sent. Valid for {_OTP_TTL_MINUTES} minutes.', 'status': 200}

    @staticmethod
    def verify_reset_code(data: dict) -> dict:
        login_value = (data.get('login') or '').strip().lower()
        code        = (data.get('code') or '').strip()

        if not login_value or not code:
            return {'success': False, 'error': 'Login and code are required', 'status': 400}

        user = request.env['res.users'].sudo().search(
            [('login', '=', login_value)], limit=1)

        if not user or not user.reset_otp_code:
            return {'success': False, 'error': 'Invalid or expired code', 'status': 400}
        if not user.reset_otp_expiration or fields.Datetime.now() > user.reset_otp_expiration:
            return {'success': False, 'error': 'Code has expired', 'status': 410}
        if user.reset_otp_code != code:
            return {'success': False, 'error': 'Incorrect code', 'status': 401}

        user.sudo().write({'reset_otp_code': False, 'reset_otp_expiration': False})
        return {'success': True, 'message': 'Code verified successfully', 'status': 200}

    @staticmethod
    def reset_password_with_code(data: dict) -> dict:
        login_value  = (data.get('login') or '').strip().lower()
        code         = (data.get('code') or '').strip()
        new_password = data.get('new_password', '').strip()

        if not login_value or not code or not new_password:
            return {'success': False, 'error': 'login, code and new_password are required', 'status': 400}

        user = request.env['res.users'].sudo().search(
            [('login', '=', login_value)], limit=1)

        if not user:
            return {'success': False, 'error': 'User not found', 'status': 404}
        if not user.reset_otp_code or user.reset_otp_code != code:
            return {'success': False, 'error': 'Invalid code', 'status': 400}
        if not user.reset_otp_expiration or fields.Datetime.now() > user.reset_otp_expiration:
            return {'success': False, 'error': 'Code has expired', 'status': 410}

        user.sudo().write({
            'password':             new_password,
            'reset_otp_code':       False,
            'reset_otp_expiration': False,
        })
        return {'success': True, 'message': 'Password updated successfully', 'status': 200}
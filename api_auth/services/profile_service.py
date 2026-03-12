import logging

from odoo.http import request

_logger = logging.getLogger(__name__)


class ProfileService:

    @staticmethod
    def get_profile(uid: int) -> dict:
        user = request.env['res.users'].sudo().browse(uid)
        if not user.exists():
            return {'success': False, 'error': 'User not found', 'status': 404}

        return {
            'success': True,
            'status':  200,
            'profile': {
                'id':           user.id,
                'email':        user.login,
                'first_name':   user.first_name or '',
                'last_name':    user.last_name  or '',
                'cin':          user.cin        or '',
                'birth_date':   str(user.birth_date) if user.birth_date else None,
                'phone_number': user.phone_number   or '',
                'role':         user.user_role      or 'client',
            },
        }

    @staticmethod
    def update_profile(uid: int, user_id: int, data: dict) -> dict:
        if uid != user_id:
            return {'success': False, 'error': 'Forbidden', 'status': 403}

        user = request.env['res.users'].sudo().browse(user_id)
        if not user.exists():
            return {'success': False, 'error': 'User not found', 'status': 404}

        _ALLOWED_FIELDS = {'first_name', 'last_name', 'cin', 'birth_date', 'phone_number'}
        values = {k: data[k] for k in _ALLOWED_FIELDS if k in data}

        if values:
            user.sudo().write(values)
            user._sync_name()

        return {'success': True, 'message': 'Profile updated successfully', 'status': 200}
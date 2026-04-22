# -*- coding: utf-8 -*-
import json
import logging
from odoo.http import request

_logger = logging.getLogger(__name__)

PANIER_SESSION_KEY = "qpharma_panier"


def load_panier():
    raw = request.session.get(PANIER_SESSION_KEY)
    if raw:
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            _logger.warning("Panier session invalide, réinitialisation.")
    return []


def save_panier(lines):
    request.session[PANIER_SESSION_KEY] = lines
    request.session.modified = True
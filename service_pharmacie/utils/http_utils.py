# -*- coding: utf-8 -*-
import json
from odoo.http import request


def get_json_payload(kwargs=None):
    if kwargs and isinstance(kwargs, dict) and kwargs:
        return kwargs

    try:
        raw = request.httprequest.data
        if raw:
            data = json.loads(raw.decode("utf-8"))
            if isinstance(data, dict):
                if "params" in data and isinstance(data["params"], dict):
                    return data["params"]
                return data
    except Exception:
        pass

    return {}
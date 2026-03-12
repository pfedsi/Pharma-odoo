from . import models, controllers

from ..api_auth.swagger.registry import register_paths, register_schemas
from .swagger.service_spec import SERVICE_PATHS, SERVICE_SCHEMAS

register_paths('service_pharmacie', SERVICE_PATHS)
register_schemas('service_pharmacie', SERVICE_SCHEMAS)
from . import models, controllers

from ..api_auth.swagger.registry import register_paths
from .swagger.service_spec import SERVICE_PATHS
register_paths('service_pharmacie', SERVICE_PATHS)
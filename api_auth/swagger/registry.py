# api_auth/swagger/registry.py

_spec_contributors = {}

def register_paths(module_name: str, paths: dict):
    """Enregistre les paths OpenAPI d'un module."""
    _spec_contributors[module_name] = paths

def get_all_paths() -> dict:
    """Retourne tous les paths fusionnés."""
    merged = {}
    for paths in _spec_contributors.values():
        merged.update(paths)
    return merged
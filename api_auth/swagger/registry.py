# api_auth/swagger/registry.py

_path_contributors = {}
_schema_contributors = {}

def register_paths(module_name: str, paths: dict):
    """Enregistre les paths OpenAPI d'un module."""
    _path_contributors[module_name] = paths

def register_schemas(module_name: str, schemas: dict):
    """Enregistre les schemas OpenAPI d'un module."""
    _schema_contributors[module_name] = schemas

def get_all_paths() -> dict:
    """Retourne tous les paths fusionnés."""
    merged = {}
    for paths in _path_contributors.values():
        merged.update(paths)
    return merged

def get_all_schemas() -> dict:
    """Retourne tous les schemas fusionnés."""
    merged = {}
    for schemas in _schema_contributors.values():
        merged.update(schemas)
    return merged
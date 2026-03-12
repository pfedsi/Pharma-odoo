# service_pharmacie/swagger/service_spec.py

SERVICE_PATHS = {
    "/api/services": {
        "get": {
            "summary": "Lister tous les services actifs",
            "tags": ["Services"],
            "parameters": [
                {
                    "name": "active",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "boolean"},
                    "description": "Filtrer par statut actif/inactif"
                }
            ],
            "responses": {
                "200": {
                    "description": "Liste des services",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {"type": "boolean"},
                                    "services": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/PharmacyService"}
                                    }
                                }
                            }
                        }
                    }
                },
                "500": {"$ref": "#/components/responses/InternalError"},
            },
        },
        "post": {
            "summary": "Créer un nouveau service",
            "tags": ["Services"],
            "security": [{"sessionCookie": []}, {"sessionHeader": []}],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["nom"],
                            "properties": {
                                "nom":                      {"type": "string"},
                                "description":              {"type": "string"},
                                "dure_estimee_par_defaut":  {"type": "integer", "description": "Durée en minutes"},
                                "active":                   {"type": "boolean", "default": True},
                            }
                        }
                    }
                }
            },
            "responses": {
                "201": {"description": "Service créé"},
                "400": {"description": "Données invalides"},
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "500": {"$ref": "#/components/responses/InternalError"},
            },
        }
    },
    "/api/services/{service_id}": {
        "get": {
            "summary": "Détail d'un service",
            "tags": ["Services"],
            "parameters": [
                {"name": "service_id", "in": "path", "required": True, "schema": {"type": "integer"}}
            ],
            "responses": {
                "200": {
                    "description": "Service trouvé",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {"type": "boolean"},
                                    "service": {"$ref": "#/components/schemas/PharmacyService"}
                                }
                            }
                        }
                    }
                },
                "404": {"$ref": "#/components/responses/NotFound"},
            },
        },
        "put": {
            "summary": "Modifier un service",
            "tags": ["Services"],
            "security": [{"sessionCookie": []}, {"sessionHeader": []}],
            "parameters": [
                {"name": "service_id", "in": "path", "required": True, "schema": {"type": "integer"}}
            ],
            "requestBody": {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "nom":                     {"type": "string"},
                                "description":             {"type": "string"},
                                "dure_estimee_par_defaut": {"type": "integer"},
                                "active":                  {"type": "boolean"},
                            }
                        }
                    }
                }
            },
            "responses": {
                "200": {"description": "Service modifié"},
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "404": {"$ref": "#/components/responses/NotFound"},
                "500": {"$ref": "#/components/responses/InternalError"},
            },
        },
        "delete": {
            "summary": "Désactiver un service (soft delete)",
            "tags": ["Services"],
            "security": [{"sessionCookie": []}, {"sessionHeader": []}],
            "parameters": [
                {"name": "service_id", "in": "path", "required": True, "schema": {"type": "integer"}}
            ],
            "responses": {
                "200": {"description": "Service désactivé"},
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "404": {"$ref": "#/components/responses/NotFound"},
            },
        }
    },
}

SERVICE_SCHEMAS = {
    "PharmacyService": {
        "type": "object",
        "properties": {
            "id":                      {"type": "integer", "example": 1},
            "nom":                     {"type": "string",  "example": "Vaccination"},
            "description":             {"type": "string",  "example": "Service de vaccination..."},
            "dure_estimee_par_defaut": {"type": "integer", "example": 30, "description": "Durée en minutes"},
            "active":                  {"type": "boolean", "example": True},
        }
    }
}

from .registry import get_all_paths

_SERVER_URL = "https://demopharma.eprswarm.com"

# ---------------------------------------------------------------------------
# Reusable schema components
# ---------------------------------------------------------------------------

_COMPONENTS = {
    "schemas": {
        "Error": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean", "example": False},
                "error":   {"type": "string",  "example": "Error message"},
            },
        },
        "Success": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean", "example": True},
                "message": {"type": "string",  "example": "Operation successful"},
            },
        },
        "UserProfile": {
            "type": "object",
            "properties": {
                "id":           {"type": "integer", "example": 42},
                "email":        {"type": "string",  "format": "email"},
                "first_name":   {"type": "string",  "example": "Jane"},
                "last_name":    {"type": "string",  "example": "Doe"},
                "cin":          {"type": "string",  "example": "12345678"},
                "birth_date":   {"type": "string",  "format": "date", "nullable": True},
                "phone_number": {"type": "string",  "example": "+21698000000"},
                "role":         {"type": "string",  "example": "client"},
            },
        },
        "SessionResponse": {
            "type": "object",
            "properties": {
                "success":    {"type": "boolean"},
                "session_id": {"type": "string", "example": "42:abc123sid"},
                "user":       {"$ref": "#/components/schemas/UserProfile"},
            },
        },
    },
    "responses": {
        "Unauthorized": {
            "description": "Authentication required or credentials invalid",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
        },
        "Forbidden": {
            "description": "Access denied",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
        },
        "NotFound": {
            "description": "Resource not found",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
        },
        "InternalError": {
            "description": "Internal server error",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
        },
    },
}

# ---------------------------------------------------------------------------
# Path definitions grouped by domain
# ---------------------------------------------------------------------------

_AUTH_PATHS = {
    "/api/auth/register": {
        "post": {
            "summary": "Register a new client account",
            "tags": ["Authentication"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["email", "password", "first_name", "last_name"],
                            "properties": {
                                "email":        {"type": "string", "format": "email"},
                                "password":     {"type": "string", "minLength": 6},
                                "first_name":   {"type": "string"},
                                "last_name":    {"type": "string"},
                                "cin":          {"type": "string"},
                                "birth_date":   {"type": "string", "format": "date"},
                                "phone_number": {"type": "string"},
                            },
                        }
                    }
                },
            },
            "responses": {
                "201": {
                    "description": "Account created successfully",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {"type": "boolean"},
                                    "user_id": {"type": "integer"},
                                    "message": {"type": "string"},
                                },
                            }
                        }
                    },
                },
                "400": {"description": "Validation error",             "$ref": "#/components/responses/Unauthorized"},
                "409": {"description": "Email already registered"},
                "500": {"$ref": "#/components/responses/InternalError"},
            },
        }
    },
    "/api/auth/login": {
        "post": {
            "summary": "Authenticate and open a session",
            "tags": ["Authentication"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["login", "password"],
                            "properties": {
                                "login":    {"type": "string", "description": "Email or username"},
                                "password": {"type": "string"},
                            },
                        }
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "Login successful",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/SessionResponse"},
                        }
                    },
                },
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "500": {"$ref": "#/components/responses/InternalError"},
            },
        }
    },
    "/api/auth/logout": {
        "post": {
            "summary": "Terminate the current session",
            "tags": ["Authentication"],
            "responses": {
                "200": {
                    "description": "Logged out",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Success"},
                        }
                    },
                },
            },
        }
    },
    "/api/auth/google": {
        "post": {
            "summary": "Sign in with Google OAuth2",
            "tags": ["Authentication"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["id_token"],
                            "properties": {
                                "id_token": {"type": "string", "description": "Google ID token"},
                            },
                        }
                    }
                },
            },
            "responses": {
                "200": {
                    "description": "Google login successful",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/SessionResponse"},
                        }
                    },
                },
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "500": {"$ref": "#/components/responses/InternalError"},
            },
        }
    },
}

_PASSWORD_RESET_PATHS = {
    "/api/auth/send_reset_code": {
        "post": {
            "summary": "Send a one-time password reset code by email",
            "tags": ["Password Reset"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["login"],
                            "properties": {
                                "login": {"type": "string", "description": "Account email / login"},
                            },
                        }
                    }
                },
            },
            "responses": {
                "200": {"description": "Code sent (or silently ignored if account not found)"},
                "400": {"description": "Missing or invalid login"},
                "500": {"$ref": "#/components/responses/InternalError"},
            },
        }
    },
    "/api/auth/verify_reset_code": {
        "post": {
            "summary": "Verify a one-time password reset code",
            "tags": ["Password Reset"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["login", "code"],
                            "properties": {
                                "login": {"type": "string"},
                                "code":  {"type": "string", "minLength": 6, "maxLength": 6},
                            },
                        }
                    }
                },
            },
            "responses": {
                "200": {"description": "Code is valid"},
                "400": {"description": "Invalid or expired code"},
                "401": {"description": "Incorrect code"},
                "410": {"description": "Code has expired"},
                "500": {"$ref": "#/components/responses/InternalError"},
            },
        }
    },
    "/api/auth/reset_password_with_code": {
        "post": {
            "summary": "Reset password using a verified OTP code",
            "tags": ["Password Reset"],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["login", "code", "new_password"],
                            "properties": {
                                "login":        {"type": "string"},
                                "code":         {"type": "string"},
                                "new_password": {"type": "string", "minLength": 6},
                            },
                        }
                    }
                },
            },
            "responses": {
                "200": {"description": "Password updated"},
                "400": {"description": "Invalid code or missing fields"},
                "404": {"$ref": "#/components/responses/NotFound"},
                "410": {"description": "Code has expired"},
                "500": {"$ref": "#/components/responses/InternalError"},
            },
        }
    },
}

_PROFILE_PATHS = {
    "/api/me": {
        "get": {
            "summary": "Get the authenticated user's profile",
            "tags": ["Profile"],
            "security": [{"sessionCookie": []}, {"sessionHeader": []}],
            "responses": {
                "200": {
                    "description": "Profile data",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "success": {"type": "boolean"},
                                    "profile": {"$ref": "#/components/schemas/UserProfile"},
                                },
                            }
                        }
                    },
                },
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "404": {"$ref": "#/components/responses/NotFound"},
            },
        }
    },
    "/api/profile/{user_id}": {
        "put": {
            "summary": "Update a user profile",
            "tags": ["Profile"],
            "security": [{"sessionCookie": []}, {"sessionHeader": []}],
            "parameters": [
                {
                    "name": "user_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "integer"},
                }
            ],
            "requestBody": {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "first_name":   {"type": "string"},
                                "last_name":    {"type": "string"},
                                "cin":          {"type": "string"},
                                "birth_date":   {"type": "string", "format": "date"},
                                "phone_number": {"type": "string"},
                            },
                        }
                    }
                }
            },
            "responses": {
                "200": {"description": "Profile updated"},
                "401": {"$ref": "#/components/responses/Unauthorized"},
                "403": {"$ref": "#/components/responses/Forbidden"},
                "404": {"$ref": "#/components/responses/NotFound"},
                "500": {"$ref": "#/components/responses/InternalError"},
            },
        }
    },
}

# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_spec() -> dict:
    """Return the complete OpenAPI 3.0 specification as a plain dict."""
    return {
        "openapi": "3.0.0",
        "info": {
            "title":       "Pharmacie API",
            "version":     "1.0.0",
            "description": "REST API for pharmacy management",
            "contact": {
                "name":  "EPR Swarm",
                "url":   "https://demopharma.eprswarm.com",
            },
        },
        "servers": [
            {"url": _SERVER_URL, "description": "Production server"},
            {"url": "http://localhost:8069", "description": "Local development"},
        ],
        "components": _COMPONENTS,
        "paths": {
            **_AUTH_PATHS,
            **_PASSWORD_RESET_PATHS,
            **_PROFILE_PATHS,
            **get_all_paths(),  

        },
    }
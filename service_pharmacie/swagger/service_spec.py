# -*- coding: utf-8 -*-
"""
Swagger / OpenAPI 3.0 — Pharmacy Queue API
"""

# ── Security scheme ───────────────────────────────────────────────────────────

SERVICE_SECURITY_SCHEMES = {
    "cookieAuth": {
        "type": "apiKey",
        "in": "cookie",
        "name": "session_id",
        "description": "Session Odoo. Obtenue via POST /web/session/authenticate.",
    }
}

# ── Schemas réutilisables ─────────────────────────────────────────────────────

SERVICE_SCHEMAS = {

    # ── Horaires ──────────────────────────────────────────────────────────────

    "HoraireJour": {
        "type": "object",
        "properties": {
            "jour_index": {
                "type": "string",
                "enum": ["0", "1", "2", "3", "4", "5", "6"],
                "description": "0 = Lundi, 6 = Dimanche",
                "example": "0",
            },
            "jour":      {"type": "string", "example": "Lundi"},
            "actif":     {"type": "boolean", "description": "false = fermé ce jour"},
            "ouverture": {
                "type": "string", "nullable": True, "example": "08:00",
                "description": "null si actif=false",
            },
            "fermeture": {
                "type": "string", "nullable": True, "example": "17:00",
                "description": "null si actif=false",
            },
            "overnight": {
                "type": "boolean", "example": False,
                "description": "true si l'horaire traverse minuit (fermeture < ouverture)",
            },
        },
        "required": ["jour_index", "jour", "actif"],
    },

    "HoraireParDefaut": {
        "type": "object",
        "properties": {
            "ouverture":          {"type": "string",  "example": "08:00"},
            "fermeture":          {"type": "string",  "example": "18:00"},
            "intervalle_minutes": {"type": "integer", "example": 30},
            "overnight": {
                "type": "boolean", "example": False,
                "description": "true si fermeture < ouverture (pharmacie de nuit)",
            },
        },
        "required": ["ouverture", "fermeture", "intervalle_minutes"],
    },

    "ServiceHoraires": {
        "type": "object",
        "properties": {
            "service_id":          {"type": "integer", "example": 3},
            "nom":                 {"type": "string",  "example": "Ordonnances"},
            "horaires_par_defaut": {"$ref": "#/components/schemas/HoraireParDefaut"},
            "horaires": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/HoraireJour"},
                "description": (
                    "Jours configurés explicitement (triés lundi→dimanche). "
                    "Les jours absents utilisent horaires_par_defaut."
                ),
            },
        },
        "required": ["service_id", "nom", "horaires_par_defaut", "horaires"],
    },

    # ── Service ───────────────────────────────────────────────────────────────

    "Service": {
        "type": "object",
        "properties": {
            "id":                   {"type": "integer", "example": 3},
            "nom":                  {"type": "string",  "example": "Ordonnances"},
            "description":          {"type": "string",  "example": "Dépôt et retrait d'ordonnances"},
            "duree_estimee":        {
                "type": "integer", "example": 15,
                "description": "Durée estimée par client (minutes)",
            },
            "queue_id":             {"type": "integer", "nullable": True, "example": 2},
            "en_attente":           {"type": "integer", "example": 4},
            "temps_attente_estime": {
                "type": "integer", "example": 60,
                "description": "Temps d'attente estimé en minutes",
            },
            "heure_ouverture":      {"type": "string",  "example": "08:00"},
            "heure_fermeture":      {"type": "string",  "example": "18:00"},
            "overnight": {
                "type": "boolean", "example": False,
                "description": "true si pharmacie de nuit (fermeture < ouverture)",
            },
            "duree_creneau": {
                "type": "integer", "example": 30,
                "description": "Intervalle entre deux réservations (minutes)",
            },
            "pharmacie_adresse":  {"type": "string",  "example": "12 Rue Ibn Khaldoun, Tunis"},
            "pharmacie_lat":      {"type": "number",  "format": "double", "example": 36.8065},
            "pharmacie_lon":      {"type": "number",  "format": "double", "example": 10.1815},
            "rayon_validation": {
                "type": "integer", "example": 200,
                "description": "Rayon GPS (m) pour valider 'Je suis là'",
            },
            "horaires": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/HoraireJour"},
                "description": "Horaires journaliers configurés pour ce service",
            },
        },
        "required": ["id", "nom"],
    },

    # ── Slot ──────────────────────────────────────────────────────────────────

    "Slot": {
        "type": "object",
        "properties": {
            "time": {
                "type": "string", "example": "09:00",
                "description": "Heure du créneau (HH:MM)",
            },
            "datetime": {
                "type": "string", "format": "date-time",
                "example": "2026-03-17T09:00:00",
            },
            "available": {"type": "boolean", "example": True},
        },
        "required": ["time", "datetime", "available"],
    },

    "SlotsResponse": {
        "type": "object",
        "properties": {
            "service_id":      {"type": "integer", "example": 3},
            "nom":             {"type": "string",  "example": "Ordonnances"},
            "date":            {"type": "string",  "format": "date", "example": "2026-03-17"},
            "heure_ouverture": {"type": "string",  "example": "08:00"},
            "heure_fermeture": {"type": "string",  "example": "18:00"},
            "overnight":       {"type": "boolean", "example": False},
            "duree_creneau":   {"type": "integer", "example": 30},
            "slots": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/Slot"},
            },
        },
        "required": ["service_id", "date", "slots"],
    },

    # ── Queue ─────────────────────────────────────────────────────────────────
    # ✅ CORRIGÉ : ajout display_name, service, position_client_virtuel
    # ✅ CORRIGÉ : nb_en_attente (nom réel du champ) au lieu de nb_en_attente
    #             (le vieux schema utilisait "nb_en_attente" OK, mais "name" seul
    #              ne reflétait pas ce que le service retourne réellement)

    "Queue": {
        "type": "object",
        "properties": {
            "id": {
                "type": "integer", "example": 2,
            },
            "name": {
                "type": "string", "example": "File – Ordonnances",
                "description": "Nom brut de la file (champ stocké)",
            },
            "display_name": {
                "type": "string",
                "example": "Ordonnances – File – Ordonnances",
                "description": "Nom affiché (computed : 'Service – name')",
            },
            "service_id": {
                "type": "integer", "nullable": True, "example": 3,
                "description": "ID du service associé. null si aucun service.",
            },
            "service": {
                "type": "string", "nullable": True, "example": "Ordonnances",
                "description": "Nom du service associé. null si aucun service.",
            },
            "nb_en_attente": {
                "type": "integer", "example": 4,
                "description": "Nombre de tickets en statut 'en_attente' dans cette file.",
            },
            "temps_attente_estime": {
                "type": "integer", "example": 60,
                "description": "Temps d'attente estimé en minutes (nb_en_attente × durée_estimée).",
            },
            "position_client_virtuel": {
                "type": "integer", "example": 2,
                "description": (
                    "Position d'insertion du client virtuel dans la file "
                    "lors de la confirmation de présence (« Je suis là »). "
                    "Minimum 1."
                ),
            },
        },
        "required": ["id", "name", "display_name", "nb_en_attente", "temps_attente_estime"],
    },

    # ── QueueRef (embedded dans Reservation) ─────────────────────────────────
    # ✅ NOUVEAU : objet allégé utilisé dans les réservations

    "QueueRef": {
        "type": "object",
        "nullable": True,
        "description": "File d'attente active du service (null si aucune file active)",
        "properties": {
            "id":                   {"type": "integer", "example": 2},
            "nom":                  {"type": "string",  "example": "Ordonnances – File – Ordonnances"},
            "en_attente":           {"type": "integer", "example": 4},
            "temps_attente_estime": {
                "type": "integer", "example": 60,
                "description": "Temps d'attente estimé en minutes",
            },
        },
        "required": ["id", "nom", "en_attente", "temps_attente_estime"],
    },

    # ── Ticket ────────────────────────────────────────────────────────────────

    "TicketRef": {
        "type": "object",
        "nullable": True,
        "description": "Référence courte au ticket (présent uniquement si statut=arrive)",
        "properties": {
            "id":       {"type": "integer", "example": 42},
            "numero":   {"type": "string",  "example": "A-007"},
            "etat": {
                "type": "string",
                "enum": ["en_attente", "appele", "termine", "annule"],
                "example": "en_attente",
            },
            "position": {"type": "integer", "example": 3},
        },
        "required": ["id", "numero", "etat", "position"],
    },

    # ✅ CORRIGÉ : ajout queue_id, heure_fin, reservation_id
    #             pour correspondre à TicketController.get_ticket / list_my_tickets
    "Ticket": {
        "type": "object",
        "properties": {
            "id":     {"type": "integer", "example": 42},
            "numero": {"type": "string",  "example": "File-001"},
            "etat": {
                "type": "string",
                "enum": ["en_attente", "appele", "termine", "annule"],
                "example": "en_attente",
            },
            "position": {
                "type": "integer", "example": 3,
                "description": "Position dans la file (parmi les tickets en_attente)",
            },
            "type_ticket": {
                "type": "string",
                "enum": ["physique", "virtuel"],
                "example": "virtuel",
            },
            "service": {
                "type": "string", "nullable": True, "example": "Ordonnances",
                "description": "Nom du service associé à la file",
            },
            "queue_id": {
                "type": "integer", "nullable": True, "example": 1,
                "description": "ID de la file d'attente",
            },
            "temps_attente_estime": {
                "type": "integer", "example": 45,
                "description": "Minutes d'attente estimées",
            },
            "heure_creation": {
                "type": "string", "format": "date-time",
                "example": "2026-03-18T10:00:00",
            },
            "heure_appel": {
                "type": "string", "format": "date-time", "nullable": True,
                "example": None,
                "description": "Heure à laquelle le ticket a été appelé. null si pas encore appelé.",
            },
            "heure_fin": {
                "type": "string", "format": "date-time", "nullable": True,
                "example": None,
                "description": "Heure de fin de service. null si pas encore terminé.",
            },
            "reservation_id": {
                "type": "integer", "nullable": True, "example": 5,
                "description": "ID de la réservation liée. null pour les tickets physiques.",
            },
        },
        "required": ["id", "numero", "etat", "position", "type_ticket", "heure_creation"],
    },

    # ✅ NOUVEAU : réponse pour GET /api/pharmacy/tickets/mine
    "TicketsListResponse": {
        "type": "object",
        "properties": {
            "tickets": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/Ticket"},
            },
            "total": {
                "type": "integer", "example": 2,
                "description": "Nombre total de tickets retournés",
            },
        },
        "required": ["tickets", "total"],
    },

    # ── Réservation ───────────────────────────────────────────────────────────
    # ✅ CORRIGÉ : queue est maintenant un objet QueueRef (plus une string)
    # ✅ AJOUT   : fenetre_je_suis_la pour activer/désactiver le bouton côté mobile

    "Reservation": {
        "type": "object",
        "properties": {
            "id":         {"type": "integer", "example": 5},
            "service_id": {"type": "integer", "example": 3},
            "service":    {"type": "string",  "example": "Ordonnances"},
            "queue": {
                "$ref": "#/components/schemas/QueueRef",
                "description": (
                    "File d'attente active du service. "
                    "null si le service n'a pas de file active."
                ),
            },
            "date_heure": {
                "type": "string", "format": "date-time",
                "example": "2026-03-17T09:00:00",
            },
            "statut": {
                "type": "string",
                "enum": ["en_attente", "arrive", "annule"],
                "example": "en_attente",
            },
            "notes":            {"type": "string",  "example": "Première visite"},
            "pharmacie_lat":    {"type": "number",  "format": "double", "example": 36.8065},
            "pharmacie_lon":    {"type": "number",  "format": "double", "example": 10.1815},
            "rayon_validation": {"type": "integer", "example": 200},
            "fenetre_je_suis_la": {
                "type": "object",
                "nullable": True,
                "description": (
                    "Fenêtre horaire (UTC) dans laquelle le bouton « Je suis là » est actif. "
                    "Calculée comme [date_heure − durée_estimée, date_heure + durée_estimée]. "
                    "null si la réservation n'a pas de créneau défini."
                ),
                "properties": {
                    "debut": {
                        "type": "string", "format": "date-time",
                        "example": "2026-03-17T08:45:00",
                    },
                    "fin": {
                        "type": "string", "format": "date-time",
                        "example": "2026-03-17T09:15:00",
                    },
                },
                "required": ["debut", "fin"],
            },
            "ticket": {"$ref": "#/components/schemas/TicketRef"},
        },
        "required": ["id", "service_id", "service", "date_heure", "statut"],
    },

    # ── Résultat annulation ───────────────────────────────────────────────────

    "AnnulationResult": {
        "type": "object",
        "properties": {
            "success":        {"type": "boolean", "example": True},
            "message":        {"type": "string",  "example": "Réservation annulée avec succès."},
            "reservation_id": {"type": "integer", "example": 5},
        },
        "required": ["success", "message", "reservation_id"],
    },

    # ── Résultat Je suis là ───────────────────────────────────────────────────
    # ✅ CORRIGÉ : ajout queue_id + queue dans le ticket retourné

    "JeSuisLaSucces": {
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "enum": [True]},
            "ticket": {
                "type": "object",
                "properties": {
                    "id":                   {"type": "integer", "example": 42},
                    "numero":               {"type": "string",  "example": "A-007"},
                    "position":             {"type": "integer", "example": 3},
                    "temps_attente_estime": {"type": "integer", "example": 45},
                    "service":              {"type": "string",  "example": "Ordonnances"},
                    "queue_id": {
                        "type": "integer", "example": 2,
                        "description": "ID de la file d'attente",
                    },
                    "queue": {
                        "type": "string", "example": "Ordonnances – File – Ordonnances",
                        "description": "display_name de la file d'attente",
                    },
                },
                "required": ["id", "numero", "position", "temps_attente_estime", "service"],
            },
            "distance_metres": {"type": "number", "example": 42.5},
        },
        "required": ["success", "ticket", "distance_metres"],
    },

    # ✅ CORRIGÉ : ajout du cas hors_fenetre avec ses champs spécifiques

    "JeSuisLaEchec": {
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "enum": [False]},
            "error": {
                "type": "string",
                "enum": [
                    "trop_loin",
                    "hors_fenetre",
                    "reservation_annulee",
                    "ticket_deja_attribue",
                    "no_queue",
                ],
                "example": "trop_loin",
            },
            "message": {
                "type": "string",
                "example": "Vous êtes à 250m de la pharmacie.",
            },
            "distance_metres": {
                "type": "number", "example": 250.0,
                "description": "Présent uniquement si error = trop_loin",
            },
            "rayon_metres": {
                "type": "integer", "example": 200,
                "description": "Présent uniquement si error = trop_loin",
            },
            "fenetre_debut": {
                "type": "string", "format": "date-time",
                "example": "2026-03-17T08:45:00",
                "description": "Présent uniquement si error = hors_fenetre",
            },
            "fenetre_fin": {
                "type": "string", "format": "date-time",
                "example": "2026-03-17T09:15:00",
                "description": "Présent uniquement si error = hors_fenetre",
            },
        },
        "required": ["success", "error", "message"],
    },

    # ── Rattachement ──────────────────────────────────────────────────────────

    "Rattachement": {
        "type": "object",
        "properties": {
            "id":       {"type": "integer", "example": 1},
            "guichet":  {"type": "string",  "example": "Guichet 1"},
            "queue_id": {"type": "integer", "example": 2},
            "user_id":  {"type": "integer", "example": 7},
        },
        "required": ["id"],
    },

    # ── Erreur générique ──────────────────────────────────────────────────────

    "Error": {
        "type": "object",
        "properties": {
            "error": {"type": "string", "example": "Authentification requise."},
        },
        "required": ["error"],
    },
}

# ── Helpers internes ──────────────────────────────────────────────────────────

def _json(schema: dict) -> dict:
    return {"application/json": {"schema": schema}}


def _ref(name: str) -> dict:
    return {"$ref": f"#/components/schemas/{name}"}


def _err(code: str) -> dict:
    return {"description": code, "content": _json(_ref("Error"))}


def _path_param(name: str) -> dict:
    return {
        "name": name, "in": "path", "required": True,
        "schema": {"type": "integer"},
    }


# ── Paths ─────────────────────────────────────────────────────────────────────

SERVICE_PATHS = {

    # ═══════════════════════════════ SERVICES ════════════════════════════════

    "/api/pharmacy/services": {
        "get": {
            "summary": "Liste des services actifs",
            "description": "Retourne tous les services actifs avec leurs horaires journaliers.",
            "tags": ["Services"],
            "security": [],
            "responses": {
                "200": {
                    "description": "Liste des services",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "services": {"type": "array", "items": _ref("Service")},
                        },
                    }),
                }
            },
        }
    },

    "/api/pharmacy/services/{service_id}": {
        "get": {
            "summary": "Détail d'un service",
            "tags": ["Services"],
            "security": [],
            "parameters": [_path_param("service_id")],
            "responses": {
                "200": {
                    "description": "Service trouvé",
                    "content": _json({
                        "type": "object",
                        "properties": {"service": _ref("Service")},
                    }),
                },
                "404": _err("Service introuvable"),
            },
        }
    },

    "/api/pharmacy/services/{service_id}/horaires": {
        "get": {
            "summary": "Horaires journaliers d'un service",
            "description": (
                "Retourne les horaires configurés jour par jour. "
                "Les jours absents utilisent les horaires_par_defaut. "
                "Le champ overnight indique si l'horaire traverse minuit."
            ),
            "tags": ["Services"],
            "security": [],
            "parameters": [_path_param("service_id")],
            "responses": {
                "200": {
                    "description": "Horaires du service",
                    "content": _json(_ref("ServiceHoraires")),
                },
                "404": _err("Service introuvable"),
            },
        }
    },

    "/api/pharmacy/services/{service_id}/slots": {
        "get": {
            "summary": "Créneaux disponibles",
            "description": (
                "Génère les créneaux pour une date donnée en respectant "
                "les horaires journaliers et l'intervalle du service. "
                "Gère le cas overnight (pharmacie de nuit)."
            ),
            "tags": ["Services"],
            "security": [],
            "parameters": [
                _path_param("service_id"),
                {
                    "name": "date", "in": "query", "required": False,
                    "schema": {"type": "string", "format": "date", "example": "2026-03-17"},
                    "description": "Date cible (YYYY-MM-DD). Défaut : aujourd'hui.",
                },
            ],
            "responses": {
                "200": {"description": "Créneaux générés", "content": _json(_ref("SlotsResponse"))},
                "400": _err("Format de date invalide"),
                "404": _err("Service introuvable"),
            },
        }
    },

    # ═══════════════════════════════ QUEUES ══════════════════════════════════
    # ✅ CORRIGÉ : description mise à jour pour refléter le filtre service actif

    "/api/pharmacy/queues": {
        "get": {
            "summary": "Liste des files d'attente actives",
            "description": (
                "Retourne toutes les files actives. "
                "Les files dont le service associé est inactif sont exclues. "
                "Les files sans service sont incluses."
            ),
            "tags": ["Queues"],
            "security": [],
            "responses": {
                "200": {
                    "description": "Liste des files actives",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "queues": {"type": "array", "items": _ref("Queue")},
                        },
                    }),
                }
            },
        }
    },

    "/api/pharmacy/queues/{queue_id}": {
        "get": {
            "summary": "Détail d'une file",
            "description": (
                "Retourne le détail d'une file active. "
                "Retourne 404 si la file est inactive ou si son service est inactif."
            ),
            "tags": ["Queues"],
            "security": [],
            "parameters": [_path_param("queue_id")],
            "responses": {
                "200": {
                    "description": "File trouvée",
                    "content": _json({
                        "type": "object",
                        "properties": {"queue": _ref("Queue")},
                    }),
                },
                "404": _err("File introuvable (inactive ou service inactif)"),
            },
        }
    },

    # ═══════════════════════════════ RESERVATIONS ════════════════════════════

    "/api/pharmacy/reservations": {
        "post": {
            "summary": "Créer une réservation",
            "description": (
                "Crée une réservation pour l'utilisateur connecté. "
                "Vérifie que le créneau est disponible et dans les horaires du service."
            ),
            "tags": ["Reservations"],
            "security": [{"cookieAuth": []}],
            "requestBody": {
                "required": True,
                "content": _json({
                    "type": "object",
                    "required": ["service_id", "date_heure_reservation"],
                    "properties": {
                        "service_id": {"type": "integer", "example": 3},
                        "date_heure_reservation": {
                            "type": "string", "format": "date-time",
                            "example": "2026-03-17T09:00:00",
                        },
                        "notes": {"type": "string", "example": "Première visite"},
                    },
                }),
            },
            "responses": {
                "201": {
                    "description": "Réservation créée",
                    "content": _json({
                        "type": "object",
                        "properties": {"reservation": _ref("Reservation")},
                    }),
                },
                "400": _err("Créneau indisponible, hors horaires ou doublon"),
                "401": _err("Authentification requise"),
            },
        }
    },

    "/api/pharmacy/reservations/mes-reservations": {
        "get": {
            "summary": "Mes réservations",
            "description": (
                "Retourne les réservations de l'utilisateur connecté, "
                "triées par date décroissante."
            ),
            "tags": ["Reservations"],
            "security": [{"cookieAuth": []}],
            "parameters": [
                {
                    "name": "statut", "in": "query", "required": False,
                    "schema": {
                        "type": "string",
                        "enum": ["en_attente", "arrive", "annule"],
                    },
                    "description": "Filtre optionnel par statut.",
                }
            ],
            "responses": {
                "200": {
                    "description": "Liste des réservations",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "reservations": {"type": "array", "items": _ref("Reservation")},
                        },
                    }),
                },
                "400": _err("Valeur de statut invalide"),
                "401": _err("Non authentifié"),
            },
        }
    },

    "/api/pharmacy/reservations/{reservation_id}": {
        "get": {
            "summary": "Détail d'une réservation",
            "tags": ["Reservations"],
            "security": [{"cookieAuth": []}],
            "parameters": [_path_param("reservation_id")],
            "responses": {
                "200": {
                    "description": "Réservation trouvée",
                    "content": _json({
                        "type": "object",
                        "properties": {"reservation": _ref("Reservation")},
                    }),
                },
                "401": _err("Non authentifié"),
                "403": _err("Accès refusé"),
                "404": _err("Réservation introuvable"),
            },
        }
    },

    "/api/pharmacy/reservations/{reservation_id}/je-suis-la": {
        "post": {
            "summary": "Je suis là (validation GPS + fenêtre horaire)",
            "description": (
                "Valide l'arrivée du client. Deux conditions sont requises :\n"
                "1. L'heure actuelle doit être dans la fenêtre "
                "[date_heure − durée_estimée, date_heure + durée_estimée].\n"
                "2. La position GPS doit être dans le rayon de la pharmacie.\n"
                "En cas de succès, attribue un ticket virtuel.\n"
                "Retourne success=true avec le ticket, ou success=false avec le motif."
            ),
            "tags": ["Reservations"],
            "security": [{"cookieAuth": []}],
            "parameters": [_path_param("reservation_id")],
            "requestBody": {
                "required": True,
                "content": _json({
                    "type": "object",
                    "required": ["latitude", "longitude"],
                    "properties": {
                        "latitude":  {"type": "number", "format": "double", "example": 36.8060},
                        "longitude": {"type": "number", "format": "double", "example": 10.1810},
                    },
                }),
            },
            "responses": {
                "200": {
                    "description": "Résultat (succès ou échec métier)",
                    "content": _json({
                        "oneOf": [_ref("JeSuisLaSucces"), _ref("JeSuisLaEchec")],
                    }),
                },
                "400": _err("Coordonnées manquantes ou invalides"),
                "401": _err("Non authentifié"),
                "403": _err("Accès refusé"),
            },
        }
    },

    "/api/pharmacy/reservations/{reservation_id}/annuler": {
        "post": {
            "summary": "Annuler une réservation",
            "description": (
                "Annule une réservation en_attente. "
                "Interdit si statut = arrive. "
                "Interdit si statut = annule (déjà annulée)."
            ),
            "tags": ["Reservations"],
            "security": [{"cookieAuth": []}],
            "parameters": [_path_param("reservation_id")],
            "responses": {
                "200": {
                    "description": "Réservation annulée",
                    "content": _json(_ref("AnnulationResult")),
                },
                "400": _err("Impossible d'annuler (déjà arrivée ou déjà annulée)"),
                "401": _err("Non authentifié"),
                "403": _err("Accès refusé"),
                "404": _err("Réservation introuvable"),
            },
        }
    },

    # ═══════════════════════════════ TICKETS ═════════════════════════════════

    # ✅ NOUVEAU : POST /api/pharmacy/tickets — création ticket physique
    "/api/pharmacy/tickets": {
        "post": {
            "summary": "Créer un ticket",
            "description": (
                "Crée un ticket pour l'utilisateur connecté dans une file donnée. "
                "Par défaut type_ticket = 'physique'. "
                "Pour les tickets virtuels, préférer le flux « Je suis là » "
                "qui crée le ticket automatiquement."
            ),
            "tags": ["Tickets"],
            "security": [{"cookieAuth": []}],
            "requestBody": {
                "required": True,
                "content": {
                    "application/x-www-form-urlencoded": {
                        "schema": {
                            "type": "object",
                            "required": ["queue_id"],
                            "properties": {
                                "queue_id": {
                                    "type": "integer", "example": 1,
                                    "description": "ID de la file d'attente cible",
                                },
                                "type_ticket": {
                                    "type": "string",
                                    "enum": ["physique", "virtuel"],
                                    "default": "physique",
                                    "description": "Type de ticket. Défaut : physique.",
                                },
                            },
                        }
                    },
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["queue_id"],
                            "properties": {
                                "queue_id": {
                                    "type": "integer", "example": 1,
                                },
                                "type_ticket": {
                                    "type": "string",
                                    "enum": ["physique", "virtuel"],
                                    "default": "physique",
                                },
                            },
                        }
                    },
                },
            },
            "responses": {
                "200": {
                    "description": "Ticket créé",
                    "content": _json({
                        "type": "object",
                        "properties": {"ticket": _ref("Ticket")},
                    }),
                },
                "400": _err("queue_id manquant ou type_ticket invalide"),
                "401": _err("Non authentifié"),
                "404": _err("File d'attente introuvable"),
            },
        }
    },

    # ✅ NOUVEAU : GET /api/pharmacy/tickets/mine — mes tickets
    # ⚠️  Ce path DOIT être déclaré AVANT /{ticket_id} pour éviter
    #     qu'Odoo/OpenAPI interprète "mine" comme un entier.
    "/api/pharmacy/tickets/mine": {
        "get": {
            "summary": "Mes tickets",
            "description": (
                "Retourne tous les tickets de l'utilisateur connecté, "
                "triés par date de création décroissante. "
                "Filtre optionnel par statut."
            ),
            "tags": ["Tickets"],
            "security": [{"cookieAuth": []}],
            "parameters": [
                {
                    "name": "statut", "in": "query", "required": False,
                    "schema": {
                        "type": "string",
                        "enum": ["en_attente", "appele", "termine", "annule"],
                    },
                    "description": "Filtre optionnel par statut.",
                }
            ],
            "responses": {
                "200": {
                    "description": "Liste des tickets",
                    "content": _json(_ref("TicketsListResponse")),
                },
                "401": _err("Non authentifié"),
            },
        }
    },

    # GET /api/pharmacy/tickets/{ticket_id} — détail d'un ticket
    "/api/pharmacy/tickets/{ticket_id}": {
        "get": {
            "summary": "Détail d'un ticket",
            "description": (
                "Retourne l'état courant d'un ticket : position, "
                "temps d'attente estimé, heures de création / appel / fin."
            ),
            "tags": ["Tickets"],
            "security": [{"cookieAuth": []}],
            "parameters": [_path_param("ticket_id")],
            "responses": {
                "200": {
                    "description": "Ticket trouvé",
                    "content": _json(_ref("Ticket")),
                },
                "401": _err("Non authentifié"),
                "404": _err("Ticket introuvable"),
            },
        }
    },

    # ═══════════════════════════════ RATTACHEMENTS ═══════════════════════════

    "/api/pharmacy/rattachements": {
        "get": {
            "summary": "Liste des rattachements (guichets)",
            "tags": ["Rattachements"],
            "security": [{"cookieAuth": []}],
            "responses": {
                "200": {
                    "description": "Liste des rattachements",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "rattachements": {
                                "type": "array",
                                "items": _ref("Rattachement"),
                            }
                        },
                    }),
                },
                "401": _err("Non authentifié"),
            },
        }
    },

    "/api/pharmacy/rattachements/{rattachement_id}/appeler-prochain": {
        "post": {
            "summary": "Appeler le prochain ticket",
            "description": (
                "Passe le ticket suivant à l'état 'appelé' pour ce guichet. "
                "En mode prioritaire, traite d'abord les tickets du service prioritaire."
            ),
            "tags": ["Rattachements"],
            "security": [{"cookieAuth": []}],
            "parameters": [_path_param("rattachement_id")],
            "responses": {
                "200": {
                    "description": "Ticket appelé",
                    "content": _json({
                        "type": "object",
                        "properties": {"ticket": _ref("Ticket")},
                    }),
                },
                "400": _err("Aucun ticket en attente"),
                "401": _err("Non authentifié"),
                "404": _err("Rattachement introuvable"),
            },
        }
    },
}
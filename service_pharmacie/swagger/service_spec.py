
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

    "Queue": {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "example": 2},
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

    # ── Produit parapharmacie ─────────────────────────────────────────────────

    "ProduitParapharmacie": {
        "type": "object",
        "properties": {
            "id":                  {"type": "integer", "example": 42},
            "nom_commercial":      {"type": "string",  "example": "Biafine"},
            "nom_generique":       {"type": "string",  "example": ""},
            "name":                {"type": "string",  "example": "Biafine crème"},
            "dosage":              {"type": "string",  "example": ""},
            "fabricant":           {"type": "string",  "example": "Pharma Labs"},
            "prix_vente_tnd":      {"type": "number",  "example": 12.500},
            "prix_achat_tnd":      {"type": "number",  "example": 8.000},
            "tva_taux":            {"type": "string",  "example": "19"},
            "forme_galenique":     {"type": "string",  "example": "Crème"},
            "forme_galenique_id":  {"type": "integer", "nullable": True, "example": 5},
            "quantite_stock":      {"type": "integer", "example": 100},
            "disponible":          {"type": "boolean", "example": True},
            "necessite_ordonnance":{"type": "boolean", "example": False},
            "parapharmaceutique":  {"type": "boolean", "example": True},
            "image_url":           {"type": "string",  "example": "https://demopharma.eprswarm.com/api/parapharma/image/42?unique=1712345678000"},
        },
        "required": ["id", "name", "prix_vente_tnd", "disponible"],
    },

    "ProduitParapharmacieDetail": {
        "allOf": [
            {"$ref": "#/components/schemas/ProduitParapharmacie"},
            {
                "type": "object",
                "properties": {
                    "description_pharmacie":  {"type": "string", "example": "Crème émolliente apaisante."},
                    "code_barre_pharmacie":   {"type": "string", "example": "3400930102015"},
                    "seuil_alerte_stock":     {"type": "number", "example": 10.0},
                    "alerte_stock":           {"type": "boolean", "example": False},
                    "lot_count":              {"type": "integer", "example": 3},
                    "prix_ttc": {
                        "type": "number", "example": 14.875,
                        "description": "Prix TTC calculé côté serveur",
                    },
                },
            },
        ]
    },

    # ── Ligne de panier ───────────────────────────────────────────────────────

    "LignePanier": {
        "type": "object",
        "properties": {
            "product_id":            {"type": "integer", "example": 42},
            "nom_commercial":        {"type": "string",  "example": "Biafine"},
            "quantite":              {"type": "integer", "example": 2},
            "prix_unitaire_ht":      {"type": "number",  "example": 12.500},
            "tva_taux":              {"type": "string",  "example": "19"},
            "montant_ht":            {"type": "number",  "example": 25.000},
            "montant_tva":           {"type": "number",  "example": 4.750},
            "montant_ttc":           {"type": "number",  "example": 29.750},
            "stock_disponible":      {"type": "integer", "example": 100},
            "alerte_stock_insuffisant": {"type": "boolean", "example": False},
        },
        "required": ["product_id", "nom_commercial", "quantite", "montant_ttc"],
    },

    # ── Prescription ──────────────────────────────────────────────────────────

    "PrescriptionMobilePayload": {
        "type": "object",
        "description": "Payload mobile complet d'une ordonnance (export_mobile_payload)",
        "properties": {
            "id":     {"type": "integer", "example": 7},
            "state":  {"type": "string",  "example": "draft"},
            "lines":  {"type": "array",   "items": {"type": "object"}},
        },
        "required": ["id"],
    },

    # ── Commande mobile ───────────────────────────────────────────────────────

    "MobileOrder": {
        "type": "object",
        "description": "Représentation d'une commande mobile (export_order_payload)",
        "properties": {
            "id":    {"type": "integer", "example": 3},
            "state": {"type": "string",  "example": "draft"},
            "lines": {"type": "array",   "items": {"type": "object"}},
        },
        "required": ["id"],
    },

    # ── Localisation pharmacie ────────────────────────────────────────────────

    "PharmacyLocalisation": {
        "type": "object",
        "description": "Données de localisation/configuration de la pharmacie",
        "properties": {
            "nom":       {"type": "string", "example": "Pharmacie Ibn Khaldoun"},
            "adresse":   {"type": "string", "example": "12 Rue Ibn Khaldoun, Tunis"},
            "latitude":  {"type": "number", "format": "double", "example": 36.8065},
            "longitude": {"type": "number", "format": "double", "example": 10.1815},
            "telephone": {"type": "string", "example": "+216 71 000 000"},
        },
    },

    # ── Display (écran d'affichage) ───────────────────────────────────────────

    "DisplayQueue": {
        "type": "object",
        "description": "Données d'une file pour l'écran d'affichage public",
        "properties": {
            "queue_id":   {"type": "integer", "example": 1},
            "queue_name": {"type": "string",  "example": "Ordonnances – File A"},
            "appeles": {
                "type": "array",
                "description": "Tickets actuellement appelés (un par guichet)",
                "items": {
                    "type": "object",
                    "properties": {
                        "rattachement_id": {"type": "integer", "example": 2},
                        "ticket_id":       {"type": "integer", "example": 42},
                        "ticket_name":     {"type": "string",  "example": "A-007"},
                        "poste_number":    {"type": "string",  "example": "3"},
                        "etat":            {"type": "string",  "example": "appele"},
                        "priorite":        {"type": "integer", "example": 1},
                    },
                },
            },
            "en_attente": {
                "type": "array",
                "description": "Prochains tickets en attente (max 10)",
                "items": {
                    "type": "object",
                    "properties": {
                        "ticket_id":   {"type": "integer", "example": 43},
                        "ticket_name": {"type": "string",  "example": "A-008"},
                        "etat":        {"type": "string",  "example": "en_attente"},
                        "priorite":    {"type": "integer", "example": 1},
                    },
                },
            },
        },
        "required": ["queue_id", "queue_name", "appeles", "en_attente"],
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


def _path_param(name: str, type_: str = "integer") -> dict:
    return {
        "name": name, "in": "path", "required": True,
        "schema": {"type": type_},
    }


def _query_param(name: str, description: str = "", required: bool = False,
                 type_: str = "string", enum: list = None, example=None) -> dict:
    schema = {"type": type_}
    if enum:
        schema["enum"] = enum
    if example is not None:
        schema["example"] = example
    p = {"name": name, "in": "query", "required": required,
         "schema": schema, "description": description}
    return p


# ── Paths ─────────────────────────────────────────────────────────────────────

SERVICE_PATHS = {

    # ═══════════════════════════════ SERVICES ════════════════════════════════

    "/api/pharmacy/services": {
        "get": {
            "summary": "Liste des services actifs",
            "description": "Retourne tous les services actifs avec leurs horaires journaliers.",
            "tags": ["Services"],
            "security": [],
            # CORRECTION : ajout du query param type_affichage (présent dans ServiceController)
            "parameters": [
                _query_param(
                    "type_affichage",
                    description=(
                        "Filtre optionnel sur le type d'affichage du service. "
                        "Transmis tel quel au service métier."
                    ),
                ),
            ],
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
            # CORRECTION : ajout du query param type_affichage (présent dans QueueController)
            "parameters": [
                _query_param(
                    "type_affichage",
                    description=(
                        "Filtre optionnel sur le type d'affichage. "
                        "Transmis tel quel au service métier."
                    ),
                ),
            ],
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

    "/api/pharmacy/tickets": {
        "post": {
            "summary": "Créer un ticket",
            "description": (
                "Crée un ticket dans une file donnée. "
                "type_ticket='physique' ne doit pas avoir de reservation_id. "
                "type_ticket='virtuel' requiert un reservation_id. "
                "Pour les tickets virtuels, préférer le flux « Je suis là » "
                "qui crée le ticket automatiquement."
            ),
            "tags": ["Tickets"],
            "security": [],
            "requestBody": {
                "required": True,
                "content": {
                    # CORRECTION : le contrôleur accepte form-urlencoded ET json ;
                    # reservation_id était absent du schéma précédent.
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
                                "reservation_id": {
                                    "type": "integer",
                                    "nullable": True,
                                    "example": 5,
                                    "description": (
                                        "Requis pour type_ticket='virtuel'. "
                                        "Interdit pour type_ticket='physique'."
                                    ),
                                },
                            },
                        }
                    },
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["queue_id"],
                            "properties": {
                                "queue_id":      {"type": "integer", "example": 1},
                                "type_ticket": {
                                    "type": "string",
                                    "enum": ["physique", "virtuel"],
                                    "default": "physique",
                                },
                                "reservation_id": {
                                    "type": "integer",
                                    "nullable": True,
                                    "example": 5,
                                    "description": (
                                        "Requis pour type_ticket='virtuel'. "
                                        "Interdit pour type_ticket='physique'."
                                    ),
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
                "400": _err(
                    "queue_id manquant, type_ticket invalide, "
                    "ou règle métier non respectée (reservation_id manquant/interdit)"
                ),
                "404": _err("File d'attente introuvable"),
            },
        }
    },

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

    # ═══════════════════════════════ LOCALISATION ════════════════════════════
    # AJOUT : PharmacyLocalizationController

    "/api/pharmacy/localisation": {
        "post": {
            "summary": "Localisation de la pharmacie",
            "description": (
                "Retourne les données de localisation et de configuration de la pharmacie "
                "(singleton). Utilise le type jsonrpc."
            ),
            "tags": ["Pharmacie"],
            "security": [],
            "requestBody": {
                "required": False,
                "content": _json({"type": "object"}),
            },
            "responses": {
                "200": {
                    "description": "Localisation trouvée",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "data":    _ref("PharmacyLocalisation"),
                        },
                    }),
                },
                "200 (échec)": {
                    "description": "Localisation introuvable",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": False},
                            "message": {"type": "string", "example": "Localisation pharmacie introuvable."},
                        },
                    }),
                },
            },
        }
    },

    # ═══════════════════════════════ DISPLAY (écran public) ══════════════════
    # AJOUT : DisplayController

    "/pharmacy/display": {
        "get": {
            "summary": "Page d'affichage public des tickets",
            "description": (
                "Rendu HTML de la page d'affichage des tickets (template QWeb). "
                "Accessible sans authentification."
            ),
            "tags": ["Display"],
            "security": [],
            "responses": {
                "200": {"description": "Page HTML rendue"},
            },
        }
    },

    "/pharmacy/display/data": {
        "get": {
            "summary": "Données temps-réel pour l'écran d'affichage",
            "description": (
                "Retourne en JSON l'état courant de toutes les files actives : "
                "tickets appelés par guichet et prochains tickets en attente (max 10 par file). "
                "Accepte GET et POST."
            ),
            "tags": ["Display"],
            "security": [],
            "responses": {
                "200": {
                    "description": "Données d'affichage",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "queues": {
                                "type": "array",
                                "items": _ref("DisplayQueue"),
                            },
                        },
                    }),
                },
            },
        },
        "post": {
            "summary": "Données temps-réel pour l'écran d'affichage (POST)",
            "description": "Alias POST de GET /pharmacy/display/data.",
            "tags": ["Display"],
            "security": [],
            "responses": {
                "200": {
                    "description": "Données d'affichage",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "queues": {
                                "type": "array",
                                "items": _ref("DisplayQueue"),
                            },
                        },
                    }),
                },
            },
        },
    },

    # ═══════════════════════════════ TICKET DISPLAY (kiosk) ══════════════════
    # AJOUT : TicketDisplayController

    "/pharmacy/ticket/display": {
        "get": {
            "summary": "Page kiosque d'affichage des tickets (protégée par mot de passe)",
            "description": (
                "Rendu HTML de la page kiosque. Requiert :\n"
                "1. Le paramètre système service_pharmacie.ticket_public_enabled = 'True'.\n"
                "2. Une session valide (cookie ticket_display_ok).\n"
                "Redirige vers /pharmacy/ticket/access sinon."
            ),
            "tags": ["Display"],
            "security": [],
            "responses": {
                "200": {"description": "Page HTML rendue"},
                "302": {"description": "Redirection vers la page d'accès"},
                "404": {"description": "Fonctionnalité désactivée"},
            },
        }
    },

    "/pharmacy/ticket/access": {
        "get": {
            "summary": "Page d'authentification kiosque",
            "description": "Formulaire de saisie du mot de passe pour accéder au kiosque.",
            "tags": ["Display"],
            "security": [],
            "responses": {
                "200": {"description": "Page HTML rendue"},
            },
        }
    },

    "/pharmacy/ticket/access/check": {
        "post": {
            "summary": "Vérification du mot de passe kiosque",
            "description": (
                "Vérifie le mot de passe soumis par le formulaire. "
                "En cas de succès, positionne ticket_display_ok dans la session "
                "et redirige vers /pharmacy/ticket/display."
            ),
            "tags": ["Display"],
            "security": [],
            "requestBody": {
                "required": True,
                "content": {
                    "application/x-www-form-urlencoded": {
                        "schema": {
                            "type": "object",
                            "required": ["password"],
                            "properties": {
                                "password": {"type": "string", "example": "mon_mot_de_passe"},
                            },
                        }
                    }
                },
            },
            "responses": {
                "302": {"description": "Redirection vers /pharmacy/ticket/display (succès) ou /pharmacy/ticket/access?error=1 (échec)"},
                "404": {"description": "Fonctionnalité désactivée"},
            },
        }
    },

    "/pharmacy/ticket/logout": {
        "get": {
            "summary": "Déconnexion kiosque",
            "description": "Supprime ticket_display_ok de la session et redirige vers /pharmacy/ticket/access.",
            "tags": ["Display"],
            "security": [],
            "responses": {
                "302": {"description": "Redirection vers la page d'accès"},
            },
        }
    },

    # ═══════════════════════════════ PARAPHARMACIE ═══════════════════════════
    # AJOUT : ParapharmacieController

    "/api/parapharma/image/{product_id}": {
        "get": {
            "summary": "Image d'un produit",
            "description": "Retourne l'image (128px) d'un product.template en PNG.",
            "tags": ["Parapharmacie"],
            "security": [],
            "parameters": [_path_param("product_id")],
            "responses": {
                "200": {
                    "description": "Image PNG",
                    "content": {"image/png": {"schema": {"type": "string", "format": "binary"}}},
                },
                "404": {"description": "Produit introuvable ou sans image"},
            },
        }
    },

    "/api/pharmacie/parapharmaceutique": {
        "get": {
            "summary": "Liste des produits parapharmaceutiques",
            "description": "Pagination, filtre par forme galénique et disponibilité.",
            "tags": ["Parapharmacie"],
            "security": [],
            "parameters": [
                _query_param("page",              "Page (défaut 1)",              example=1,  type_="integer"),
                _query_param("limit",             "Résultats par page (max 50)",  example=20, type_="integer"),
                _query_param("forme_galenique_id","ID de la forme galénique",     type_="integer"),
                _query_param("disponible",        "Filtrer les produits en stock (1/true/yes)"),
            ],
            "responses": {
                "200": {
                    "description": "Liste paginée",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success":  {"type": "boolean"},
                            "total":    {"type": "integer"},
                            "page":     {"type": "integer"},
                            "limit":    {"type": "integer"},
                            "pages":    {"type": "integer"},
                            "products": {"type": "array", "items": _ref("ProduitParapharmacie")},
                        },
                    }),
                },
            },
        }
    },

    "/api/pharmacie/parapharmaceutique/{product_id}": {
        "get": {
            "summary": "Détail d'un produit parapharmaceutique",
            "tags": ["Parapharmacie"],
            "security": [],
            "parameters": [_path_param("product_id")],
            "responses": {
                "200": {
                    "description": "Produit trouvé",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean"},
                            "product": _ref("ProduitParapharmacieDetail"),
                        },
                    }),
                },
                "404": _err("Produit parapharmaceutique introuvable"),
            },
        }
    },

    "/api/pharmacie/parapharmaceutique/search": {
        "post": {
            "summary": "Recherche plein-texte de produits parapharmaceutiques",
            "tags": ["Parapharmacie"],
            "security": [],
            "requestBody": {
                "required": True,
                "content": _json({
                    "type": "object",
                    "required": ["query"],
                    "properties": {
                        "query": {"type": "string",  "example": "biafine"},
                        "page":  {"type": "integer", "example": 1, "default": 1},
                        "limit": {"type": "integer", "example": 20, "default": 20},
                    },
                }),
            },
            "responses": {
                "200": {
                    "description": "Résultats de recherche",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success":  {"type": "boolean"},
                            "query":    {"type": "string"},
                            "total":    {"type": "integer"},
                            "page":     {"type": "integer"},
                            "limit":    {"type": "integer"},
                            "products": {"type": "array", "items": _ref("ProduitParapharmacie")},
                        },
                    }),
                },
                "400": _err("Le champ 'query' est requis"),
            },
        }
    },

    "/api/pharmacie/panier/calculer": {
        "post": {
            "summary": "Calculer le montant d'un panier",
            "description": (
                "Calcule HT, TVA et TTC pour une liste d'articles. "
                "Accepte les produits parapharmaceutiques ET les médicaments. "
                "La TVA est lue depuis Odoo (non fournie par le client)."
            ),
            "tags": ["Parapharmacie"],
            "security": [],
            "requestBody": {
                "required": True,
                "content": _json({
                    "type": "object",
                    "required": ["articles"],
                    "properties": {
                        "articles": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["product_id", "quantite"],
                                "properties": {
                                    "product_id": {"type": "integer", "example": 42},
                                    "quantite":   {"type": "integer", "example": 2},
                                },
                            },
                        }
                    },
                }),
            },
            "responses": {
                "200": {
                    "description": "Calcul réalisé",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success":     {"type": "boolean"},
                            "lignes":      {"type": "array", "items": _ref("LignePanier")},
                            "total_ht":    {"type": "number"},
                            "total_tva":   {"type": "number"},
                            "total_ttc":   {"type": "number"},
                            "nb_articles": {"type": "integer"},
                            "erreurs":     {"type": "array", "items": {"type": "object"}},
                        },
                    }),
                },
                "400": _err("La liste 'articles' est vide ou absente"),
            },
        }
    },

    # ═══════════════════════════════ CHATBOT ═════════════════════════════════
    # AJOUT : QPharmaBotController (toutes les routes sont type=jsonrpc)

    "/api/chatbot/message": {
        "post": {
            "summary": "Envoyer un message au chatbot",
            "description": "Point d'entrée principal du chatbot QPharma. Type jsonrpc.",
            "tags": ["Chatbot"],
            "security": [],
            "requestBody": {
                "required": True,
                "content": _json({
                    "type": "object",
                    "description": "Payload jsonrpc — contenu libre selon le service chatbot",
                }),
            },
            "responses": {
                "200": {
                    "description": "Réponse du chatbot",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean"},
                        },
                    }),
                },
            },
        }
    },

    "/api/chatbot/stock": {
        "post": {
            "summary": "Consulter le stock via le chatbot",
            "tags": ["Chatbot"],
            "security": [],
            "requestBody": {"required": True, "content": _json({"type": "object"})},
            "responses": {
                "200": {
                    "description": "Données de stock",
                    "content": _json({"type": "object", "properties": {"success": {"type": "boolean"}}}),
                }
            },
        }
    },

    "/api/chatbot/panier": {
        "post": {
            "summary": "Consulter le panier chatbot",
            "tags": ["Chatbot"],
            "security": [],
            "requestBody": {"required": True, "content": _json({"type": "object"})},
            "responses": {
                "200": {
                    "description": "Contenu du panier",
                    "content": _json({"type": "object", "properties": {"success": {"type": "boolean"}}}),
                }
            },
        }
    },

    "/api/chatbot/panier/ajouter": {
        "post": {
            "summary": "Ajouter un article au panier chatbot",
            "tags": ["Chatbot"],
            "security": [],
            "requestBody": {"required": True, "content": _json({"type": "object"})},
            "responses": {
                "200": {
                    "description": "Article ajouté",
                    "content": _json({"type": "object", "properties": {"success": {"type": "boolean"}}}),
                }
            },
        }
    },

    "/api/chatbot/panier/modifier": {
        "post": {
            "summary": "Modifier un article du panier chatbot",
            "tags": ["Chatbot"],
            "security": [],
            "requestBody": {"required": True, "content": _json({"type": "object"})},
            "responses": {
                "200": {
                    "description": "Article modifié",
                    "content": _json({"type": "object", "properties": {"success": {"type": "boolean"}}}),
                }
            },
        }
    },

    "/api/chatbot/panier/vider": {
        "post": {
            "summary": "Vider le panier chatbot",
            "tags": ["Chatbot"],
            "security": [],
            "requestBody": {"required": True, "content": _json({"type": "object"})},
            "responses": {
                "200": {
                    "description": "Panier vidé",
                    "content": _json({"type": "object", "properties": {"success": {"type": "boolean"}}}),
                }
            },
        }
    },

    "/api/chatbot/panier/confirmer": {
        "post": {
            "summary": "Confirmer le panier chatbot",
            "tags": ["Chatbot"],
            "security": [],
            "requestBody": {"required": True, "content": _json({"type": "object"})},
            "responses": {
                "200": {
                    "description": "Panier confirmé",
                    "content": _json({"type": "object", "properties": {"success": {"type": "boolean"}}}),
                }
            },
        }
    },

    # ═══════════════════════════════ MOBILE ORDER ════════════════════════════
    # AJOUT : MobileOrderController

    "/api/mobile/order/start": {
        "post": {
            "summary": "Démarrer une commande mobile",
            "description": (
                "Crée une réservation et, si des lignes de panier valides sont fournies, "
                "crée également la commande mobile associée."
            ),
            "tags": ["Commandes Mobile"],
            "security": [],
            "requestBody": {
                "required": True,
                "content": _json({
                    "type": "object",
                    "required": ["service_id", "date_heure_reservation"],
                    "properties": {
                        "service_id":              {"type": "integer", "example": 3},
                        "date_heure_reservation":  {"type": "string", "format": "date-time", "example": "2026-03-17T09:00:00"},
                        "partner_id":              {"type": "integer", "nullable": True, "example": 12},
                        "prescription_id":         {"type": "integer", "nullable": True, "example": 7},
                        "notes":                   {"type": "string", "example": ""},
                        "cart_lines": {
                            "type": "array",
                            "description": "Lignes de panier unifiées",
                            "items": {
                                "type": "object",
                                "required": ["product_id", "quantite"],
                                "properties": {
                                    "product_id": {"type": "integer", "example": 42},
                                    "quantite":   {"type": "number",  "example": 2},
                                },
                            },
                        },
                    },
                }),
            },
            "responses": {
                "200": {
                    "description": "Réservation (et commande) créée",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success":      {"type": "boolean"},
                            "reservation":  {"type": "object"},
                            "mobile_order": {
                                "oneOf": [_ref("MobileOrder"), {"type": "null"}],
                                "description": "null si aucune ligne de panier valide",
                            },
                            "next_step":    {"type": "string", "example": "je_suis_la"},
                        },
                    }),
                },
                "200 (échec)": {
                    "description": "Erreur métier",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": False},
                            "message": {"type": "string"},
                        },
                    }),
                },
            },
        }
    },

    "/api/mobile/order/cancel_reservation": {
        "post": {
            "summary": "Annuler une réservation (flux public, par payload)",
            "description": "Annule une réservation identifiée par reservation_id dans le body.",
            "tags": ["Commandes Mobile"],
            "security": [],
            "requestBody": {
                "required": True,
                "content": _json({
                    "type": "object",
                    "required": ["reservation_id"],
                    "properties": {
                        "reservation_id": {"type": "integer", "example": 5},
                    },
                }),
            },
            "responses": {
                "200": {
                    "description": "Réservation annulée ou erreur",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success":        {"type": "boolean"},
                            "message":        {"type": "string"},
                            "reservation_id": {"type": "integer"},
                        },
                    }),
                },
            },
        }
    },

    "/api/mobile/reservation/{reservation_id}/cancel": {
        "post": {
            "summary": "Annuler une réservation (route directe)",
            "description": "Annule la réservation identifiée par l'ID dans l'URL.",
            "tags": ["Commandes Mobile"],
            "security": [],
            "parameters": [_path_param("reservation_id")],
            "responses": {
                "200": {
                    "description": "Réservation annulée ou erreur",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success":        {"type": "boolean"},
                            "message":        {"type": "string"},
                            "reservation_id": {"type": "integer"},
                        },
                    }),
                },
            },
        }
    },

    "/api/mobile/order/{order_id}": {
        "post": {
            "summary": "Récupérer une commande mobile",
            "tags": ["Commandes Mobile"],
            "security": [],
            "parameters": [_path_param("order_id")],
            "responses": {
                "200": {
                    "description": "Commande trouvée",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success":      {"type": "boolean"},
                            "mobile_order": _ref("MobileOrder"),
                        },
                    }),
                },
            },
        }
    },

    "/api/mobile/order/{order_id}/attach_ticket": {
        "post": {
            "summary": "Rattacher un ticket à une commande mobile",
            "tags": ["Commandes Mobile"],
            "security": [],
            "parameters": [_path_param("order_id")],
            "requestBody": {
                "required": True,
                "content": _json({
                    "type": "object",
                    "required": ["ticket_id"],
                    "properties": {
                        "ticket_id": {"type": "integer", "example": 42},
                    },
                }),
            },
            "responses": {
                "200": {
                    "description": "Ticket rattaché",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success":      {"type": "boolean"},
                            "mobile_order": _ref("MobileOrder"),
                        },
                    }),
                },
            },
        }
    },

    "/api/mobile/order/{order_id}/confirm": {
        "post": {
            "summary": "Confirmer une commande mobile → POS",
            "description": "Convertit la commande mobile en commande POS.",
            "tags": ["Commandes Mobile"],
            "security": [],
            "parameters": [_path_param("order_id")],
            "responses": {
                "200": {
                    "description": "Commande confirmée",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success":      {"type": "boolean"},
                            "mobile_order": _ref("MobileOrder"),
                            "pos_order": {
                                "type": "object",
                                "properties": {
                                    "id":   {"type": "integer", "example": 100},
                                    "name": {"type": "string",  "example": "POS/2026/0042"},
                                },
                            },
                        },
                    }),
                },
            },
        }
    },

    "/api/mobile/order/{order_id}/cancel": {
        "post": {
            "summary": "Annuler une commande mobile",
            "description": (
                "Annule la commande mobile. Si la réservation liée est en_attente, "
                "elle est également annulée."
            ),
            "tags": ["Commandes Mobile"],
            "security": [],
            "parameters": [_path_param("order_id")],
            "responses": {
                "200": {
                    "description": "Commande annulée",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean"},
                            "message": {"type": "string"},
                        },
                    }),
                },
            },
        }
    },

    # ═══════════════════════════════ PRESCRIPTIONS (API) ═════════════════════
    # AJOUT : PrescriptionApiController

    "/api/prescription/upload": {
        "post": {
            "summary": "Uploader une ordonnance",
            "description": "Crée une ordonnance à partir d'un fichier base64 (image ou PDF).",
            "tags": ["Ordonnances"],
            "security": [],
            "requestBody": {
                "required": True,
                "content": _json({
                    "type": "object",
                    "required": ["file_base64"],
                    "properties": {
                        "filename":    {"type": "string",  "example": "ordonnance.jpg"},
                        "file_base64": {"type": "string",  "description": "Contenu du fichier en base64"},
                        "source_type": {"type": "string",  "example": "virtual", "default": "virtual"},
                        "ticket_id":   {"type": "integer", "nullable": True},
                        "partner_id":  {"type": "integer", "nullable": True},
                        "mimetype":    {"type": "string",  "example": "image/jpeg"},
                    },
                }),
            },
            "responses": {
                "200": {
                    "description": "Ordonnance créée",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean"},
                            "data":    _ref("PrescriptionMobilePayload"),
                        },
                    }),
                },
                "200 (échec)": {
                    "description": "Fichier manquant",
                    "content": _json({
                        "type": "object",
                        "properties": {"success": {"type": "boolean", "example": False}, "message": {"type": "string"}},
                    }),
                },
            },
        }
    },

    "/api/prescription/{prescription_id}/details": {
        "post": {
            "summary": "Détail d'une ordonnance",
            "tags": ["Ordonnances"],
            "security": [],
            "parameters": [_path_param("prescription_id")],
            "responses": {
                "200": {
                    "description": "Ordonnance trouvée",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean"},
                            "data":    _ref("PrescriptionMobilePayload"),
                        },
                    }),
                },
            },
        }
    },

    "/api/prescription/line/{line_id}/delete": {
        "post": {
            "summary": "Supprimer une ligne d'ordonnance (marquer comme supprimée)",
            "tags": ["Ordonnances"],
            "security": [],
            "parameters": [_path_param("line_id")],
            "responses": {
                "200": {
                    "description": "Ligne marquée supprimée",
                    "content": _json({"type": "object", "properties": {"success": {"type": "boolean"}}}),
                },
            },
        }
    },

    "/api/prescription/line/{line_id}/update": {
        "post": {
            "summary": "Modifier une ligne d'ordonnance",
            "tags": ["Ordonnances"],
            "security": [],
            "parameters": [_path_param("line_id")],
            "requestBody": {
                "required": False,
                "content": _json({
                    "type": "object",
                    "properties": {
                        "drug_name": {"type": "string"},
                        "dosage":    {"type": "string"},
                        "form":      {"type": "string"},
                        "quantity":  {"type": "string"},
                    },
                }),
            },
            "responses": {
                "200": {
                    "description": "Ligne mise à jour",
                    "content": _json({"type": "object", "properties": {"success": {"type": "boolean"}}}),
                },
            },
        }
    },

    "/api/prescription/{prescription_id}/add_line": {
        "post": {
            "summary": "Ajouter une ligne à une ordonnance",
            "tags": ["Ordonnances"],
            "security": [],
            "parameters": [_path_param("prescription_id")],
            "requestBody": {
                "required": False,
                "content": _json({
                    "type": "object",
                    "properties": {
                        "drug_name": {"type": "string"},
                        "dosage":    {"type": "string"},
                        "form":      {"type": "string"},
                        "quantity":  {"type": "string"},
                        "duration":  {"type": "string"},
                    },
                }),
            },
            "responses": {
                "200": {
                    "description": "Ligne créée",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean"},
                            "line_id": {"type": "integer"},
                        },
                    }),
                },
            },
        }
    },

    "/api/prescription/{prescription_id}/check_availability": {
        "post": {
            "summary": "Vérifier la disponibilité des médicaments d'une ordonnance",
            "tags": ["Ordonnances"],
            "security": [],
            "parameters": [_path_param("prescription_id")],
            "responses": {
                "200": {
                    "description": "Résultats de disponibilité",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean"},
                            "results": {"type": "object"},
                            "data":    _ref("PrescriptionMobilePayload"),
                        },
                    }),
                },
            },
        }
    },

    "/api/prescription/line/{line_id}/choose_alternative": {
        "post": {
            "summary": "Accepter ou refuser un médicament alternatif",
            "tags": ["Ordonnances"],
            "security": [],
            "parameters": [_path_param("line_id")],
            "requestBody": {
                "required": True,
                "content": _json({
                    "type": "object",
                    "required": ["accept_alternative"],
                    "properties": {
                        "accept_alternative": {"type": "boolean", "example": True},
                    },
                }),
            },
            "responses": {
                "200": {
                    "description": "Choix enregistré",
                    "content": _json({"type": "object", "properties": {"success": {"type": "boolean"}}}),
                },
            },
        }
    },

    # ── Routes POS ────────────────────────────────────────────────────────────

    "/pos/prescription/upload_for_order": {
        "post": {
            "summary": "Uploader une ordonnance pour une commande POS",
            "description": "Associe une ordonnance à une commande POS existante. Auth utilisateur requis.",
            "tags": ["Ordonnances", "POS"],
            "security": [{"cookieAuth": []}],
            "requestBody": {
                "required": True,
                "content": _json({
                    "type": "object",
                    "required": ["order_id", "file_base64"],
                    "properties": {
                        "order_id":    {"type": "integer", "example": 100},
                        "filename":    {"type": "string",  "example": "ordonnance.jpg"},
                        "file_base64": {"type": "string"},
                        "mimetype":    {"type": "string",  "example": "image/jpeg"},
                    },
                }),
            },
            "responses": {
                "200": {
                    "description": "Ordonnance créée et associée",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success":         {"type": "boolean"},
                            "data":            _ref("PrescriptionMobilePayload"),
                            "prescription_id": {"type": "integer"},
                        },
                    }),
                },
            },
        }
    },

    "/pos/prescription/scan": {
        "post": {
            "summary": "Scanner une ordonnance au kiosque POS",
            "description": "Crée une ordonnance depuis le scanner kiosque sans commande POS associée. Auth utilisateur requis.",
            "tags": ["Ordonnances", "POS"],
            "security": [{"cookieAuth": []}],
            "requestBody": {
                "required": True,
                "content": _json({
                    "type": "object",
                    "required": ["file_base64"],
                    "properties": {
                        "filename":    {"type": "string",  "example": "ordonnance.jpg"},
                        "file_base64": {"type": "string"},
                        "mimetype":    {"type": "string",  "example": "image/jpeg"},
                        "ticket_id":   {"type": "integer", "nullable": True},
                    },
                }),
            },
            "responses": {
                "200": {
                    "description": "Ordonnance scannée",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success":         {"type": "boolean"},
                            "prescription_id": {"type": "integer"},
                            "data":            _ref("PrescriptionMobilePayload"),
                        },
                    }),
                },
            },
        }
    },

    "/pos/prescription/get_product_for_pos": {
        "post": {
            "summary": "Récupérer un produit pour le POS",
            "description": (
                "Retourne les informations d'un product.product pour l'intégration POS. "
                "Auth utilisateur requis. "
                "Note : cette route est définie deux fois dans le contrôleur source — "
                "seule la première définition est active."
            ),
            "tags": ["POS"],
            "security": [{"cookieAuth": []}],
            "requestBody": {
                "required": True,
                "content": _json({
                    "type": "object",
                    "required": ["product_id"],
                    "properties": {
                        "product_id": {"type": "integer", "example": 42},
                    },
                }),
            },
            "responses": {
                "200": {
                    "description": "Produit trouvé",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean"},
                            "data": {
                                "type": "object",
                                "properties": {
                                    "id":           {"type": "integer"},
                                    "display_name": {"type": "string"},
                                    "lst_price":    {"type": "number"},
                                },
                            },
                        },
                    }),
                },
            },
        }
    },

    # ═══════════════════════════════ PRESCRIPTIONS (MOBILE) ══════════════════
    # AJOUT : PrescriptionMobileController
    # Note : ces routes dupliquent en partie PrescriptionApiController
    # mais sont distinctes (préfixe /mobile/).

    "/api/prescription/{prescription_id}/mobile/details": {
        "post": {
            "summary": "Détail mobile d'une ordonnance",
            "tags": ["Ordonnances Mobile"],
            "security": [],
            "parameters": [_path_param("prescription_id")],
            "responses": {
                "200": {
                    "description": "Ordonnance trouvée",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean"},
                            "data":    _ref("PrescriptionMobilePayload"),
                        },
                    }),
                },
            },
        }
    },

    "/api/prescription/line/{line_id}/mobile/delete": {
        "post": {
            "summary": "Supprimer une ligne (mobile)",
            "tags": ["Ordonnances Mobile"],
            "security": [],
            "parameters": [_path_param("line_id")],
            "responses": {
                "200": {
                    "description": "Ligne marquée supprimée",
                    "content": _json({"type": "object", "properties": {"success": {"type": "boolean"}}}),
                },
            },
        }
    },

    "/api/prescription/line/{line_id}/mobile/update": {
        "post": {
            "summary": "Modifier une ligne (mobile)",
            "tags": ["Ordonnances Mobile"],
            "security": [],
            "parameters": [_path_param("line_id")],
            "requestBody": {
                "required": False,
                "content": _json({
                    "type": "object",
                    "properties": {
                        "drug_name": {"type": "string"},
                        "dosage":    {"type": "string"},
                        "form":      {"type": "string"},
                        "quantity":  {"type": "string"},
                    },
                }),
            },
            "responses": {
                "200": {
                    "description": "Ligne mise à jour",
                    "content": _json({"type": "object", "properties": {"success": {"type": "boolean"}}}),
                },
            },
        }
    },

    "/api/prescription/{prescription_id}/mobile/add_line": {
        "post": {
            "summary": "Ajouter une ligne (mobile)",
            "tags": ["Ordonnances Mobile"],
            "security": [],
            "parameters": [_path_param("prescription_id")],
            "requestBody": {
                "required": False,
                "content": _json({
                    "type": "object",
                    "properties": {
                        "drug_name": {"type": "string"},
                        "dosage":    {"type": "string"},
                        "form":      {"type": "string"},
                        "quantity":  {"type": "string"},
                        "duration":  {"type": "string"},
                    },
                }),
            },
            "responses": {
                "200": {
                    "description": "Ligne créée",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean"},
                            "line_id": {"type": "integer"},
                        },
                    }),
                },
            },
        }
    },

    "/api/prescription/{prescription_id}/mobile/confirm": {
        "post": {
            "summary": "Confirmer les lignes d'une ordonnance (mobile)",
            "description": "Appelle action_evaluate_mobile_lines() sur l'ordonnance.",
            "tags": ["Ordonnances Mobile"],
            "security": [],
            "parameters": [_path_param("prescription_id")],
            "responses": {
                "200": {
                    "description": "Ordonnance confirmée",
                    "content": _json({
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean"},
                            "results": {"type": "object"},
                            "data":    _ref("PrescriptionMobilePayload"),
                        },
                    }),
                },
            },
        }
    },

    "/api/prescription/line/{line_id}/mobile/alternative": {
        "post": {
            "summary": "Choisir un alternatif (mobile)",
            "tags": ["Ordonnances Mobile"],
            "security": [],
            "parameters": [_path_param("line_id")],
            "requestBody": {
                "required": True,
                "content": _json({
                    "type": "object",
                    "required": ["accept_alternative"],
                    "properties": {
                        "accept_alternative": {"type": "boolean", "example": True},
                    },
                }),
            },
            "responses": {
                "200": {
                    "description": "Choix enregistré",
                    "content": _json({"type": "object", "properties": {"success": {"type": "boolean"}}}),
                },
            },
        }
    },
}
# -*- coding: utf-8 -*-

from odoo.http import request


def get_openai_config():
    icp = request.env["ir.config_parameter"].sudo()
    api_key = icp.get_param("qpharma_ocr.openai_api_key") or ""
    model = icp.get_param("qpharma_ocr.openai_model") or "gpt-4o"
    return {
        "api_key": str(api_key).strip(),
        "model": str(model).strip() or "gpt-4o",
    }


def safe_messages(history):
    """
    Nettoie et limite l'historique de conversation envoyé à OpenAI.
    - Garde uniquement les rôles 'user' et 'assistant'
    - Ignore les messages vides ou malformés
    - Limite aux 20 derniers échanges pour éviter de dépasser le context window
    """
    result = []

    for item in history[-20:]:
        if not isinstance(item, dict):
            continue

        role = item.get("role", "")
        content = item.get("content", "")

        if role not in ("user", "assistant"):
            continue
        if not isinstance(content, str) or not content.strip():
            continue

        result.append({
            "role": role,
            "content": content.strip(),
        })

    return result


def build_suggestions(products):
    """
    Construit les chips d'action affichées sous les messages du bot.
    3 types : add_to_cart, rx_required, unavailable.
    """
    suggestions = []

    for product in products:
        if product.get("disponible") and not product.get("necessite_ordonnance"):
            suggestions.append({
                "type": "add_to_cart",
                "label": f"أضف {product['nom']} للسلة",
                "product_id": product["product_id"],
            })
        elif product.get("necessite_ordonnance"):
            suggestions.append({
                "type": "rx_required",
                "label": f"{product['nom']} يحتاج وصفة",
                "product_id": product["product_id"],
            })
        elif not product.get("disponible"):
            suggestions.append({
                "type": "unavailable",
                "label": f"{product['nom']} غير متوفر",
                "product_id": product["product_id"],
            })

    return suggestions


def build_stock_context(products):
    """
    Construit le contexte stock injecté dans le prompt système OpenAI.

    CORRECTION: product.template n'a pas de champ tva_taux — c'est un champ
    calculé fictif côté frontend. On utilise directement prix_vente_tnd
    qui est déjà le prix TTC dans ce modèle pharmacie (TVA incluse ou nulle).
    On utilise aussi getattr() avec fallback pour tous les champs optionnels
    afin d'éviter AttributeError si le modèle évolue.
    """
    if not products:
        return ""

    lines = ["=== معلومات المخزون ==="]

    for product in products:
        # FIX: pas de tva_taux sur product.template — prix_vente_tnd est le prix final
        prix = round(float(getattr(product, "prix_vente_tnd", 0) or 0), 3)

        # FIX: quantite_stock est un champ computed, utiliser getattr avec fallback
        stock_qty = float(getattr(product, "quantite_stock", 0) or 0)
        disponible = stock_qty > 0

        status = "✅ متوفر" if disponible else "❌ غير متوفر"

        # FIX: necessite_ordonnance peut être absent sur certaines variantes
        necessite_rx = bool(getattr(product, "necessite_ordonnance", False))
        rx = " (يحتاج وصفة)" if necessite_rx else ""

        # Nom : préférer nom_commercial, fallback sur name
        nom = getattr(product, "nom_commercial", None) or getattr(product, "name", "")
        dosage = getattr(product, "dosage", "") or ""

        lines.append(
            f"- {nom} | "
            f"{dosage} | "
            f"{status}{rx} | السعر: {prix} دينار | "
            f"product_id:{product.id}"
        )

        # Proposer des alternatives uniquement si : non disponible ET sans ordonnance
        if not disponible and not necessite_rx:
            try:
                alternatives = product.chatbot_search_alternatives(limit=3)
            except Exception:
                alternatives = []

            if alternatives:
                lines.append("  alternatives disponibles:")
                for alt in alternatives:
                    alt_prix = round(float(getattr(alt, "prix_vente_tnd", 0) or 0), 3)
                    alt_nom = getattr(alt, "nom_commercial", None) or getattr(alt, "name", "")
                    alt_dosage = getattr(alt, "dosage", "") or ""
                    lines.append(
                        f"  - {alt_nom} | "
                        f"{alt_dosage} | متوفر | "
                        f"{alt_prix} دينار | product_id:{alt.id}"
                    )

    lines.append("===================")
    return "\n".join(lines)
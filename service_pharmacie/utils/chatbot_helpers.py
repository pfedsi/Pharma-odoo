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
    if not products:
        return ""

    lines = ["=== معلومات المخزون ==="]

    for product in products:
        qty = int(product.quantite_stock or 0)
        prix = round(
            float(product.prix_vente_tnd or 0.0) * (1 + (float(product.tva_taux or "0")) / 100.0),
            3,
        )
        status = "✅ متوفر" if qty > 0 else "❌ غير متوفر"
        rx = " (يحتاج وصفة)" if product.necessite_ordonnance else ""

        lines.append(
            f"- {product.nom_commercial or product.name} | {product.dosage or ''} | "
            f"{status}{rx} | كمية: {qty} | السعر: {prix} دينار | product_id:{product.id}"
        )

        if qty <= 0 and not product.necessite_ordonnance:
            alternatives = product.chatbot_search_alternatives(limit=3)
            if alternatives:
                lines.append("  alternatives disponibles:")
                for alt in alternatives:
                    alt_qty = int(alt.quantite_stock or 0)
                    alt_price = round(
                        float(alt.prix_vente_tnd or 0.0) * (1 + (float(alt.tva_taux or "0")) / 100.0),
                        3,
                    )
                    lines.append(
                        f"  - {alt.nom_commercial or alt.name} | {alt.dosage or ''} | "
                        f"✅ متوفر | كمية: {alt_qty} | السعر: {alt_price} دينار | product_id:{alt.id}"
                    )

    lines.append("===================")
    return "\n".join(lines)
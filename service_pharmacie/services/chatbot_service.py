# -*- coding: utf-8 -*-

import logging
import requests

from odoo.http import request

from ..utils.chatbot_helpers import (
    get_openai_config,
    safe_messages,
    build_suggestions,
    build_stock_context,
)
from ..utils.panier_utils import load_panier, save_panier

_logger = logging.getLogger(__name__)


class ChatbotService:

    CHATBOT_SYSTEM_PROMPT = """
أنت QPharmaBot، المساعد الصيدلي الذكي لـ Q-Pharma TN (تونس).
تتحدث دائمًا باللهجة التونسية بطريقة طبيعية، واضحة، ومهنية.

المجالات اللي تنجم تعاون فيها فقط:
- الأدوية: الاستعمال، الجرعات العامة، الآثار الجانبية، التفاعلات، الموانع
- توفر الأدوية في المخزون
- المعادلات الجنيسة المتوفرة في تونس
- نصائح الحمية والتغذية العامة
- خدمات الصيدلية
- نصائح الاستعمال السليم والتخزين
- التوعية الصحية العامة غير التشخيصية

حدودك:
- تجاوب فقط على الأسئلة المتعلقة بالصحة، الأدوية، الصيدلية، التغذية، والخدمات المرتبطة بهم
- إذا كان السؤال خارج هالمجالات، اعتذر بلطف وقل إنك مختص فقط في الصحة والأدوية
- لا تجاوب على أسئلة في السياسة، البرمجة، الدراسة، الرياضة، الأخبار، الترفيه، أو أي موضوع خارج اختصاصك
- لا تكتب تشخيصًا طبيًا أبدًا
- لا تعوّض الطبيب أو الصيدلي أو الاستعجالي
- لا تعطي تعليمات خطيرة أو غير آمنة أو تجريبية

ممنوعات صارمة:
- ممنوع تقديم أي مساعدة تخص المخدرات أو المواد الممنوعة أو طرق الاستعمال أو التصنيع أو الإخفاء أو الشراء
- ممنوع تقديم نصائح حول إساءة استعمال الأدوية أو الجرعات الخطيرة أو الخلطات الخطيرة
- ممنوع شرح طرق الانتحار، إيذاء النفس، أو إيذاء الآخرين
- ممنوع إعطاء وصفات علاجية نهائية أو تأكيد مرض معيّن
- ممنوع اقتراح أدوية تصرف بوصفة كبديل آمن بدون تنبيه واضح لضرورة الرجوع لمهني صحة

قواعد الرد:
- كن ودودًا، موجزًا، ومهنيًا
- جاوب بطريقة مفهومة وبسيطة
- إذا كان المنتج متوفر في المخزون، أعلم المستخدم بوضوح وقل له ينجم يضيفه للسلة
- إذا كان المنتج متوفر ويستلزم وصفة طبية، أعلم المستخدم بوضوح أنه متوفر لكن صرفه يتطلب ordonnance / وصفة طبية
- إذا كان المنتج غير متوفر وما يحتاجش وصفة، تنجم تقترح alternatives متوفرة في المخزون فقط
- إذا كان المنتج غير متوفر ويحتاج وصفة، لا تقترح أي alternative
- إذا كانت المعلومة غير أكيدة أو ناقصة، قل هذا بوضوح
- في الحالات الحساسة، انصح المستخدم بالتواصل مع طبيب أو صيدلي
- في الحالات المستعجلة أو الخطيرة، اطلب منه يتوجه فورًا للاستعجالي أو يكلم طبيب حالًا

أسلوب الرفض خارج الاختصاص:
"نعتذر، أنا نعاون فقط في الأسئلة المتعلقة بالأدوية، الصحة، والتغذية. إذا عندك سؤال في هالمجال، مرحبا."

أسلوب الرفض للمخدرات أو الطلبات الخطيرة:
"ما نجمش نعاون في الطلب هذا. إذا عندك سؤال صحي أو دوائي آمن، نعاونك بكل سرور."

تذكير مهم:
- إذا لزم الأمر، شجّع المستخدم على استشارة طبيب أو صيدلي
- لا تخرج عن اختصاصك مهما كان السؤال
""".strip()

    @classmethod
    def handle_message(cls, payload):
        message = (payload.get("message") or "").strip()
        history = payload.get("history") or []

        if not message:
            return {"success": False, "error": "Message vide."}

        cfg = get_openai_config()
        if not cfg["api_key"]:
            return {"success": False, "error": "Clé OpenAI non configurée."}

        products_rs = request.env["product.template"].sudo().chatbot_search_products(
        message,
        limit=3
    )
        stock_context = build_stock_context(products_rs)

        system_content = cls.CHATBOT_SYSTEM_PROMPT
        if stock_context:
            system_content += f"\n\n{stock_context}"

        messages = [{"role": "system", "content": system_content}]
        messages += safe_messages(history)
        messages.append({"role": "user", "content": message})

        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {cfg['api_key']}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": cfg["model"],
                    "max_tokens": 800,
                    "temperature": 0.65,
                    "messages": messages,
                },
                timeout=30,
            )
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            return {"success": False, "error": "OpenAI timeout. حاول مرة أخرى."}
        except requests.exceptions.RequestException as e:
            _logger.exception("QPharmaBot OpenAI error")
            return {"success": False, "error": f"خطأ في الاتصال: {e}"}
        except Exception as e:
            _logger.exception("QPharmaBot unexpected error")
            return {"success": False, "error": f"خطأ غير متوقع: {e}"}

        try:
            data = resp.json()
        except ValueError:
            _logger.error("Réponse OpenAI non-JSON : %s", resp.text[:200])
            return {"success": False, "error": "Réponse inattendue d'OpenAI."}

        if not resp.ok:
            msg = data.get("error", {}).get("message", f"HTTP {resp.status_code}")
            _logger.error("OpenAI erreur : %s", msg)
            return {"success": False, "error": f"OpenAI : {msg}"}

        reply_text = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

        if not reply_text:
            return {"success": False, "error": "OpenAI لم يُرجع جوابًا."}

        products_found = [p.chatbot_to_dict() for p in products_rs]

        return {
            "success": True,
            "reply": reply_text,
            "products": products_found,
            "suggestions": build_suggestions(products_found),
        }

    @staticmethod
    def get_stock(payload):
        product_id = payload.get("product_id")
        if not product_id:
            return {"success": False, "error": "product_id manquant."}

        product = request.env["product.template"].sudo().browse(int(product_id))
        if not product.exists():
            return {"success": False, "error": "Produit introuvable."}

        return {
            "success": True,
            "product": product.chatbot_to_dict(),
        }

    @staticmethod
    def get_panier(_payload=None):
        panier = load_panier()

        ids = [line["product_id"] for line in panier]
        products = {
            p.id: p
            for p in request.env["product.template"].sudo().browse(ids)
            if p.exists()
        }

        lignes_valides = []
        for ligne in panier:
            product = products.get(ligne["product_id"])
            if product:
                ligne["stock"] = int(product.quantite_stock or 0)
                ligne["disponible"] = ligne["stock"] > 0
                ligne["alerte"] = ligne["quantite"] > ligne["stock"]
                lignes_valides.append(ligne)

        total_ttc = sum(
            float(line.get("prix_ttc", 0.0) or 0.0) * int(line.get("quantite", 0) or 0)
            for line in lignes_valides
        )

        return {
            "success": True,
            "lignes": lignes_valides,
            "total_ttc": round(total_ttc, 3),
            "nb_articles": sum(int(line.get("quantite", 0) or 0) for line in lignes_valides),
        }

    @staticmethod
    def add_to_panier(payload):
        product_id = payload.get("product_id")
        quantite = max(1, int(payload.get("quantite") or 1))

        if not product_id:
            return {"success": False, "error": "product_id manquant."}

        product = request.env["product.template"].sudo().browse(int(product_id))
        if not product.exists():
            return {"success": False, "error": "Produit introuvable."}

        stock = int(product.quantite_stock or 0)
        if stock <= 0:
            return {
                "success": False,
                "error": "هذا الدواء ما متوفرش في المخزون.",
                "disponible": False,
            }

        if quantite > stock:
            return {
                "success": False,
                "error": f"الكمية المطلوبة ({quantite}) أكبر من المتوفر ({stock}).",
                "stock_disponible": stock,
            }

        panier = load_panier()

        for line in panier:
            if line["product_id"] == int(product_id):
                new_qty = int(line["quantite"]) + quantite
                if new_qty > stock:
                    return {
                        "success": False,
                        "error": f"الكمية الإجمالية ({new_qty}) تتجاوز المخزون ({stock}).",
                    }
                line["quantite"] = new_qty
                save_panier(panier)
                return {
                    "success": True,
                    "panier": panier,
                    "action": "updated",
                }

        panier.append(product.chatbot_to_dict(qty=quantite))
        save_panier(panier)

        return {
            "success": True,
            "panier": panier,
            "action": "added",
            "message": f"تمت إضافة {product.nom_commercial or product.name} للسلة ✅",
        }

    @staticmethod
    def modify_panier(payload):
        product_id = payload.get("product_id")
        quantite = int(payload.get("quantite") or 0)

        if not product_id:
            return {"success": False, "error": "product_id manquant."}

        product_id = int(product_id)
        panier = load_panier()

        if quantite <= 0:
            panier = [line for line in panier if line["product_id"] != product_id]
        else:
            product = request.env["product.template"].sudo().browse(product_id)
            stock = int(product.quantite_stock or 0) if product.exists() else 0
            if quantite > stock:
                return {"success": False, "error": f"الكمية تتجاوز المخزون ({stock})."}

            for line in panier:
                if line["product_id"] == product_id:
                    line["quantite"] = quantite
                    break

        save_panier(panier)
        return {"success": True, "panier": panier}

    @staticmethod
    def clear_panier(_payload=None):
        save_panier([])
        return {"success": True, "message": "السلة فارغة الآن."}

    @staticmethod
    def confirm_panier(payload):
        panier = load_panier()

        if not panier:
            return {"success": False, "error": "السلة فارغة."}

        partner_id = payload.get("partner_id")
        notes = payload.get("notes") or ""

        if partner_id:
            partner = request.env["res.partner"].sudo().browse(int(partner_id))
            if not partner.exists():
                partner_id = None

        if not partner_id:
            partner = request.env["res.partner"].sudo().search(
                [("name", "=", "Client Comptoir")],
                limit=1,
            )
            if not partner:
                partner = request.env["res.partner"].sudo().create({
                    "name": "Client Comptoir",
                })
            partner_id = partner.id

        order = request.env["sale.order"].sudo().create({
            "partner_id": partner_id,
            "note": notes,
            "origin": "QPharmaBot",
        })

        for line in panier:
            tmpl = request.env["product.template"].sudo().browse(line["product_id"])
            if not tmpl.exists():
                continue

            variant = tmpl.product_variant_id
            if not variant:
                continue

            request.env["sale.order.line"].sudo().create({
                "order_id": order.id,
                "product_id": variant.id,
                "product_uom_qty": line["quantite"],
                "price_unit": line["prix_ttc"],
            })

        save_panier([])

        return {
            "success": True,
            "order_id": order.id,
            "order_name": order.name,
            "message": f"تم تأكيد طلبك رقم {order.name} ✅ انتظر دورك في الصيدلية.",
        }
# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.http import request
import base64

class ParapharmacieController(http.Controller):
  
    @http.route('/api/parapharma/image/<int:product_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def product_image(self, product_id, **kwargs):
        product = request.env['product.template'].sudo().browse(product_id)
        if not product.exists() or not product.image_128:
            return request.not_found()

        image_bytes = base64.b64decode(product.image_128)
        headers = [
            ('Content-Type', 'image/png'),
            ('Cache-Control', 'public, max-age=86400'),
            ('Access-Control-Allow-Origin', '*'),
        ]
        return request.make_response(image_bytes, headers=headers)
    def _serialize_product(self, p, full=False):
        """Sérialise un product.template en dict JSON-friendly."""
        
        unique = int(p.write_date.timestamp() * 1000) if p.write_date else 0
        image_url = f"https://demopharma.eprswarm.com/api/parapharma/image/{p.id}?unique={unique}"
        
        base = {
            "id": p.id,
            "nom_commercial": p.nom_commercial or p.name,
            "nom_generique": p.nom_generique or "",
            "name": p.name,
            "dosage": p.dosage or "",
            "fabricant": p.fabricant or "",
            "prix_vente_tnd": round(p.prix_vente_tnd or 0.0, 3),
            "prix_achat_tnd": round(p.prix_achat_tnd or 0.0, 3),
            "tva_taux": p.tva_taux or "19",
            "forme_galenique": p.forme_galenique_id.name if p.forme_galenique_id else "",
            "forme_galenique_id": p.forme_galenique_id.id if p.forme_galenique_id else None,
            "quantite_stock": p.quantite_stock or 0,
            "disponible": (p.quantite_stock or 0) > 0,
            "necessite_ordonnance": bool(p.necessite_ordonnance),
            "parapharmaceutique": bool(p.parapharmaceutique),
            "image_url": image_url,  # ✅ corrigé
        }

        if full:
            base.update({
                "description_pharmacie": p.description_pharmacie or "",
                "code_barre_pharmacie": p.code_barre_pharmacie or "",
                "seuil_alerte_stock": p.seuil_alerte_stock or 0.0,
                "alerte_stock": bool(p.alerte_stock),
                "lot_count": p.lot_count or 0,
                "prix_ttc": round(
                    (p.prix_vente_tnd or 0.0) * (1 + int(p.tva_taux or 0) / 100), 3
                ),
            })

        return base

    def _json_response(self, data, status=200):
        return request.make_response(
            json.dumps(data, ensure_ascii=False),
            headers=[
                ("Content-Type", "application/json; charset=utf-8"),
                ("Access-Control-Allow-Origin", "*"),
            ],
            status=status,
        )

    def _error(self, message, status=400):
        return self._json_response({"success": False, "message": message}, status=status)

    # ── /api/pharmacie/parapharmaceutique  (liste) ────────────────────

    @http.route(
        "/api/pharmacie/parapharmaceutique",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def liste_parapharmaceutique(self, **kwargs):
        try:
            # Paramètres de pagination et filtrage
            page = max(1, int(kwargs.get("page", 1)))
            limit = min(50, max(1, int(kwargs.get("limit", 20))))
            offset = (page - 1) * limit

            forme_id = kwargs.get("forme_galenique_id")
            disponible_only = kwargs.get("disponible", "").lower() in ("1", "true", "yes")

            domain = [
                ("parapharmaceutique", "=", True),
                ("active", "=", True),
            ]
            if forme_id:
                domain.append(("forme_galenique_id", "=", int(forme_id)))

            Product = request.env["product.template"].sudo()
            total = Product.search_count(domain)
            products = Product.search(domain, limit=limit, offset=offset, order="name asc")

            if disponible_only:
                products = products.filtered(lambda p: (p.quantite_stock or 0) > 0)

            data = {
                "success": True,
                "total": total,
                "page": page,
                "limit": limit,
                "pages": max(1, -(-total // limit)),  # ceil division
                "products": [self._serialize_product(p) for p in products],
            }
        except Exception as e:
            return self._error("Erreur serveur : %s" % str(e), 500)

        return self._json_response(data)

    # ── /api/pharmacie/parapharmaceutique/<id>  (détail) ─────────────

    @http.route(
        "/api/pharmacie/parapharmaceutique/<int:product_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def detail_parapharmaceutique(self, product_id, **kwargs):
        try:
            product = request.env["product.template"].sudo().browse(product_id)
            if not product.exists() or not product.parapharmaceutique:
                return self._error("Produit parapharmaceutique introuvable.", 404)

            data = {
                "success": True,
                "product": self._serialize_product(product, full=True),
            }
        except Exception as e:
            return self._error("Erreur serveur : %s" % str(e), 500)

        return self._json_response(data)

    

    # ── /api/pharmacie/parapharmaceutique/search  (POST) ─────────────

    @http.route(
        "/api/pharmacie/parapharmaceutique/search",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def search_parapharmaceutique(self, **kwargs):
        try:
            body = json.loads(request.httprequest.data or b"{}")
            query = (body.get("query") or "").strip()
            page = max(1, int(body.get("page", 1)))
            limit = min(50, max(1, int(body.get("limit", 20))))
            offset = (page - 1) * limit

            if not query:
                return self._error("Le champ 'query' est requis.")

            domain = [
                ("parapharmaceutique", "=", True),
                ("active", "=", True),
                "|", "|", "|",
                ("name", "ilike", query),
                ("nom_commercial", "ilike", query),
                ("nom_generique", "ilike", query),
                ("description_pharmacie", "ilike", query),
            ]

            Product = request.env["product.template"].sudo()
            total = Product.search_count(domain)
            products = Product.search(domain, limit=limit, offset=offset, order="name asc")

            data = {
                "success": True,
                "query": query,
                "total": total,
                "page": page,
                "limit": limit,
                "products": [self._serialize_product(p) for p in products],
            }
        except Exception as e:
            return self._error("Erreur serveur : %s" % str(e), 500)

        return self._json_response(data)

    # ── /api/pharmacie/panier/calculer  (POST) ────────────────────────
    #
    # Body attendu :
    # {
    #   "articles": [
    #     { "product_id": 42, "quantite": 2 },
    #     { "product_id": 17, "quantite": 1 }
    #   ]
    # }
    @http.route(
        "/api/pharmacie/panier/calculer",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def calculer_panier(self, **kwargs):
        try:
            body = json.loads(request.httprequest.data or b"{}")
            articles = body.get("articles", [])

            if not articles:
                return self._error("La liste 'articles' est vide ou absente.")

            Product = request.env["product.template"].sudo()
            lignes = []
            total_ht = 0.0
            total_tva = 0.0
            erreurs = []

            for item in articles:
                pid = item.get("product_id")
                qty = max(0, int(item.get("quantite", 0)))

                if not pid:
                    erreurs.append({"product_id": pid, "message": "product_id manquant."})
                    continue

                product = Product.browse(pid)

                # ✅ Accepte parapharmaceutique OU médicament
                if not product.exists() or not (
                    product.parapharmaceutique or product.is_medicament
                ):
                    erreurs.append({
                        "product_id": pid,
                        "message": "Produit introuvable ou non autorisé.",
                    })
                    continue

                if qty == 0:
                    continue

                prix_ht = product.prix_vente_tnd or 0.0
                # ✅ TVA réelle depuis Odoo, pas depuis le client
                taux_tva = int(product.tva_taux or 0) / 100
                montant_ht = round(prix_ht * qty, 3)
                montant_tva = round(montant_ht * taux_tva, 3)
                montant_ttc = round(montant_ht + montant_tva, 3)

                total_ht += montant_ht
                total_tva += montant_tva

                lignes.append({
                    "product_id": pid,
                    "nom_commercial": product.nom_commercial or product.name,
                    "quantite": qty,
                    "prix_unitaire_ht": round(prix_ht, 3),
                    "tva_taux": product.tva_taux or "0",
                    "montant_ht": montant_ht,
                    "montant_tva": montant_tva,
                    "montant_ttc": montant_ttc,
                    "stock_disponible": int(product.quantite_stock or 0),
                    "alerte_stock_insuffisant": int(product.quantite_stock or 0) < qty,
                })

            total_ttc = round(total_ht + total_tva, 3)

            data = {
                "success": True,
                "lignes": lignes,
                "total_ht": round(total_ht, 3),
                "total_tva": round(total_tva, 3),
                "total_ttc": total_ttc,
                "nb_articles": sum(l["quantite"] for l in lignes),
                "erreurs": erreurs,
            }
        except Exception as e:
            return self._error("Erreur serveur : %s" % str(e), 500)

        return self._json_response(data)
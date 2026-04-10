# -*- coding: utf-8 -*-
import json
import re
from odoo import http
from odoo.http import request


class PharmacieController(http.Controller):

    def _normalize_text(self, value):
        """Normalisation basique : minuscules + strip."""
        return (value or "").strip().lower()

    def _normalize_dosage(self, value):
        """
        Normalise un dosage pour comparaison flexible.
        Exemples :
          "1000 mg" → "1000mg"
          "1 g"     → "1g"
          "1000MG"  → "1000mg"
          "500 Mg"  → "500mg"
        """
        s = (value or "").strip().lower()
        # Supprimer les espaces entre chiffres et unité
        s = re.sub(r'\s+', '', s)
        return s

    def _dosage_matches(self, dosage_db, dosage_search):
        """
        Compare deux dosages de façon flexible.
        Gère aussi la conversion g ↔ mg :
          "1g" == "1000mg"
        """
        if not dosage_search:
            return True  # pas de filtre dosage → on accepte tout

        d_db = self._normalize_dosage(dosage_db)
        d_sr = self._normalize_dosage(dosage_search)

        if not d_db:
            return False

        if d_db == d_sr:
            return True

        # Conversion g ↔ mg
        def to_mg(s):
            m = re.match(r'^([\d.]+)(mg|g)$', s)
            if not m:
                return None
            val, unit = float(m.group(1)), m.group(2)
            return val * 1000 if unit == 'g' else val

        mg_db = to_mg(d_db)
        mg_sr = to_mg(d_sr)
        if mg_db is not None and mg_sr is not None:
            return abs(mg_db - mg_sr) < 0.01

        return False

    def _get_available_qty(self, product):
        inventaires = request.env["pharmacie.inventaire"].sudo().search([
            ("product_id", "=", product.id),
            ("active", "=", True),
            ("state", "!=", "expire"),
        ])
        return sum(inventaires.mapped("quantite_en_stock")) if inventaires else 0

    def _find_product(self, nom=None, dosage=None, generique=None):
        Product = request.env["product.template"].sudo()

        nom = (nom or "").strip()
        dosage = (dosage or "").strip()
        generique = (generique or "").strip()

        domain = [("is_medicament", "=", True)]

        if nom:
            domain += [
                "|", "|",
                ("name", "ilike", nom),
                ("nom_commercial", "ilike", nom),
                ("nom_generique", "ilike", nom),
            ]

        products = Product.search(domain, limit=50)

        # ── Filtre dosage flexible ──────────────────────────────
        if dosage:
            filtered_dosage = products.filtered(
                lambda p: self._dosage_matches(p.dosage, dosage)
            )
            # Fallback : si aucun match dosage, on garde tous les résultats
            # plutôt que de retourner vide
            products = filtered_dosage if filtered_dosage else products

        # ── Filtre générique (optionnel, avec fallback) ─────────
        if generique:
            filtered_gen = products.filtered(
                lambda p: self._normalize_text(p.nom_generique) == self._normalize_text(generique)
                or self._normalize_text(generique) in self._normalize_text(p.nom_generique)
                or self._normalize_text(p.nom_generique) in self._normalize_text(generique)
            )
            products = filtered_gen if filtered_gen else products

        return products[:1]

    def _get_otc_suggestions(self, product, limit=5):
        Product = request.env["product.template"].sudo()

        domain = [
            ("is_medicament", "=", True),
            ("id", "!=", product.id),
            ("necessite_ordonnance", "=", False),
        ]

        candidates = Product.search(domain, limit=100)
        candidates = candidates.filtered(lambda p: self._get_available_qty(p) > 0)

        same_generic = candidates.filtered(
            lambda p: (
                product.nom_generique and
                self._normalize_text(p.nom_generique) == self._normalize_text(product.nom_generique)
            )
        )

        if same_generic and product.dosage:
            same_generic_dosage = same_generic.filtered(
                lambda p: self._dosage_matches(p.dosage, product.dosage)
            )
            candidates = same_generic_dosage if same_generic_dosage else same_generic
        elif same_generic:
            candidates = same_generic
        else:
            if product.dosage:
                same_dosage = candidates.filtered(
                    lambda p: self._dosage_matches(p.dosage, product.dosage)
                )
                if same_dosage:
                    candidates = same_dosage

        suggestions = []
        for p in candidates[:limit]:
            suggestions.append({
                "product_id": p.id,
                "nom": p.nom_commercial or p.name,
                "nom_generique": p.nom_generique or "",
                "dosage": p.dosage or "",
                "quantite_totale": self._get_available_qty(p),
                "prix_vente_tnd": p.prix_vente_tnd or 0.0,
                "necessite_ordonnance": bool(p.necessite_ordonnance),
            })

        return suggestions

    def _serialize_product_result(self, product):
        qty = self._get_available_qty(product)

        data = {
            "product_id": product.id,
            "name": product.name,
            "nom_commercial": product.nom_commercial or "",
            "nom_generique": product.nom_generique or "",
            "dosage": product.dosage or "",
            "prix_vente_tnd": product.prix_vente_tnd or 0.0,
            "quantite_totale": qty,
            "disponible": qty > 0,
            "necessite_ordonnance": bool(product.necessite_ordonnance),
            "suggestions": [],
        }

        if bool(product.necessite_ordonnance):
            data["message"] = "Médicament soumis à ordonnance. Retour médecin obligatoire."
        elif qty > 0:
            data["message"] = "Médicament disponible en stock."
        else:
            data["message"] = "Médicament OTC indisponible."
            data["suggestions"] = self._get_otc_suggestions(product)

        return data

    # ──────────────────────────────────────────────────────────────
    # /api/pharmacie/check_stock  (single)
    # ──────────────────────────────────────────────────────────────
    @http.route(
        "/api/pharmacie/check_stock",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def check_stock(self, **kwargs):
        try:
            body = json.loads(request.httprequest.data or b"{}")
            nom = body.get("nom")
            dosage = body.get("dosage")
            generique = body.get("generique")

            product = self._find_product(nom=nom, dosage=dosage, generique=generique)

            if not product:
                result = {"success": False, "message": "Médicament introuvable.", "data": None}
            else:
                result = {
                    "success": True,
                    "message": "Vérification terminée.",
                    "data": self._serialize_product_result(product[0]),
                }

        except Exception as e:
            result = {"success": False, "message": "Erreur serveur : %s" % str(e), "data": None}

        return request.make_response(
            json.dumps(result),
            headers=[("Content-Type", "application/json")],
        )

    # ──────────────────────────────────────────────────────────────
    # /api/pharmacie/check_many_stock  (batch)
    # ──────────────────────────────────────────────────────────────
    @http.route(
        "/api/pharmacie/check_many_stock",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def check_many_stock(self, **kwargs):
        try:
            body = json.loads(request.httprequest.data or b"{}")
            medicaments = body.get("medicaments", [])

            results = []

            for med in medicaments:
                nom = med.get("nom", "").strip()
                dosage = med.get("dosage", "").strip()
                generique = med.get("generique", "").strip()

                if not nom:
                    results.append({
                        "nom": nom,
                        "dosage": dosage,
                        "success": False,
                        "message": "Nom du médicament manquant.",
                        "data": None,
                    })
                    continue

                product = self._find_product(nom=nom, dosage=dosage, generique=generique)

                if not product:
                    results.append({
                        "nom": nom,
                        "dosage": dosage,
                        "success": False,
                        "message": "Médicament introuvable dans la base.",
                        "data": None,
                    })
                    continue

                data = self._serialize_product_result(product[0])
                results.append({
                    "nom": nom,
                    "dosage": dosage,
                    "success": True,
                    "message": data.get("message", "OK"),
                    "data": data,
                })

            response_data = {
                "success": True,
                "message": "Vérification terminée.",
                "results": results,
            }

        except Exception as e:
            response_data = {
                "success": False,
                "message": "Erreur serveur : %s" % str(e),
                "results": [],
            }

        return request.make_response(
            json.dumps(response_data),
            headers=[("Content-Type", "application/json")],
        )
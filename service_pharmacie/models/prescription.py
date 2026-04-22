from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import unicodedata
import logging

_logger = logging.getLogger(__name__)


class PharmacyPrescription(models.Model):
    _name = "pharmacy.prescription"
    _description = "Prescription"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(default="New", tracking=True)
    source_type = fields.Selection([
        ("virtual", "Client virtuel"),
        ("kiosk", "Client borne"),
    ], default="virtual", required=True, tracking=True)

    state = fields.Selection([
        ("draft", "Brouillon"),
        ("uploaded", "Uploadée"),
        ("to_review", "À vérifier"),
        ("validated", "Validée"),
        ("done", "Traitée"),
        ("rejected", "Rejetée"),
        ("error", "Erreur"),
    ], default="draft", tracking=True)

    attachment_id = fields.Many2one("ir.attachment", string="Fichier ordonnance")
    uploaded_file = fields.Binary(string="Ordonnance")
    uploaded_file_name = fields.Char(string="Nom du fichier")
    file_name = fields.Char(string="Nom du fichier")

    patient_name = fields.Char()
    doctor_name = fields.Char()
    prescription_date = fields.Char()

    raw_ai_result = fields.Text()
    pharmacist_note = fields.Text()

    line_ids = fields.One2many(
        "pharmacy.prescription.line",
        "prescription_id",
        string="Lignes ordonnance"
    )

    ticket_id = fields.Many2one("pharmacy.ticket")
    partner_id = fields.Many2one("res.partner")
    pos_order_id = fields.Many2one("pos.order", string="Commande POS")

    has_unmatched_lines = fields.Boolean(compute="_compute_flags")
    has_low_confidence = fields.Boolean(compute="_compute_flags")
    mobile_order_id = fields.Many2one(
        "pharmacy.mobile.order",
        string="Commande mobile",
        ondelete="set null",
    )

    reservation_id = fields.Many2one(
        "pharmacy.reservation",
        string="Réservation",
        ondelete="set null",
    )
    @api.depends("line_ids.product_id", "line_ids.confidence", "line_ids.needs_review")
    def _compute_flags(self):
        for rec in self:
            rec.has_unmatched_lines = any(not l.product_id for l in rec.line_ids)
            rec.has_low_confidence = any((l.confidence or 0.0) < 0.75 for l in rec.line_ids)

    def _compute_stock(self):
        for rec in self:
            for line in rec.line_ids:
                product_tmpl = line.product_id.product_tmpl_id if line.product_id else False
                qty = product_tmpl.quantite_stock if product_tmpl else 0.0

                line.qty_available = qty
                line.is_available = qty > 0
                line.is_partial = False

    @api.model
    def create_from_attachment(self, attachment, source_type="virtual", ticket_id=None, partner_id=None , pos_order_id=None):
        rec = self.create({
            "attachment_id": attachment.id,
            "source_type": source_type,
            "state": "uploaded",
            "ticket_id": ticket_id,
            "partner_id": partner_id,
            "pos_order_id": pos_order_id,
            "file_name": attachment.name,
        })
        rec.action_scan()
        return rec

    def action_save_attachment(self):
        for rec in self:
            if not rec.uploaded_file:
                raise UserError(_("Veuillez choisir un fichier."))

            filename = rec.uploaded_file_name or "ordonnance.jpg"
            lower_name = filename.lower()

            if lower_name.endswith(".png"):
                mimetype = "image/png"
            elif lower_name.endswith(".webp"):
                mimetype = "image/webp"
            elif lower_name.endswith(".gif"):
                mimetype = "image/gif"
            else:
                mimetype = "image/jpeg"

            attachment = self.env["ir.attachment"].create({
                "name": filename,
                "type": "binary",
                "datas": rec.uploaded_file,
                "res_model": rec._name,
                "res_id": rec.id,
                "mimetype": mimetype,
            })

            rec.attachment_id = attachment.id
            rec.file_name = attachment.name
            rec.state = "uploaded"

    def action_upload_and_scan(self):
        for rec in self:
            if not rec.attachment_id:
                rec.action_save_attachment()
            rec.action_scan()

    @api.model
    def _normalize_text(self, text):
        text = (text or "").strip().lower()
        text = unicodedata.normalize("NFD", text)
        text = "".join(c for c in text if unicodedata.category(c) != "Mn")
        return " ".join(text.split())

    @api.model
    def _find_best_product_match(self, search_name):
        ProductTemplate = self.env["product.template"].sudo()
        normalized_search = self._normalize_text(search_name)

        if not normalized_search:
            return False

        products = ProductTemplate.search([
            ("is_medicament", "=", True),
        ])

        _logger.info("Recherche produit pour: %s", search_name)
        _logger.info("Nom normalisé: %s", normalized_search)
        _logger.info("Total produits trouvés en base: %s", len(products))

        exact_match = False
        partial_match = False

        for p in products:
            values_to_test = [
                p.name or "",
                p.nom_generique or "",
                p.nom_commercial or "",
            ]

            normalized_values = [self._normalize_text(v) for v in values_to_test if v]

            for candidate in normalized_values:
                if normalized_search == candidate:
                    _logger.info("MATCH EXACT: %s", p.display_name)
                    exact_match = p
                    break

            if exact_match:
                break

        if exact_match:
            return exact_match

        for p in products:
            values_to_test = [
                p.name or "",
                p.nom_generique or "",
                p.nom_commercial or "",
            ]

            normalized_values = [self._normalize_text(v) for v in values_to_test if v]

            for candidate in normalized_values:
                if normalized_search in candidate or candidate in normalized_search:
                    _logger.info("MATCH PARTIEL: %s", p.display_name)
                    partial_match = p
                    break

            if partial_match:
                break

        return partial_match or False

    def action_scan(self):
        for rec in self:
            if not rec.attachment_id:
                raise UserError(_("Aucune pièce jointe."))

            result = self.env["pharmacy.openai.service"].extract_prescription(rec.attachment_id)

            rec.raw_ai_result = json.dumps(result, ensure_ascii=False, indent=2)
            rec.patient_name = result.get("patient_name", "")
            rec.doctor_name = result.get("doctor_name", "")
            rec.prescription_date = result.get("prescription_date", "")

            rec.line_ids.unlink()

            for med in result.get("medications", []):
                self.env["pharmacy.prescription.line"].create({
                    "prescription_id": rec.id,
                    "raw_label": med.get("raw_label", ""),
                    "extracted_name": med.get("drug_name", ""),
                    "dosage": med.get("dosage", ""),
                    "form": med.get("form", ""),
                    "quantity_text": med.get("quantity", ""),
                    "duration_text": med.get("duration", ""),
                    "confidence": med.get("confidence", 0.0),
                    "needs_review": True,
                })

            rec._match_products()
            rec._compute_stock()
            rec.state = "to_review"

    def export_client_payload(self):
        self.ensure_one()
        return {
            "prescription_id": self.id,
            "status": self.state,
            "patient_name": self.patient_name,
            "medications": [
                {
                    "line_id": l.id,
                    "name": l.corrected_name or l.extracted_name,
                    "raw_label": l.raw_label,
                    "dosage": l.dosage,
                    "form": l.form,
                    "quantity": l.quantity_text,
                    "duration": l.duration_text,
                    "confidence": l.confidence,
                    "matched_product_id": l.product_id.id if l.product_id else None,
                    "matched_product_name": l.product_id.display_name if l.product_id else None,
                    "available": l.is_available,
                    "available_qty": l.qty_available,
                    "needs_review": l.needs_review,
                }
                for l in self.line_ids
            ],
            "summary": {
                "total_lines": len(self.line_ids),
                "available_count": len(self.line_ids.filtered(lambda x: x.is_available)),
                "unavailable_count": len(self.line_ids.filtered(lambda x: not x.is_available)),
                "review_required": any(self.line_ids.mapped("needs_review")),
            }
        }

    def _find_equivalent_product(self, product_tmpl):
        self.ensure_one()

        domain = [
            ("id", "!=", product_tmpl.id),
            ("is_medicament", "=", True),
        ]

        if product_tmpl.forme_galenique_id:
            domain.append(("forme_galenique_id", "=", product_tmpl.forme_galenique_id.id))

        candidates = self.env["product.template"].search(domain)

        available_candidates = candidates.filtered(lambda p: (p.quantite_stock or 0) > 0)
        if not available_candidates:
            return False

        if product_tmpl.nom_generique:
            normalized_generic = self._normalize_text(product_tmpl.nom_generique)
            generic_match = available_candidates.filtered(
                lambda p: self._normalize_text(p.nom_generique) == normalized_generic
            )
            if generic_match:
                return generic_match[0]

        if product_tmpl.dosage:
            normalized_dosage = self._normalize_text(product_tmpl.dosage)
            dosage_match = available_candidates.filtered(
                lambda p: self._normalize_text(p.dosage) == normalized_dosage
            )
            if dosage_match:
                return dosage_match[0]

        return available_candidates[0] if available_candidates else False

    def _evaluate_confirmed_medication(self, line):
        product = line.product_id.product_tmpl_id if line.product_id else False

        if not product:
            return {
                "state": "not_found",
                "message": "Médicament non trouvé dans le catalogue.",
                "product_name": line.corrected_name or line.extracted_name,
                "requires_prescription": False,
                "available_qty": 0,
                "alternative": None,
            }

        available_qty = product.quantite_stock or 0
        requires_rx = bool(product.necessite_ordonnance)

        if available_qty > 0:
            if requires_rx:
                return {
                    "state": "available_rx_required",
                    "message": "Disponible en pharmacie. Ordonnance obligatoire lors du retrait.",
                    "product_name": product.display_name,
                    "requires_prescription": True,
                    "available_qty": available_qty,
                    "alternative": None,
                }
            return {
                "state": "available_no_rx",
                "message": "Disponible en pharmacie.",
                "product_name": product.display_name,
                "requires_prescription": False,
                "available_qty": available_qty,
                "alternative": None,
            }

        if requires_rx:
            return {
                "state": "out_of_stock_rx_required",
                "message": "Ce médicament est hors stock. Il nécessite une ordonnance. Veuillez consulter votre médecin pour une alternative.",
                "product_name": product.display_name,
                "requires_prescription": True,
                "available_qty": 0,
                "alternative": None,
            }

        alternative = self._find_equivalent_product(product)

        if alternative:
            return {
                "state": "out_of_stock_with_alternative",
                "message": "Ce médicament est hors stock. Une alternative disponible en pharmacie vous est proposée.",
                "product_name": product.display_name,
                "requires_prescription": False,
                "available_qty": 0,
                "alternative": {
                    "id": alternative.id,
                    "name": alternative.display_name,
                    "generic_name": alternative.nom_generique,
                    "dosage": alternative.dosage,
                    "form": alternative.forme_galenique_id.name if alternative.forme_galenique_id else "",
                    "stock_qty": alternative.quantite_stock,
                },
            }

        return {
            "state": "out_of_stock_no_alternative",
            "message": "Ce médicament est hors stock. Aucune alternative n'est disponible actuellement.",
            "product_name": product.display_name,
            "requires_prescription": False,
            "available_qty": 0,
            "alternative": None,
        }

    def action_evaluate_confirmed_lines(self):
        _logger.info("==== CLICK VERIFIER DISPONIBILITE ====")
        self.ensure_one()

        # Refaire le matching avant l'évaluation
        self._match_products()
        self._compute_stock()

        for line in self.line_ids:
            _logger.info(
                "Line: %s | corrected_name: %s | product_id: %s",
                line.extracted_name,
                line.corrected_name,
                line.product_id,
            )

        for line in self.line_ids.filtered(lambda l: l.is_confirmed_by_client):
            result = self._evaluate_confirmed_medication(line)
            _logger.info("Result for %s: %s", line.extracted_name, result)

            line.evaluation_state = result.get("state")
            line.evaluation_message = result.get("message")

            alt = result.get("alternative") or {}
            line.alternative_product_id = alt.get("id") if alt else False

        self.state = "validated"
    def _match_products(self):
        ProductTemplate = self.env["product.template"].sudo()

        for rec in self:
            for line in rec.line_ids:
                search_name = (line.corrected_name or line.extracted_name or "").strip()
                normalized_search = rec._normalize_text(search_name)

                _logger.info("==== MATCH DEBUG ====")
                _logger.info("OCR NAME: %s", search_name)
                _logger.info("OCR NAME NORMALIZED: %s", normalized_search)

                if not normalized_search:
                    _logger.info("-> Aucun nom trouvé")
                    line.product_id = False
                    line.needs_review = True
                    continue

                products = ProductTemplate.search([
                    ("is_medicament", "=", True),
                ])

                _logger.info("Total produits médicaments trouvés en base: %s", len(products))

                matched_product = False
                best_score = 0

                for p in products:
                    candidates = [
                        p.name or "",
                        p.nom_generique or "",
                        p.nom_commercial or "",
                    ]

                    for candidate in candidates:
                        normalized_candidate = rec._normalize_text(candidate)

                        if not normalized_candidate:
                            continue

                        if normalized_search == normalized_candidate:
                            matched_product = p
                            best_score = 100
                            _logger.info("MATCH EXACT sur %s", candidate)
                            break

                        if normalized_search in normalized_candidate:
                            score = 80
                            if score > best_score:
                                matched_product = p
                                best_score = score
                                _logger.info("MATCH PARTIEL sur %s", candidate)

                        elif normalized_candidate in normalized_search:
                            score = 70
                            if score > best_score:
                                matched_product = p
                                best_score = score
                                _logger.info("MATCH INVERSE sur %s", candidate)

                    if best_score == 100:
                        break

                if not matched_product:
                    _logger.warning("Aucun match pour: %s", search_name)
                    line.product_id = False
                    line.needs_review = True
                    continue

                product = matched_product.product_variant_id
                line.product_id = product.id if product else False
                line.needs_review = not bool(product)

                _logger.info(
                    "Produit associé final: %s | variant_id: %s",
                    matched_product.display_name,
                    product.id if product else False,
                )
    def _get_active_client_lines(self):
        self.ensure_one()
        return self.line_ids.filtered(lambda l: not l.is_deleted_by_client and l.is_confirmed_by_client)
    def action_evaluate_mobile_lines(self):
        self.ensure_one()

        self._match_products()
        self._compute_stock()

        results = []
        for line in self._get_active_client_lines():
            result = self._evaluate_confirmed_medication(line)

            line.evaluation_state = result.get("state")
            line.evaluation_message = result.get("message")

            alt = result.get("alternative") or {}
            line.alternative_product_id = alt.get("id") if alt else False

            results.append({
                "line_id": line.id,
                "name": line.corrected_name or line.extracted_name,
                **result,
            })

        return results
    def export_mobile_payload(self):
        self.ensure_one()
        visible_lines = self.line_ids.filtered(lambda l: not l.is_deleted_by_client)

        return {
            "prescription_id": self.id,
            "status": self.state,
            "patient_name": self.patient_name,
            "doctor_name": self.doctor_name,
            "prescription_date": self.prescription_date,
            "medications": [
                {
                    "line_id": l.id,
                    "raw_label": l.raw_label,
                    "name": l.corrected_name or l.extracted_name,
                    "extracted_name": l.extracted_name,
                    "corrected_name": l.corrected_name,
                    "dosage": l.dosage,
                    "form": l.form,
                    "quantity": l.quantity_text,
                    "duration": l.duration_text,
                    "confidence": l.confidence,
                    "product_id": l.product_id.id if l.product_id else None,
                    "product_name": l.product_id.display_name if l.product_id else None,
                    "qty_available": l.qty_available,
                    "is_available": l.is_available,
                    "needs_review": l.needs_review,
                    "is_confirmed_by_client": l.is_confirmed_by_client,
                    "is_deleted_by_client": l.is_deleted_by_client,
                    "evaluation_state": l.evaluation_state,
                    "evaluation_message": l.evaluation_message,
                    "alternative_product_id": l.alternative_product_id.id if l.alternative_product_id else None,
                    "alternative_product_name": l.alternative_product_id.display_name if l.alternative_product_id else None,
                }
                for l in visible_lines
            ]
        }

    def _get_active_client_lines(self):
        self.ensure_one()
        return self.line_ids.filtered(lambda l: not l.is_deleted_by_client and l.is_confirmed_by_client)

    def action_evaluate_mobile_lines(self):
        self.ensure_one()

        self._match_products()
        self._compute_stock()

        results = []
        for line in self._get_active_client_lines():
            result = self._evaluate_confirmed_medication(line)

            line.evaluation_state = result.get("state")
            line.evaluation_message = result.get("message")

            alt = result.get("alternative") or {}
            line.alternative_product_id = alt.get("id") if alt else False

            results.append({
                "line_id": line.id,
                "requested_name": line.corrected_name or line.extracted_name,
                **result,
            })

        return results
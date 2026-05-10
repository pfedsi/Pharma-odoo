import base64
import re
from odoo import http
from odoo.http import request


class PrescriptionApiController(http.Controller):

    @staticmethod
    def _clean_base64(raw: str) -> str:
        raw = str(raw or "")
        raw = re.sub(r"^data:[^;]+;base64,", "", raw)
        raw = "".join(raw.split())
        raw = raw.rstrip("=")
        remainder = len(raw) % 4
        if remainder == 1:
            raw = raw[:-1]
        if len(raw) % 4 != 0:
            raw += "=" * (4 - len(raw) % 4)
        return raw

    @http.route(
        "/api/prescription/upload",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def upload_prescription(self, **payload):
        filename = payload.get("filename") or "prescription.jpg"
        file_base64 = payload.get("file_base64")
        mimetype = payload.get("mimetype") or "image/jpeg"

        if not file_base64:
            return {"success": False, "message": "Fichier manquant"}

        try:
            cleaned = self._clean_base64(file_base64)
            base64.b64decode(cleaned, validate=True)
            file_base64 = cleaned
        except Exception as e:
            return {"success": False, "message": f"Base64 invalide: {e}"}

        try:
            attachment = request.env["ir.attachment"].sudo().create({
                "name": filename,
                "type": "binary",
                "datas": file_base64,
                "mimetype": mimetype,
            })
        except Exception as e:
            return {"success": False, "message": f"Erreur création attachment: {e}"}

        try:
            prescription = request.env["pharmacy.prescription"].sudo().create_from_attachment(
                attachment=attachment,
                source_type=payload.get("source_type") or "virtual",
                ticket_id=payload.get("ticket_id"),
                partner_id=payload.get("partner_id"),
            )
        except Exception as e:
            import traceback
            return {
                "success": False,
                "message": f"Erreur scan: {str(e)}",
                "traceback": traceback.format_exc(),
            }

        return {
            "success": True,
            "data": prescription.export_mobile_payload(),
        }

    @http.route(
        "/api/prescription/<int:prescription_id>/details",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def prescription_details(self, prescription_id, **payload):
        prescription = request.env["pharmacy.prescription"].sudo().browse(prescription_id)
        if not prescription.exists():
            return {"success": False, "message": "Ordonnance introuvable"}
        return {"success": True, "data": prescription.export_mobile_payload()}

    @http.route(
        "/api/prescription/line/<int:line_id>/delete",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def delete_line(self, line_id, **payload):
        line = request.env["pharmacy.prescription.line"].sudo().browse(line_id)
        if not line.exists():
            return {"success": False, "message": "Ligne introuvable"}
        line.write({"is_deleted_by_client": True, "is_confirmed_by_client": False})
        return {"success": True}

    @http.route(
        "/api/prescription/line/<int:line_id>/update",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def update_line(self, line_id, **payload):
        line = request.env["pharmacy.prescription.line"].sudo().browse(line_id)
        if not line.exists():
            return {"success": False, "message": "Ligne introuvable"}
        line.write({
            "corrected_name": payload.get("drug_name") or line.corrected_name or line.extracted_name,
            "dosage": payload.get("dosage", line.dosage),
            "form": payload.get("form", line.form),
            "quantity_text": payload.get("quantity", line.quantity_text),
            "is_edited_by_client": True,
            "is_confirmed_by_client": True,
            "is_deleted_by_client": False,
        })
        return {"success": True}

    @http.route(
        "/api/prescription/<int:prescription_id>/add_line",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def add_line(self, prescription_id, **payload):
        prescription = request.env["pharmacy.prescription"].sudo().browse(prescription_id)
        if not prescription.exists():
            return {"success": False, "message": "Ordonnance introuvable"}
        line = request.env["pharmacy.prescription.line"].sudo().create({
            "prescription_id": prescription.id,
            "raw_label": "",
            "extracted_name": payload.get("drug_name", ""),
            "corrected_name": payload.get("drug_name", ""),
            "dosage": payload.get("dosage", ""),
            "form": payload.get("form", ""),
            "quantity_text": payload.get("quantity", ""),
            "duration_text": payload.get("duration", ""),
            "confidence": 1.0,
            "is_added_by_client": True,
            "is_confirmed_by_client": True,
            "needs_review": False,
        })
        return {"success": True, "line_id": line.id}

    @http.route(
        "/api/prescription/<int:prescription_id>/check_availability",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def check_availability(self, prescription_id, **payload):
        prescription = request.env["pharmacy.prescription"].sudo().browse(prescription_id)
        if not prescription.exists():
            return {"success": False, "message": "Ordonnance introuvable"}
        results = prescription.action_evaluate_mobile_lines()
        return {
            "success": True,
            "results": results,
            "data": prescription.export_mobile_payload(),
        }

    @http.route(
        "/api/prescription/line/<int:line_id>/choose_alternative",
        type="json",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def choose_alternative(self, line_id, **payload):
        line = request.env["pharmacy.prescription.line"].sudo().browse(line_id)
        if not line.exists():
            return {"success": False, "message": "Ligne introuvable"}
        line.write({"alternative_accepted": bool(payload.get("accept_alternative"))})
        return {"success": True}

    @http.route(
        "/pos/prescription/upload_for_order",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def upload_prescription_for_order(self, **payload):
        order_id = payload.get("order_id")
        filename = payload.get("filename") or "ordonnance.jpg"
        file_base64 = payload.get("file_base64")
        mimetype = payload.get("mimetype") or "image/jpeg"

        if not order_id:
            return {"success": False, "message": "Commande POS manquante."}
        if not file_base64:
            return {"success": False, "message": "Fichier manquant."}

        order = request.env["pos.order"].sudo().browse(int(order_id))
        if not order.exists():
            return {"success": False, "message": "Commande POS introuvable."}

        try:
            cleaned = self._clean_base64(file_base64)
            base64.b64decode(cleaned, validate=True)
            file_base64 = cleaned
        except Exception as e:
            return {"success": False, "message": f"Base64 invalide: {e}"}

        attachment = request.env["ir.attachment"].sudo().create({
            "name": filename,
            "type": "binary",
            "datas": file_base64,
            "mimetype": mimetype,
        })
        prescription = request.env["pharmacy.prescription"].sudo().create_from_attachment(
            attachment=attachment,
            source_type="kiosk",
            partner_id=order.partner_id.id if order.partner_id else False,
            pos_order_id=order.id,
        )
        return {
            "success": True,
            "data": prescription.export_mobile_payload(),
            "prescription_id": prescription.id,
        }

    @http.route(
        "/pos/prescription/scan",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def scan_prescription_pos(self, **payload):
        filename = payload.get("filename") or "ordonnance.jpg"
        file_base64 = payload.get("file_base64")
        mimetype = payload.get("mimetype") or "image/jpeg"
        ticket_id = payload.get("ticket_id")

        if not file_base64:
            return {"success": False, "message": "Fichier manquant."}

        try:
            cleaned = self._clean_base64(file_base64)
            base64.b64decode(cleaned, validate=True)
            file_base64 = cleaned
        except Exception as e:
            return {"success": False, "message": f"Base64 invalide: {e}"}

        attachment = request.env["ir.attachment"].sudo().create({
            "name": filename,
            "type": "binary",
            "datas": file_base64,
            "mimetype": mimetype,
        })
        prescription = request.env["pharmacy.prescription"].sudo().create_from_attachment(
            attachment=attachment,
            source_type="kiosk",
            ticket_id=ticket_id or False,
            partner_id=False,
            pos_order_id=False,
        )
        return {
            "success": True,
            "prescription_id": prescription.id,
            "data": prescription.export_mobile_payload(),
        }

    @http.route(
        "/pos/prescription/get_product_for_pos",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def get_product_for_pos(self, **payload):
        product_id = payload.get("product_id")
        if not product_id:
            return {"success": False, "message": "Produit manquant."}
        product = request.env["product.product"].sudo().browse(int(product_id))
        if not product.exists():
            return {"success": False, "message": "Produit introuvable."}
        return {
            "success": True,
            "data": {
                "id": product.id,
                "display_name": product.display_name,
                "lst_price": product.lst_price,
            },
        }
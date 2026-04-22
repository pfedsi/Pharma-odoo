from odoo import http
from odoo.http import request


class PrescriptionMobileController(http.Controller):

    @http.route('/api/prescription/<int:prescription_id>/mobile/details', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def mobile_prescription_details(self, prescription_id, **payload):
        prescription = request.env["pharmacy.prescription"].sudo().browse(prescription_id)
        if not prescription.exists():
            return {"success": False, "message": "Ordonnance introuvable."}

        return {
            "success": True,
            "data": prescription.export_mobile_payload()
        }

    @http.route('/api/prescription/line/<int:line_id>/mobile/delete', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def mobile_delete_line(self, line_id, **payload):
        line = request.env["pharmacy.prescription.line"].sudo().browse(line_id)
        if not line.exists():
            return {"success": False, "message": "Ligne introuvable."}

        line.write({
            "is_deleted_by_client": True,
            "is_confirmed_by_client": False,
        })

        return {"success": True}

    @http.route('/api/prescription/line/<int:line_id>/mobile/update', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def mobile_update_line(self, line_id, **payload):
        line = request.env["pharmacy.prescription.line"].sudo().browse(line_id)
        if not line.exists():
            return {"success": False, "message": "Ligne introuvable."}

        vals = {
            "corrected_name": payload.get("drug_name") or line.corrected_name or line.extracted_name,
            "dosage": payload.get("dosage", line.dosage),
            "form": payload.get("form", line.form),
            "quantity_text": payload.get("quantity", line.quantity_text),
            "is_edited_by_client": True,
            "is_confirmed_by_client": True,
            "is_deleted_by_client": False,
        }
        line.write(vals)

        return {"success": True}

    @http.route('/api/prescription/<int:prescription_id>/mobile/add_line', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def mobile_add_line(self, prescription_id, **payload):
        prescription = request.env["pharmacy.prescription"].sudo().browse(prescription_id)
        if not prescription.exists():
            return {"success": False, "message": "Ordonnance introuvable."}

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

    @http.route('/api/prescription/<int:prescription_id>/mobile/confirm', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def mobile_confirm_prescription(self, prescription_id, **payload):
        prescription = request.env["pharmacy.prescription"].sudo().browse(prescription_id)
        if not prescription.exists():
            return {"success": False, "message": "Ordonnance introuvable."}

        results = prescription.sudo().action_evaluate_mobile_lines()

        return {
            "success": True,
            "results": results,
            "data": prescription.export_mobile_payload()
        }

    @http.route('/api/prescription/line/<int:line_id>/mobile/alternative', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def mobile_choose_alternative(self, line_id, **payload):
        line = request.env["pharmacy.prescription.line"].sudo().browse(line_id)
        if not line.exists():
            return {"success": False, "message": "Ligne introuvable."}

        accept = bool(payload.get("accept_alternative"))

        line.write({
            "alternative_accepted": accept
        })

        return {"success": True}
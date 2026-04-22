from odoo import models, fields

class PharmacyPrescriptionLine(models.Model):
    _name = "pharmacy.prescription.line"
    _description = "Prescription Line"

    prescription_id = fields.Many2one("pharmacy.prescription", required=True, ondelete="cascade")

    raw_label = fields.Char()
    extracted_name = fields.Char(required=True)
    corrected_name = fields.Char()

    dosage = fields.Char()
    form = fields.Char()
    quantity_text = fields.Char()
    duration_text = fields.Char()

    confidence = fields.Float(default=0.0)
    needs_review = fields.Boolean(default=True)
    is_corrected = fields.Boolean(default=False)

    product_id = fields.Many2one("product.product")
    qty_available = fields.Float()
    is_available = fields.Boolean()
    is_partial = fields.Boolean()
    is_confirmed_by_client = fields.Boolean(string="Confirmé par le client", default=True)
    evaluation_state = fields.Selection([
        ("not_found", "Non trouvé"),
        ("available_rx_required", "Disponible - ordonnance obligatoire"),
        ("available_no_rx", "Disponible"),
        ("out_of_stock_rx_required", "Hors stock - retour médecin"),
        ("out_of_stock_with_alternative", "Hors stock - alternative"),
        ("out_of_stock_no_alternative", "Hors stock - sans alternative"),
    ], string="Résultat métier")

    evaluation_message = fields.Char(string="Message métier")
    alternative_product_id = fields.Many2one("product.template", string="Alternative proposée")
    is_deleted_by_client = fields.Boolean(default=False)
    is_added_by_client = fields.Boolean(default=False)
    is_edited_by_client = fields.Boolean(default=False)
    alternative_accepted = fields.Boolean(default=False)
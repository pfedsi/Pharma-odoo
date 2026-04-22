# -*- coding: utf-8 -*-
import logging
from odoo import models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class MobileOrderService(models.AbstractModel):
    _name = "pharmacy.mobile.order.service"
    _description = "Service Commande Mobile"

    def _get_session_token(self):
        request = self.env.context.get("request")
        if request:
            return (
                request.httprequest.headers.get("X-Session-Id")
                or request.session.sid
            )
        return self.env.context.get("session_token")

    def _get_public_user(self):
        return self.env.ref("base.public_user")

    def _resolve_partner(self, partner_id=None):
        if partner_id:
            partner = self.env["res.partner"].sudo().browse(partner_id)
            if partner.exists():
                return partner
        return False

    def _build_order_line_vals_from_product(
        self,
        order,
        product,
        qty,
        source_type="manual",
        prescription_id=None,
        prescription_line_id=None,
    ):
        return {
            "order_id": order.id,
            "product_tmpl_id": product.id,
            "name": product.nom_commercial or product.name,
            "quantity": qty,
            "price_unit": product.prix_vente_tnd or product.list_price or 0.0,
            "source_type": source_type,
            "prescription_id": prescription_id or False,
            "prescription_line_id": prescription_line_id or False,
            "requires_prescription": bool(product.necessite_ordonnance),
            "product_type_label": "parapharmacie" if product.parapharmaceutique else "medicament",
        }

    def create_from_unified_cart_and_reservation(
        self,
        reservation,
        unified_cart_lines,
        partner_id=None,
        prescription_id=None,
        notes=None,
    ):
        if not unified_cart_lines:
            raise ValidationError(_("Le panier est vide."))

        partner = self._resolve_partner(partner_id)
        public_user = self._get_public_user()
        session_token = self._get_session_token()

        order = self.env["pharmacy.mobile.order"].sudo().create({
            "partner_id": partner.id if partner else False,
            "user_id": public_user.id,
            "session_token": session_token,
            "reservation_id": reservation.id,
            "prescription_id": prescription_id or False,
            "notes": notes or "",
            "state": "reserved",
        })

        ProductTemplate = self.env["product.template"].sudo()

        for line in unified_cart_lines:
            product_id = int(line.get("product_id") or 0)
            qty = float(line.get("quantite") or 0)
            source_type = line.get("source_type") or "manual"
            src_prescription_id = line.get("prescription_id")
            src_prescription_line_id = line.get("prescription_line_id")

            if not product_id or qty <= 0:
                continue

            product = ProductTemplate.browse(product_id)
            if not product.exists():
                continue

            vals = self._build_order_line_vals_from_product(
                order=order,
                product=product,
                qty=qty,
                source_type=source_type,
                prescription_id=src_prescription_id,
                prescription_line_id=src_prescription_line_id,
            )
            self.env["pharmacy.mobile.order.line"].sudo().create(vals)

        if not order.line_ids:
            raise ValidationError(_("Aucune ligne valide n'a été trouvée dans le panier."))

        return order

    def attach_ticket(self, mobile_order, ticket):
        mobile_order.sudo().write({
            "ticket_id": ticket.id,
            "state": "arrived",
        })

        if "mobile_order_id" in ticket._fields:
            ticket.sudo().write({"mobile_order_id": mobile_order.id})

        if mobile_order.prescription_id:
            vals = {"ticket_id": ticket.id}
            if "reservation_id" in mobile_order.prescription_id._fields and mobile_order.reservation_id:
                vals["reservation_id"] = mobile_order.reservation_id.id
            if "mobile_order_id" in mobile_order.prescription_id._fields:
                vals["mobile_order_id"] = mobile_order.id
            mobile_order.prescription_id.sudo().write(vals)

        return mobile_order

    def confirm_to_pos_order(self, mobile_order):
        if mobile_order.pos_order_id:
            return mobile_order.pos_order_id

        if not mobile_order.line_ids:
            raise ValidationError(_("Impossible de confirmer une commande vide."))

        pos_config = self.env["pos.config"].sudo().search([], limit=1)
        if not pos_config:
            raise UserError(_("Aucune configuration POS disponible."))

        session = self.env["pos.session"].sudo().search([
            ("config_id", "=", pos_config.id),
            ("state", "=", "opened"),
        ], limit=1)

        if not session:
            raise UserError(_("Aucune session POS ouverte n'est disponible."))

        line_commands = []
        for line in mobile_order.line_ids:
            product_variant = line.product_tmpl_id.product_variant_id
            if not product_variant:
                continue

            line_commands.append((0, 0, {
                "product_id": product_variant.id,
                "qty": line.quantity,
                "price_unit": line.price_unit,
                "name": line.name,
            }))

        order_vals = {
            "session_id": session.id,
            "partner_id": mobile_order.partner_id.id or False,
            "reservation_id": mobile_order.reservation_id.id or False,
            "ticket_id": mobile_order.ticket_id.id or False,
            "mobile_order_id": mobile_order.id,
            "note": mobile_order.notes or "",
            "lines": line_commands,
        }

        pos_order = self.env["pos.order"].sudo().create(order_vals)

        mobile_order.sudo().write({
            "pos_order_id": pos_order.id,
            "state": "confirmed",
        })

        if mobile_order.prescription_id:
            vals = {
                "pos_order_id": pos_order.id,
                "ticket_id": mobile_order.ticket_id.id if mobile_order.ticket_id else False,
            }
            if "mobile_order_id" in mobile_order.prescription_id._fields:
                vals["mobile_order_id"] = mobile_order.id
            mobile_order.prescription_id.sudo().write(vals)

        return pos_order

    def export_order_payload(self, order):
        return {
            "id": order.id,
            "name": order.name,
            "state": order.state,
            "reservation_id": order.reservation_id.id if order.reservation_id else None,
            "ticket_id": order.ticket_id.id if order.ticket_id else None,
            "pos_order_id": order.pos_order_id.id if order.pos_order_id else None,
            "amount_total": order.amount_total,
            "item_count": order.item_count,
            "service": order.service_id.nom if order.service_id else None,
            "lines": [
                {
                    "id": l.id,
                    "product_id": l.product_tmpl_id.id,
                    "name": l.name,
                    "quantity": l.quantity,
                    "price_unit": l.price_unit,
                    "subtotal": l.subtotal,
                    "source_type": l.source_type,
                    "prescription_id": l.prescription_id.id if l.prescription_id else None,
                    "prescription_line_id": l.prescription_line_id.id if l.prescription_line_id else None,
                    "requires_prescription": l.requires_prescription,
                    "product_type_label": l.product_type_label,
                }
                for l in order.line_ids
            ],
        }
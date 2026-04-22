# -*- coding: utf-8 -*-
import logging
from odoo import http
from odoo.http import request
from ..services.reservation_service import ReservationService

_logger = logging.getLogger(__name__)


class MobileOrderController(http.Controller):

    def _svc(self):
        return request.env["pharmacy.mobile.order.service"].with_context(request=request)

    def _get_params(self, **kwargs):
        if kwargs:
            return kwargs
        try:
            data = request.get_json_data()
            if isinstance(data, dict):
                return data.get("params", data)
        except Exception:
            pass
        return {}

    @http.route(
        "/api/mobile/order/cancel_reservation",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def cancel_reservation_public_payload(self, **kwargs):
        """
        POST /api/mobile/order/cancel_reservation
        Body : { "reservation_id": int }
        """
        try:
            payload = self._get_params(**kwargs)
            reservation_id = int(payload.get("reservation_id") or 0)
            if not reservation_id:
                return {"success": False, "message": "reservation_id requis."}

            reservation = request.env["pharmacy.reservation"].sudo().browse(reservation_id)
            if not reservation.exists():
                return {"success": False, "message": "Réservation introuvable."}
            if reservation.statut == "annule":
                return {"success": False, "message": "Réservation déjà annulée."}
            if reservation.statut == "arrive":
                return {"success": False, "message": "Impossible d'annuler une réservation arrivée."}

            reservation.sudo().write({"statut": "annule"})
            _logger.info("Reservation %s annulée via flux public.", reservation_id)
            return {
                "success": True,
                "message": "Réservation annulée avec succès.",
                "reservation_id": reservation_id,
            }

        except Exception as e:
            _logger.exception("CANCEL RESERVATION PUBLIC ERROR")
            return {"success": False, "message": str(e)}

    @http.route(
        "/api/mobile/reservation/<int:reservation_id>/cancel",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def cancel_reservation_public(self, reservation_id, **kwargs):
        """
        POST /api/mobile/reservation/<id>/cancel
        """
        try:
            reservation = request.env["pharmacy.reservation"].sudo().browse(reservation_id)
            if not reservation.exists():
                return {"success": False, "message": "Réservation introuvable."}
            if reservation.statut == "annule":
                return {"success": False, "message": "Réservation déjà annulée."}
            if reservation.statut == "arrive":
                return {"success": False, "message": "Impossible d'annuler une réservation arrivée."}

            reservation.sudo().write({"statut": "annule"})
            _logger.info("Reservation %s annulée via route directe.", reservation_id)
            return {
                "success": True,
                "message": "Réservation annulée avec succès.",
                "reservation_id": reservation_id,
            }

        except Exception as e:
            _logger.exception("CANCEL RESERVATION DIRECT ERROR")
            return {"success": False, "message": str(e)}

    @http.route(
        "/api/mobile/order/start",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def start_mobile_order(self, **kwargs):
        try:
            payload = self._get_params(**kwargs)
            _logger.info("start_mobile_order payload = %s", payload)

            service_id = int(payload.get("service_id") or 0)
            date_heure_reservation = payload.get("date_heure_reservation")
            partner_id = payload.get("partner_id")
            prescription_id = payload.get("prescription_id")
            notes = payload.get("notes") or ""
            unified_cart_lines = payload.get("cart_lines") or []

            if not service_id:
                return {"success": False, "message": "service_id est requis."}
            if not date_heure_reservation:
                return {"success": False, "message": "date_heure_reservation est requis."}

            public_user = request.env.ref("base.public_user")
            svc = ReservationService(request.env)
            reservation_data = svc.create(
                user_id=public_user.id,
                service_id=service_id,
                date_heure=date_heure_reservation,
                notes=notes,
            )
            reservation = request.env["pharmacy.reservation"].sudo().browse(
                reservation_data["id"]
            )

            mobile_order_payload = None
            valid_lines = [
                l for l in unified_cart_lines
                if l.get("product_id") and float(l.get("quantite") or 0) > 0
            ]

            if valid_lines:
                order = self._svc().create_from_unified_cart_and_reservation(
                    reservation=reservation,
                    unified_cart_lines=valid_lines,
                    partner_id=partner_id,
                    prescription_id=prescription_id,
                    notes=notes,
                )
                mobile_order_payload = self._svc().export_order_payload(order)

            return {
                "success": True,
                "reservation": reservation_data,
                "mobile_order": mobile_order_payload,
                "next_step": "je_suis_la",
            }

        except Exception as e:
            _logger.exception("MOBILE ORDER START ERROR")
            return {"success": False, "message": str(e)}

    @http.route(
        "/api/mobile/order/<int:order_id>",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def get_mobile_order(self, order_id, **kwargs):
        try:
            order = request.env["pharmacy.mobile.order"].sudo().browse(order_id)
            if not order.exists():
                return {"success": False, "message": "Commande introuvable."}
            return {
                "success": True,
                "mobile_order": self._svc().export_order_payload(order),
            }
        except Exception as e:
            _logger.exception("GET MOBILE ORDER ERROR")
            return {"success": False, "message": str(e)}

    @http.route(
        "/api/mobile/order/<int:order_id>/attach_ticket",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def attach_ticket(self, order_id, **kwargs):
        try:
            payload = self._get_params(**kwargs)
            ticket_id = int(payload.get("ticket_id") or 0)
            if not ticket_id:
                return {"success": False, "message": "ticket_id est requis."}

            order = request.env["pharmacy.mobile.order"].sudo().browse(order_id)
            if not order.exists():
                return {"success": False, "message": "Commande introuvable."}

            ticket = request.env["pharmacy.ticket"].sudo().browse(ticket_id)
            if not ticket.exists():
                return {"success": False, "message": "Ticket introuvable."}

            self._svc().attach_ticket(order, ticket)
            return {
                "success": True,
                "mobile_order": self._svc().export_order_payload(order),
            }
        except Exception as e:
            _logger.exception("ATTACH TICKET ERROR")
            return {"success": False, "message": str(e)}

    @http.route(
        "/api/mobile/order/<int:order_id>/confirm",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def confirm_mobile_order(self, order_id, **kwargs):
        try:
            order = request.env["pharmacy.mobile.order"].sudo().browse(order_id)
            if not order.exists():
                return {"success": False, "message": "Commande introuvable."}

            pos_order = self._svc().confirm_to_pos_order(order)
            return {
                "success": True,
                "mobile_order": self._svc().export_order_payload(order),
                "pos_order": {"id": pos_order.id, "name": pos_order.name},
            }
        except Exception as e:
            _logger.exception("CONFIRM MOBILE ORDER ERROR")
            return {"success": False, "message": str(e)}

    @http.route(
        "/api/mobile/order/<int:order_id>/cancel",
        type="jsonrpc",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def cancel_mobile_order(self, order_id, **kwargs):
        try:
            order = request.env["pharmacy.mobile.order"].sudo().browse(order_id)
            if not order.exists():
                return {"success": False, "message": "Commande introuvable."}

            if order.state in ("confirmed", "cancelled"):
                return {
                    "success": False,
                    "message": f"Impossible d'annuler une commande en statut «{order.state}».",
                }

            if order.reservation_id and order.reservation_id.statut == "en_attente":
                order.reservation_id.sudo().write({"statut": "annule"})
                _logger.info(
                    "Reservation %s annulée via cancel commande.",
                    order.reservation_id.id,
                )

            order.sudo().write({"state": "cancelled"})
            _logger.info("MobileOrder %s annulée.", order_id)

            return {
                "success": True,
                "message": "Commande et réservation annulées avec succès.",
            }

        except Exception as e:
            _logger.exception("CANCEL MOBILE ORDER ERROR")
            return {"success": False, "message": str(e)}
from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class TicketDisplayController(http.Controller):

    @http.route("/pharmacy/ticket/display", type="http", auth="public", csrf=False)
    def ticket_display_page(self, **kwargs):
        config = request.env["ir.config_parameter"].sudo()
        enabled = config.get_param("service_pharmacie.ticket_public_enabled", "False")

        _logger.info(
            "DISPLAY | enabled=%s | session_ok=%s",
            enabled,
            request.session.get("ticket_display_ok")
        )

        if enabled != "True":
            return request.not_found()

        if not request.session.get("ticket_display_ok"):
            return request.redirect("/pharmacy/ticket/access")

        return request.render("service_pharmacie.ticket_display_page")

    @http.route("/pharmacy/ticket/access", type="http", auth="public", csrf=False)
    def ticket_access_page(self, **kwargs):
        return request.render("service_pharmacie.ticket_access_page")

    @http.route("/pharmacy/ticket/access/check", type="http", auth="public", methods=["POST"], csrf=False)
    def ticket_access_check(self, **post):
        password_input = (post.get("password") or "").strip()

        config = request.env["ir.config_parameter"].sudo()
        enabled = config.get_param("service_pharmacie.ticket_public_enabled", "False")
        password = config.get_param("service_pharmacie.ticket_public_password", "")

        _logger.info(
            "ACCESS CHECK | enabled=%s | input=%s | configured=%s",
            enabled,
            bool(password_input),
            bool(password)
        )

        if enabled != "True":
            return request.not_found()

        if not password:
            return request.redirect("/pharmacy/ticket/access?error=config")

        if password_input == password:
            request.session["ticket_display_ok"] = True
            _logger.info("ACCESS OK | redirecting to /pharmacy/ticket/display")
            return request.redirect("/pharmacy/ticket/display")

        return request.redirect("/pharmacy/ticket/access?error=1")

    @http.route("/pharmacy/ticket/logout", type="http", auth="public", csrf=False)
    def ticket_logout(self, **kwargs):
        request.session.pop("ticket_display_ok", None)
        return request.redirect("/pharmacy/ticket/access")
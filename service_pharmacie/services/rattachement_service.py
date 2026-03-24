# -*- coding: utf-8 -*-
"""SERVICE — RattachementService"""
from odoo.exceptions import UserError


class RattachementService:

    def __init__(self, env):
        self.env = env

    def list_active(self) -> list:
        rattachements = self.env["pharmacy.rattachement"].sudo().search(
            [("active", "=", True)]
        )
        return [self._to_dict(r) for r in rattachements]

    def appeler_prochain(self, rattachement_id: int) -> dict:
        ratt = self.env["pharmacy.rattachement"].sudo().browse(rattachement_id)
        if not ratt.exists():
            raise UserError(f"Rattachement {rattachement_id} introuvable.")
        ticket = ratt.get_prochain_ticket()
        if not ticket:
            raise UserError("Aucun ticket en attente dans cette file.")
        ticket.action_appeler()
        return {
            "success": True,
            "ticket": {
                "id": ticket.id,
                "numero": ticket.name,
                "service": ticket.service_id.nom if ticket.service_id else None,
            },
        }

    def _to_dict(self, r) -> dict:
        return {
            "id": r.id,
            "assistant": r.assistant_id.name if r.assistant_id else None,
            "file": r.file_id.display_name if r.file_id else None,
            "file_id": r.file_id.id if r.file_id else None,
            "mode": r.mode_rattachement,
            "service_prioritaire": (
                r.service_prioritaire_id.nom if r.service_prioritaire_id else None
            ),
            "active": r.active,
        }
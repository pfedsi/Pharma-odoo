# -*- coding: utf-8 -*-
"""SERVICE — QueueService"""
from odoo.exceptions import UserError


class QueueService:

    def __init__(self, env):
        self.env = env

    # ── API publique ──────────────────────────────────────────────────────────

    def list_active(self, type_affichage: str | None = None) -> list:
        """
        Retourne uniquement les files actives.
        Si un service est lié, il doit aussi être actif.
        Les queues sans service sont incluses si elles sont actives.
        Si type_affichage est 'physique' ou 'virtuel', filtre par type du service lié.
        """
        queues = self.env["pharmacy.queue"].sudo().search([
            ("active", "=", True),
        ])

        queues = queues.filtered(
            lambda q: not q.service_id or q.service_id.active
        )

        if type_affichage in ("physique", "virtuel"):
            queues = queues.filtered(
                lambda q: not q.service_id
                or q.service_id.type_affichage in (type_affichage, "les_deux")
            )

        return [self._to_dict(q) for q in queues]

    def get_by_id(self, queue_id: int) -> dict:
        queue = self.env["pharmacy.queue"].sudo().browse(queue_id)

        if not queue.exists() or not queue.active:
            raise UserError(f"File d'attente {queue_id} introuvable.")

        if queue.service_id and not queue.service_id.active:
            raise UserError(f"File d'attente {queue_id} introuvable.")

        return self._to_dict(queue)

    # ── Helper ────────────────────────────────────────────────────────────────

    def _to_dict(self, q) -> dict:
        service = q.service_id

        return {
            "id": q.id,
            "name": q.name,
            "display_name": q.display_name,
            "active": q.active,
            "service_id": service.id if service else None,
            "service": service.nom if service else None,
            "nb_en_attente": int(q.nb_en_attente or 0),
            "temps_attente_estime": int(q.temps_attente_estime or 0),
            "position_client_virtuel": q.position_client_virtuel,
        }
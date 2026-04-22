# -*- coding: utf-8 -*-
"""SERVICE — TicketService"""
from odoo.exceptions import UserError


class TicketService:

    def __init__(self, env):
        self.env = env

    def get_by_id(self, ticket_id: int) -> dict:
        ticket = self.env["pharmacy.ticket"].sudo().browse(ticket_id)
        if not ticket.exists():
            raise UserError(f"Ticket {ticket_id} introuvable.")
        return self._to_dict(ticket)

    def list_mine(self, uid: int, statut: str = None) -> list:
        domain = [("user_id", "=", uid)]
        if statut:
            domain.append(("etat", "=", statut))

        tickets = (
            self.env["pharmacy.ticket"]
            .sudo()
            .search(domain, order="heure_creation desc")
        )
        return [self._to_dict(t) for t in tickets]

    def create_ticket(
        self,
        queue_id: int,
        uid: int,
        type_ticket: str = "physique",
        reservation_id: int = None,
    ) -> dict:
        queue = self.env["pharmacy.queue"].sudo().browse(queue_id)
        if not queue.exists() or not queue.active:
            raise UserError(f"File d'attente {queue_id} introuvable ou inactive.")

        user = self.env["res.users"].sudo().browse(uid)
        if not user.exists():
            raise UserError(f"Utilisateur {uid} introuvable.")

        reservation = None

        if type_ticket == "virtuel":
            if not reservation_id:
                raise UserError("reservation_id est requis pour un ticket virtuel.")

            reservation = self.env["pharmacy.reservation"].sudo().browse(reservation_id)
            if not reservation.exists():
                raise UserError(f"Réservation {reservation_id} introuvable.")

            if reservation.statut == "annule":
                raise UserError("Impossible de créer un ticket pour une réservation annulée.")

            if reservation.ticket_id:
                raise UserError("Cette réservation a déjà un ticket.")

            if not reservation.queue_id or reservation.queue_id.id != queue.id:
                raise UserError("La réservation n'appartient pas à cette file d'attente.")

            # Optionnel mais recommandé si le ticket est créé pour le client de la réservation
            uid = reservation.user_id.id

        else:
            if reservation_id:
                raise UserError("Un ticket physique ne doit pas être lié à une réservation.")

        ticket_vals = {
            "queue_id": queue.id,
            "user_id": uid,
            "type_ticket": type_ticket,
            "reservation_id": reservation.id if reservation else False,
        }

        ticket = self.env["pharmacy.ticket"].sudo().create(ticket_vals)

        if reservation:
            reservation.sudo().write({
                "ticket_id": ticket.id,
                "statut": "arrive",
            })

        return self._to_dict(ticket)

    def _to_dict(self, t) -> dict:
        return {
            "id":                   t.id,
            "numero":               t.name,
            "etat":                 t.etat,
            "position":             t.position,
            "type_ticket":          t.type_ticket,
            "service":              t.service_id.nom if t.service_id else None,
            "queue_id":             t.queue_id.id if t.queue_id else None,
            "temps_attente_estime": t.queue_id.temps_attente_estime if t.queue_id else 0,
            "heure_creation":       t.heure_creation.isoformat() if t.heure_creation else None,
            "heure_appel":          t.heure_appel.isoformat() if t.heure_appel else None,
            "heure_fin":            t.heure_fin.isoformat() if t.heure_fin else None,
            "reservation_id":       t.reservation_id.id if t.reservation_id else None,
        }
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

    # ── Liste des tickets du client connecté ──────────────────────────────────

    def list_mine(self, uid: int, statut: str = None) -> list:
        """
        Retourne tous les tickets de l'utilisateur connecté.
        Filtre optionnel : statut = 'en_attente' | 'appele' | 'termine' | 'annule'
        """
        domain = [("user_id", "=", uid)]
        if statut:
            domain.append(("etat", "=", statut))

        tickets = (
            self.env["pharmacy.ticket"]
            .sudo()
            .search(domain, order="heure_creation desc")
        )
        return [self._to_dict(t) for t in tickets]

    # ── Créer un ticket physique (comptoir) ───────────────────────────────────

    def create_ticket(self, queue_id: int, uid: int, type_ticket: str = "physique") -> dict:
        """
        Crée un ticket pour un client dans une file d'attente.
        Utilisé pour les tickets physiques créés au comptoir.
        """
        queue = self.env["pharmacy.queue"].sudo().browse(queue_id)
        if not queue.exists() or not queue.active:
            raise UserError(f"File d'attente {queue_id} introuvable ou inactive.")

        user = self.env["res.users"].sudo().browse(uid)
        if not user.exists():
            raise UserError(f"Utilisateur {uid} introuvable.")

        ticket = self.env["pharmacy.ticket"].sudo().create({
            "queue_id":    queue.id,
            "user_id":     uid,
            "type_ticket": type_ticket,
        })
        return self._to_dict(ticket)

    # ── Sérialisation ─────────────────────────────────────────────────────────

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
            "heure_appel":          t.heure_appel.isoformat()    if t.heure_appel    else None,
            "heure_fin":            t.heure_fin.isoformat()      if t.heure_fin      else None,
            "reservation_id":       t.reservation_id.id          if t.reservation_id else None,
        }
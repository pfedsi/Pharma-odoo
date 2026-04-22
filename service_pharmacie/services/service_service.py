# -*- coding: utf-8 -*-
"""SERVICE — ServiceService"""

import datetime
from odoo.exceptions import UserError


JOURS = {
    "0": "Lundi",
    "1": "Mardi",
    "2": "Mercredi",
    "3": "Jeudi",
    "4": "Vendredi",
    "5": "Samedi",
    "6": "Dimanche",
}


def _fmt_time(val: float) -> str:
    if val is None:
        return None
    h = int(val)
    m = int(round((val - h) * 60))
    return f"{h:02d}:{m:02d}"


def _is_overnight(opening: float, closing: float) -> bool:
    if opening is None or closing is None:
        return False
    return closing <= opening


class ServiceService:

    def __init__(self, env):
        self.env = env

    # ─────────────────────────────────────────
    # API publique
    # ─────────────────────────────────────────
    def list_active(self, type_affichage: str | None = None):
        domain = [("active", "=", True)]
        if type_affichage in ("physique", "virtuel"):
            domain += [("type_affichage", "in", [type_affichage, "les_deux"])]
        services = self.env["pharmacy.service"].search(domain)
        return [self._to_dict(s) for s in services]

    def get_by_id(self, service_id: int) -> dict:
        service = self.env["pharmacy.service"].sudo().browse(service_id)
        if not service.exists() or not service.active:
            raise UserError(f"Service {service_id} introuvable.")
        if not service.queue_id:
            service._ensure_queue()
        return self._to_dict(service)

    def get_slots(self, service_id: int, date_str: str) -> dict:
        service = self.env["pharmacy.service"].sudo().browse(service_id)
        if not service.exists() or not service.active:
            raise UserError(f"Service {service_id} introuvable.")

        try:
            date = datetime.date.fromisoformat(date_str)
        except ValueError:
            raise UserError("Format de date invalide. Utiliser YYYY-MM-DD.")

        raw_slots = service.compute_slots(date)

        slots = []
        for slot in raw_slots:
            if isinstance(slot, dict):
                slots.append({
                    "heure": slot.get("time"),
                    "datetime": slot.get("datetime"),
                    "disponible": slot.get("available", True),
                })
            elif hasattr(slot, "strftime"):
                slots.append({
                    "heure": slot.strftime("%H:%M"),
                    "datetime": None,
                    "disponible": True,
                })
            else:
                slots.append({
                    "heure": str(slot),
                    "datetime": None,
                    "disponible": True,
                })

        h_ouv, h_fer = service._get_horaire_du_jour(date)

        return {
            "service_id": service.id,
            "nom": service.nom,
            "date": date_str,
            "heure_ouverture": _fmt_time(h_ouv),
            "heure_fermeture": _fmt_time(h_fer),
            "overnight": _is_overnight(h_ouv, h_fer),
            "duree_creneau": service.duree_creneau,
            "slots": slots,
        }

    def get_horaires(self, service_id: int) -> dict:
        service = self.env["pharmacy.service"].sudo().browse(service_id)
        if not service.exists() or not service.active:
            raise UserError(f"Service {service_id} introuvable.")

        return {
            "service_id": service.id,
            "nom": service.nom,
            "horaires_par_defaut": {
                "ouverture": _fmt_time(service.heure_ouverture),
                "fermeture": _fmt_time(service.heure_fermeture),
                "intervalle_minutes": service.duree_creneau,
                "overnight": _is_overnight(service.heure_ouverture, service.heure_fermeture),
            },
            "horaires": [
                self._horaire_to_dict(h)
                for h in service.horaire_ids.sorted("jour_semaine")
            ],
        }

    # ─────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────

    def _horaire_to_dict(self, h) -> dict:
        overnight = (
            _is_overnight(h.heure_ouverture, h.heure_fermeture)
            if h.actif and h.heure_ouverture is not None and h.heure_fermeture is not None
            else False
        )
        return {
            "jour_index": h.jour_semaine,
            "jour": JOURS.get(h.jour_semaine, h.jour_semaine),
            "actif": h.actif,
            "ouverture": _fmt_time(h.heure_ouverture) if h.actif else None,
            "fermeture": _fmt_time(h.heure_fermeture) if h.actif else None,
            "overnight": overnight,
        }

    def _to_dict(self, s) -> dict:
        q = s.queue_id
        overnight = _is_overnight(s.heure_ouverture, s.heure_fermeture)

        return {
            "id": s.id,
            "nom": s.nom,
            "description": s.description or "",

            "duree_estimee": s.dure_estimee_par_defaut or 0,

            # File d'attente
            "queue_id": q.id if q and q.active else None,
            "queue_nom": q.display_name if q and q.active else None,
            "en_attente": int(getattr(q, "nb_en_attente", 0) or 0) if q and q.active else 0,
            "temps_attente_estime": int(getattr(q, "temps_attente_estime", 0) or 0) if q and q.active else 0,

            # Horaires
            "heure_ouverture": _fmt_time(s.heure_ouverture),
            "heure_fermeture": _fmt_time(s.heure_fermeture),
            "overnight": overnight,
            "duree_creneau": s.duree_creneau or 0,
            "multiplicateur_creneau": int(s.multiplicateur_creneau or 2),
            "warning_creneau": s.warning_creneau,

            # Type d'affichage
            "type_affichage": s.type_affichage or "physique",

            # GPS optionnel
            "pharmacie_adresse": getattr(s, "pharmacie_adresse", "") or "",
            "pharmacie_lat": float(getattr(s, "pharmacie_lat", 0) or 0),
            "pharmacie_lon": float(getattr(s, "pharmacie_lon", 0) or 0),
            "rayon_validation": float(getattr(s, "rayon_validation", 0) or 0),

            # Horaires détaillés
            "horaires": [
                self._horaire_to_dict(h)
                for h in s.horaire_ids.sorted("jour_semaine")
            ],
        }
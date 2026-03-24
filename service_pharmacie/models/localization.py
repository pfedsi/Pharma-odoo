# -*- coding: utf-8 -*-
"""
pharmacy.localization — Localisation unique de la pharmacie
------------------------------------------------------------
• Une seule localisation globale (singleton via _check_singleton)
• Liée directement à pharmacy.reservation (pas via pharmacy.service)
• pharmacy.service garde ses champs related pour rétrocompatibilité API
"""
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class PharmacyLocalization(models.Model):
    _name = "pharmacy.localization"
    _description = "Localisation pharmacie"
    _rec_name = "nom"

    # ── Identification ────────────────────────────────────────────────────────

    nom = fields.Char(
        string="Nom de la pharmacie",
        required=True,
        default="Pharmacie",
        help="Ex : Pharmacie Ibn Sina – Tunis",
    )

    # ── Adresse ───────────────────────────────────────────────────────────────

    pharmacie_adresse = fields.Char(
        string="Adresse complète",
        help="Ex : 12 Rue Ibn Khaldoun, Tunis 1000",
    )

    # ── Coordonnées GPS ───────────────────────────────────────────────────────

    pharmacie_lat = fields.Float(
        string="Latitude",
        digits=(10, 7),
        default=36.8065,
    )
    pharmacie_lon = fields.Float(
        string="Longitude",
        digits=(10, 7),
        default=10.1815,
    )

    # ── Rayon de validation ───────────────────────────────────────────────────

    rayon_validation = fields.Integer(
        string="Rayon GPS (m)",
        default=200,
        help="Distance maximale autorisée pour valider l'arrivée via « Je suis là ».",
    )

    # ── Google Maps (computed) ────────────────────────────────────────────────

    maps_url = fields.Char(
        string="Lien Google Maps",
        compute="_compute_maps_url",
        store=False,
    )

    @api.depends("pharmacie_lat", "pharmacie_lon")
    def _compute_maps_url(self):
        for rec in self:
            rec.maps_url = (
                f"https://www.google.com/maps?q={rec.pharmacie_lat},{rec.pharmacie_lon}"
            )

    # ── Réservations liées ────────────────────────────────────────────────────

    reservation_ids = fields.One2many(
        "pharmacy.reservation",
        "localisation_id",
        string="Réservations",
        readonly=True,
    )

    nb_reservations = fields.Integer(
        string="Nb réservations",
        compute="_compute_nb_reservations",
        store=True,
    )

    @api.depends("reservation_ids")
    def _compute_nb_reservations(self):
        for rec in self:
            rec.nb_reservations = len(rec.reservation_ids)

    # ── Singleton : une seule localisation autorisée ──────────────────────────

    @api.constrains("nom")
    def _check_singleton(self):
        if self.search_count([]) > 1:
            raise ValidationError(
                _("Une seule localisation est autorisée. "
                  "Modifiez la localisation existante au lieu d'en créer une nouvelle.")
            )

    # ── Contraintes ───────────────────────────────────────────────────────────

    @api.constrains("rayon_validation")
    def _check_rayon(self):
        for rec in self:
            if rec.rayon_validation < 10:
                raise ValidationError(
                    _("Le rayon GPS de validation doit être d'au moins 10 mètres.")
                )

    # ── Suppression protégée ──────────────────────────────────────────────────

    def unlink(self):
        for rec in self:
            if rec.reservation_ids:
                raise ValidationError(
                    _(
                        "Impossible de supprimer la localisation « %s » : "
                        "%d réservation(s) y sont rattachées."
                    ) % (rec.nom, len(rec.reservation_ids))
                )
        return super().unlink()

    # ── Helper classe : récupère ou crée la localisation unique ──────────────

    @api.model
    def get_singleton(self):
        """Retourne la localisation unique, ou False si elle n'existe pas encore."""
        loc = self.search([], limit=1)
        return loc or False
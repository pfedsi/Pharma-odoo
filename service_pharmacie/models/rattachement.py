# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class PharmacyRattachement(models.Model):
    _name = "pharmacy.rattachement"
    _description = "Rattachement assistant – file"
    _rec_name = "display_name"
    _inherit = ["mail.thread"]

    display_name = fields.Char(compute="_compute_display_name", store=True)

    assistant_id = fields.Many2one(
        "res.users",
        string="Assistant",
        required=True,
        domain=lambda self: self._domain_assistant_id(),
    )
    current_ticket_id = fields.Many2one(
        "pharmacy.ticket",
        string="Ticket en cours",
        readonly=True,
        ondelete="set null",
        tracking=True,
    )
    last_called_at = fields.Datetime(
        string="Dernier appel",
        readonly=True,
    )
    file_id = fields.Many2one(
        "pharmacy.queue",
        string="File d'attente",
        required=True,
    )
    # ── Mémorise la file propre en mode prioritaire ───────────────────────────
    # Écrit UNE SEULE FOIS dans pos_set_my_rattachement.
    # Jamais écrasé lors des bascules automatiques vers d'autres files.
    file_prioritaire_id = fields.Many2one(
        "pharmacy.queue",
        string="File prioritaire (origine)",
        ondelete="set null",
        help=(
            "File propre assignée en mode prioritaire. "
            "N'est jamais écrasé lors des bascules automatiques."
        ),
    )
    # ─────────────────────────────────────────────────────────────────────────
    mode_rattachement = fields.Selection(
        [
            ("manuel",       "Manuel"),
            ("auto_attente", "Automatique (temps d'attente)"),
            ("prioritaire",  "Prioritaire"),
        ],
        string="Mode",
        required=True,
        default="manuel",
        tracking=True,
    )
    poste_number = fields.Char(
        string="Numéro de poste",
        default="1",
        tracking=True,
    )
    service_prioritaire_id = fields.Many2one(
        "pharmacy.service",
        string="Service prioritaire",
    )
    date_debut = fields.Datetime(default=fields.Datetime.now, required=True)
    date_fin   = fields.Datetime()
    active     = fields.Boolean(default=True)

    # ── Domain helper ─────────────────────────────────────────────────────────

    def _domain_assistant_id(self):
        user_group  = self.env.ref("base.group_user").id
        admin_group = self.env.ref("base.group_system").id
        self.env.cr.execute("""
            SELECT DISTINCT uid
            FROM res_groups_users_rel
            WHERE gid IN %s
        """, [(user_group, admin_group)])
        user_ids = [row[0] for row in self.env.cr.fetchall()]
        return [("id", "in", user_ids)]

    # ── Computed ──────────────────────────────────────────────────────────────

    @api.depends("assistant_id", "file_id", "mode_rattachement")
    def _compute_display_name(self):
        labels = dict(self._fields["mode_rattachement"].selection)
        for rec in self:
            rec.display_name = (
                f"{rec.assistant_id.name or ''} - "
                f"{rec.file_id.display_name or ''} "
                f"({labels.get(rec.mode_rattachement, '')})"
            )

    # ── Constraints ───────────────────────────────────────────────────────────

    @api.constrains("mode_rattachement", "service_prioritaire_id")
    def _check_mode_prioritaire(self):
        for rec in self:
            if rec.mode_rattachement == "prioritaire" and not rec.service_prioritaire_id:
                raise ValidationError(
                    _("Un service prioritaire est obligatoire en mode prioritaire.")
                )

    @api.constrains("assistant_id", "active")
    def _check_unique_active_rattachement(self):
        for rec in self:
            if rec.active:
                count = self.search_count([
                    ("assistant_id", "=", rec.assistant_id.id),
                    ("active",       "=", True),
                    ("id",           "!=", rec.id),
                ])
                if count:
                    raise ValidationError(
                        _("Cet assistant possède déjà un rattachement actif.")
                    )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_queue_from_mode(self, mode_rattachement, file_id=False, service_prioritaire_id=False):
        """
        Résout la file à persister dans file_id lors de la configuration
        du rattachement (pos_set_my_rattachement).
        En mode prioritaire, retourne la file liée au service prioritaire.
        En mode auto, retourne n'importe quelle file active (la vraie
        résolution se fait dynamiquement à chaque appel de ticket).
        """
        Queue = self.env["pharmacy.queue"]

        if mode_rattachement == "manuel":
            if not file_id:
                raise UserError(_("En mode manuel, il faut choisir une file."))
            queue = Queue.browse(file_id)
            if not queue.exists():
                raise UserError(_("La file choisie est introuvable."))
            return queue

        if mode_rattachement == "auto_attente":
            queues = Queue.search([("active", "=", True)], limit=1)
            if not queues:
                raise UserError(_("Aucune file active trouvée."))
            return queues

        if mode_rattachement == "prioritaire":
            if not service_prioritaire_id:
                raise UserError(_("Le service prioritaire est obligatoire."))
            service = self.env["pharmacy.service"].browse(service_prioritaire_id)
            if not service.exists():
                raise UserError(_("Le service prioritaire choisi est introuvable."))
            if not service.queue_id:
                raise UserError(_("Aucune file n'est liée au service prioritaire choisi."))
            return service.queue_id

        raise UserError(_("Mode de rattachement invalide."))

    def _get_my_active_rattachement(self):
        user = self.env.user
        rattachement = self.search([
            ("assistant_id", "=", user.id),
            ("active",       "=", True),
        ], order="date_debut desc", limit=1)

        if not rattachement:
            raise UserError(_("Aucun rattachement actif trouvé."))
        if not rattachement.file_id:
            raise UserError(_("Aucune file n'est liée à votre rattachement."))

        return rattachement

    def _get_next_waiting_ticket(self, queue):
        """Retourne le prochain ticket en attente dans une file."""
        return self.env["pharmacy.ticket"].search([
            ("queue_id", "=", queue.id),
            ("etat",     "=", "en_attente"),
        ], order="priorite desc, heure_creation asc", limit=1)

    def _resolve_target_queue(self, rattachement):
        """
        Résout dynamiquement la file dans laquelle appeler le prochain ticket.

        Règles :
        - manuel      → toujours rattachement.file_id
        - auto_attente → file la plus chargée (_pick_busiest_queue)
        - prioritaire  → file propre (file_prioritaire_id) en premier ;
                         si elle est vide → bascule auto sur la plus chargée.
                         Dès qu'un ticket arrive dans la file propre, le
                         prochain call_next y retourne automatiquement,
                         même si l'opérateur traitait une autre file.

        Note : on utilise systématiquement file_prioritaire_id et NON
        file_id, car ce dernier peut avoir été mis à jour lors d'une
        bascule automatique précédente.
        """
        mode = rattachement.mode_rattachement

        if mode == "manuel":
            return rattachement.file_id

        if mode == "auto_attente":
            return self._pick_busiest_queue()

        if mode == "prioritaire":
            # file_prioritaire_id = file propre d'origine, jamais écrasée.
            # Fallback sur file_id pour les rattachements antérieurs à la migration.
            own_queue = rattachement.file_prioritaire_id or rattachement.file_id
            if own_queue and self._get_next_waiting_ticket(own_queue):
                return own_queue
            # File propre vide → bascule temporaire sur la file la plus chargée
            return self._pick_busiest_queue()

        raise UserError(_("Mode de rattachement invalide."))

    def _pick_busiest_queue(self):
        """
        Retourne la file active avec le plus de tickets en attente.
        À égalité, préfère celle dont le premier ticket est arrivé
        le plus tôt (heure_creation la plus ancienne).
        """
        Queue  = self.env["pharmacy.queue"]
        queues = Queue.search([("active", "=", True)])
        if not queues:
            return Queue  # recordset vide

        best_queue    = None
        best_count    = -1
        best_earliest = None

        for q in queues:
            tickets = self.env["pharmacy.ticket"].search([
                ("queue_id", "=", q.id),
                ("etat",     "=", "en_attente"),
            ], order="heure_creation asc")

            count    = len(tickets)
            earliest = tickets[0].heure_creation if tickets else None

            if count == 0:
                continue

            if best_queue is None:
                best_queue    = q
                best_count    = count
                best_earliest = earliest
                continue

            if count > best_count:
                best_queue    = q
                best_count    = count
                best_earliest = earliest
            elif (
                count == best_count
                and earliest and best_earliest
                and earliest < best_earliest
            ):
                best_queue    = q
                best_earliest = earliest

        return best_queue if best_queue else Queue

    # ── POS API ───────────────────────────────────────────────────────────────

    @api.model
    def pos_get_my_rattachement(self):
        user         = self.env.user
        rattachement = self.search([
            ("assistant_id", "=", user.id),
            ("active",       "=", True),
        ], order="date_debut desc", limit=1)

        if not rattachement:
            return {
                "found":               False,
                "mode":                False,
                "user_id":             user.id,
                "queue_id":            False,
                "queue_name":          False,
                "poste_number":        False,
                "current_ticket_id":   False,
                "current_ticket_name": False,
            }

        return {
            "found":               True,
            "mode":                rattachement.mode_rattachement,
            "user_id":             user.id,
            "queue_id":            rattachement.file_id.id            if rattachement.file_id            else False,
            "queue_name":          rattachement.file_id.display_name  if rattachement.file_id            else False,
            "poste_number":        rattachement.poste_number          or False,
            "current_ticket_id":   rattachement.current_ticket_id.id  if rattachement.current_ticket_id  else False,
            "current_ticket_name": rattachement.current_ticket_id.name if rattachement.current_ticket_id else False,
        }

    @api.model
    def pos_set_my_rattachement(
        self,
        mode_rattachement,
        file_id=False,
        service_prioritaire_id=False,
        poste_number=False,
    ):
        user = self.env.user
        queue = self._get_queue_from_mode(
            mode_rattachement,
            file_id=file_id,
            service_prioritaire_id=service_prioritaire_id,
        )

        rattachement = self.search([
            ("assistant_id", "=", user.id),
            ("active", "=", True),
        ], order="date_debut desc", limit=1)

        new_poste = str(poste_number) if poste_number else "1"
        new_file_prioritaire_id = queue.id if mode_rattachement == "prioritaire" else False

        vals = {
            "assistant_id": user.id,
            "mode_rattachement": mode_rattachement,
            "file_id": queue.id,
            "service_prioritaire_id": service_prioritaire_id or False,
            "poste_number": new_poste,
            "file_prioritaire_id": new_file_prioritaire_id,
        }

        if rattachement:
            has_changed = (
                rattachement.mode_rattachement != mode_rattachement
                or (rattachement.file_id.id if rattachement.file_id else False) != queue.id
                or (rattachement.service_prioritaire_id.id if rattachement.service_prioritaire_id else False) != (service_prioritaire_id or False)
                or (rattachement.poste_number or "1") != new_poste
                or (rattachement.file_prioritaire_id.id if rattachement.file_prioritaire_id else False) != new_file_prioritaire_id
            )

            if has_changed:
                self._close_and_archive_current_rattachement(rattachement)
                rattachement = self.create(vals)
            else:
                rattachement.write(vals)
        else:
            rattachement = self.create(vals)

        return {
            "found": True,
            "mode": mode_rattachement,
            "queue_id": queue.id,
            "queue_name": queue.display_name,
            "poste_number": rattachement.poste_number,
            "current_ticket_id": rattachement.current_ticket_id.id if rattachement.current_ticket_id else False,
            "current_ticket_name": rattachement.current_ticket_id.name if rattachement.current_ticket_id else False,
        }

    @api.model
    def pos_call_next_ticket(self):
        rattachement = self._get_my_active_rattachement()

        _logger.info(
            "POS CALL NEXT — rattachement=%s mode=%s",
            rattachement.id, rattachement.mode_rattachement,
        )

        try:
            old_ticket = rattachement.current_ticket_id
            if old_ticket:
                _logger.info(
                    "Ancien ticket avant appel suivant => %s (etat=%s)",
                    old_ticket.name, old_ticket.etat,
                )
                if old_ticket.etat != "termine":
                    old_ticket.action_terminer()
                    self._create_ticket_history_trace(rattachement, old_ticket)
                    _logger.info("Ancien ticket terminé => %s", old_ticket.name)
                rattachement.write({"current_ticket_id": False})

            # 2. Résoudre dynamiquement la file cible
            #    En mode prioritaire : vérifie file_prioritaire_id en premier,
            #    bascule auto si vide, retour automatique dès qu'un ticket
            #    arrive dans la file propre.
            queue = self._resolve_target_queue(rattachement)

            if not queue or not queue.exists():
                return {
                    "success":      True,
                    "message":      _("Aucune file active disponible."),
                    "queue_name":   False,
                    "poste_number": rattachement.poste_number,
                    "ticket":       False,
                }

            # 3. Chercher le prochain ticket
            next_ticket = self._get_next_waiting_ticket(queue)
            _logger.info(
                "Next ticket trouvé = %s",
                next_ticket.name if next_ticket else "AUCUN",
            )

            if not next_ticket:
                return {
                    "success":      True,
                    "message":      _("Aucun ticket en attente dans la file."),
                    "queue_name":   queue.display_name,
                    "poste_number": rattachement.poste_number,
                    "ticket":       False,
                }

            _logger.info("Appel ticket %s", next_ticket.name)
            next_ticket.action_appeler()

            # 5. Mettre à jour le rattachement
            #    • current_ticket_id et last_called_at → toujours mis à jour
            #    • file_id → mis à jour pour l'affichage si la file a changé
            #    • file_prioritaire_id → JAMAIS touché ici (mémoire permanente)
            update_vals = {
                "current_ticket_id": next_ticket.id,
                "last_called_at":    fields.Datetime.now(),
            }
            if queue.id != rattachement.file_id.id:
                update_vals["file_id"] = queue.id

            rattachement.write(update_vals)

            _logger.info(
                "SUIVANT OK => assistant=%s | file=%s | ticket=%s",
                rattachement.assistant_id.name,
                queue.display_name,
                next_ticket.name,
            )

            return {
                "success":      True,
                "message":      _("Ticket suivant appelé."),
                "queue_name":   queue.display_name,
                "poste_number": rattachement.poste_number,
                "ticket": {
                    "id":   next_ticket.id,
                    "name": next_ticket.name,
                    "etat": next_ticket.etat,
                },
            }

        except Exception as e:
            _logger.exception("Erreur pos_call_next_ticket: %s", e)
            raise

    @api.model
    def pos_finish_current_ticket(self):
        rattachement = self._get_my_active_rattachement()
        current_ticket = rattachement.current_ticket_id

        if not current_ticket:
            return {
                "success": True,
                "message": _("Aucun ticket en cours pour cet assistant."),
                "ticket": False,
            }

        if current_ticket.etat != "termine":
            current_ticket.action_terminer()

        self._create_ticket_history_trace(rattachement, current_ticket)

        rattachement.write({"current_ticket_id": False})

        _logger.info(
            "TERMINER => assistant=%s | ticket=%s",
            rattachement.assistant_id.name,
            current_ticket.name,
        )

        return {
            "success": True,
            "message": _("Ticket terminé."),
            "ticket": {
                "id": current_ticket.id,
                "name": current_ticket.name,
                "etat": current_ticket.etat,
            },
        }
    def _close_and_archive_current_rattachement(self, rattachement):
            now            = fields.Datetime.now()
            current_ticket = rattachement.current_ticket_id

            self.env["pharmacy.queue.history"].create({
                "rattachement_id":       rattachement.id,
                "assistant_id":          rattachement.assistant_id.id,
                "file_id":               rattachement.file_id.id if rattachement.file_id else False,
                "service_id":            rattachement.file_id.service_id.id
                                        if rattachement.file_id and rattachement.file_id.service_id
                                        else False,
                "mode_rattachement":     rattachement.mode_rattachement,
                "poste_number":          rattachement.poste_number,
                "date_debut":            rattachement.date_debut,
                "date_fin":              now,
                "ticket_id":             current_ticket.id           if current_ticket else False,
                "date_debut_traitement": current_ticket.heure_appel  if current_ticket else False,
                "date_fin_traitement":   current_ticket.heure_fin    if current_ticket else False,
            })

            rattachement.write({
                "active":            False,
                "date_fin":          now,
                "current_ticket_id": False,
            })
    def _create_ticket_history_trace(self, rattachement, ticket):
        if not rattachement or not ticket:
            return False
        existing = self.env["pharmacy.queue.history"].search([
            ("ticket_id", "=", ticket.id),
        ], limit=1)
        if existing:
            return existing
        return self.env["pharmacy.queue.history"].create({
            "rattachement_id": rattachement.id,
            "assistant_id": rattachement.assistant_id.id,
            "file_id": ticket.queue_id.id if ticket.queue_id else (rattachement.file_id.id if rattachement.file_id else False),
            "service_id": ticket.service_id.id if ticket.service_id else False,
            "mode_rattachement": rattachement.mode_rattachement,
            "poste_number": rattachement.poste_number,
            "date_debut": rattachement.date_debut or fields.Datetime.now(),
            "date_fin": fields.Datetime.now(),
            "ticket_id": ticket.id,
            "date_debut_traitement": ticket.heure_appel,
            "date_fin_traitement": ticket.heure_fin,
        })
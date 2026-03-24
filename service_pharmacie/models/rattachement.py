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

    mode_rattachement = fields.Selection(
        [
            ("manuel", "Manuel"),
            ("auto_attente", "Automatique (temps d'attente)"),
            ("prioritaire", "Prioritaire"),
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
    date_fin = fields.Datetime()
    active = fields.Boolean(default=True)

    
    

    def _domain_assistant_id(self):
        user_group = self.env.ref("base.group_user").id
        admin_group = self.env.ref("base.group_system").id

        self.env.cr.execute("""
            SELECT DISTINCT uid
            FROM res_groups_users_rel
            WHERE gid IN %s
        """, [(user_group, admin_group)])

        user_ids = [row[0] for row in self.env.cr.fetchall()]
        return [("id", "in", user_ids)]

    @api.depends("assistant_id", "file_id", "mode_rattachement")
    def _compute_display_name(self):
        labels = dict(self._fields["mode_rattachement"].selection)
        for rec in self:
            rec.display_name = (
                f"{rec.assistant_id.name or ''} - "
                f"{rec.file_id.display_name or ''} "
                f"({labels.get(rec.mode_rattachement, '')})"
            )

    @api.constrains("mode_rattachement", "service_prioritaire_id")
    def _check_mode_prioritaire(self):
        for rec in self:
            if rec.mode_rattachement == "prioritaire" and not rec.service_prioritaire_id:
                raise ValidationError(
                    _("Un service prioritaire est obligatoire en mode prioritaire.")
                )

    def _get_queue_from_mode(self, mode_rattachement, file_id=False, service_prioritaire_id=False):
        Queue = self.env["pharmacy.queue"]

        if mode_rattachement == "manuel":
            if not file_id:
                raise UserError(_("En mode manuel, il faut choisir une file."))
            queue = Queue.browse(file_id)
            if not queue.exists():
                raise UserError(_("La file choisie est introuvable."))
            return queue

        if mode_rattachement == "auto_attente":
            queues = Queue.search([("active", "=", True)])
            if not queues:
                raise UserError(_("Aucune file active trouvée."))
            queue = max(queues, key=lambda q: q.temps_attente_estime or 0)
            return queue

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
            ("active", "=", True),
        ], order="date_debut desc", limit=1)

        if not rattachement:
            raise UserError(_("Aucun rattachement actif trouvé."))

        if not rattachement.file_id:
            raise UserError(_("Aucune file n'est liée à votre rattachement."))

        return rattachement

    def _get_next_waiting_ticket(self, queue):
        return self.env["pharmacy.ticket"].search([
            ("queue_id", "=", queue.id),
            ("etat", "=", "en_attente"),
        ], order="priorite desc, heure_creation asc", limit=1)

    @api.model
    def pos_get_my_rattachement(self):
        user = self.env.user

        rattachement = self.search([
            ("assistant_id", "=", user.id),
            ("active", "=", True),
        ], order="date_debut desc", limit=1)

        if not rattachement:
            return {
                "found": False,
                "mode": False,
                "user_id": user.id,
                "queue_id": False,
                "queue_name": False,
                "poste_number": False,
                "current_ticket_id": False,
                "current_ticket_name": False,
            }

        return {
            "found": True,
            "mode": rattachement.mode_rattachement,
            "user_id": user.id,
            "queue_id": rattachement.file_id.id if rattachement.file_id else False,
            "queue_name": rattachement.file_id.display_name if rattachement.file_id else False,
            "poste_number": rattachement.poste_number or False,
            "current_ticket_id": rattachement.current_ticket_id.id if rattachement.current_ticket_id else False,
            "current_ticket_name": rattachement.current_ticket_id.name if rattachement.current_ticket_id else False,
        }
    @api.model
    def pos_set_my_rattachement(self, mode_rattachement, file_id=False, service_prioritaire_id=False, poste_number=False):
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

        vals = {
            "assistant_id": user.id,
            "mode_rattachement": mode_rattachement,
            "file_id": queue.id,
            "service_prioritaire_id": service_prioritaire_id or False,
            "poste_number": str(poste_number) if poste_number else "1",
        }

        if rattachement:
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
        queue = rattachement.file_id

        _logger.info("POS CALL NEXT - rattachement=%s queue=%s", rattachement.id, queue.display_name)

        try:
            old_ticket = rattachement.current_ticket_id

            # 1) Toujours terminer l'ancien ticket avant de chercher/appeler le suivant
            if old_ticket:
                _logger.info(
                    "Ancien ticket détecté avant appel du suivant => %s (etat=%s)",
                    old_ticket.name,
                    old_ticket.etat,
                )

                if old_ticket.etat != "termine":
                    old_ticket.action_terminer()
                    _logger.info("Ancien ticket terminé => %s", old_ticket.name)

                # on détache tout de suite l'ancien ticket du rattachement
                rattachement.write({"current_ticket_id": False})

            # 2) Chercher le prochain ticket en attente
            next_ticket = self._get_next_waiting_ticket(queue)
            _logger.info("Next ticket trouvé = %s", next_ticket.name if next_ticket else "AUCUN")

            if not next_ticket:
                return {
                    "success": True,
                    "message": _("Aucun ticket en attente dans la file."),
                    "queue_name": queue.display_name,
                    "poste_number": rattachement.poste_number,
                    "ticket": False,
                }

            # 3) Appeler le nouveau ticket
            _logger.info("Appel ticket %s", next_ticket.name)
            next_ticket.action_appeler()

            # 4) Lier le nouveau ticket comme ticket courant
            rattachement.write({
                "current_ticket_id": next_ticket.id,
                "last_called_at": fields.Datetime.now(),
            })

            _logger.info(
                "SUIVANT OK => assistant=%s | file=%s | ticket=%s",
                rattachement.assistant_id.name,
                queue.display_name,
                next_ticket.name,
            )

            return {
                "success": True,
                "message": _("Ticket suivant appelé."),
                "queue_name": queue.display_name,
                "poste_number": rattachement.poste_number,
                "ticket": {
                    "id": next_ticket.id,
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
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PosOrderPaid(models.Model):
    """Extension du modèle pos.order pour la gestion admin des commandes payées."""
    _inherit = 'pos.order'

    can_refund = fields.Boolean(
        string='Peut être remboursé',
        compute='_compute_can_refund',
        store=False,
    )

    refund_count = fields.Integer(
        string='Nb Remboursements',
        compute='_compute_refund_count',
        store=False,
    )

    @api.depends('state', 'is_refund', 'amount_total')
    def _compute_can_refund(self):
        for order in self:
            order.can_refund = (
                order.state in ('paid', 'done', 'invoiced')
                and not order.is_refund
                and order.amount_total > 0
            )

    @api.depends('lines')
    def _compute_refund_count(self):
        for order in self:
            refunds = self.env['pos.order'].search([
                ('lines.refunded_orderline_id', 'in', order.lines.ids)
            ])
            order.refund_count = len(refunds)

    def action_open_refund_wizard(self):
        """Ouvre le wizard de remboursement."""
        self.ensure_one()
        if not self.can_refund:
            raise UserError(_("Cette commande ne peut pas être remboursée."))

        return {
            'name': _('Rembourser la commande %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'pos.refund.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id':    self.id,
                'default_order_name':  self.name,
                'default_amount_total': self.amount_total,
            },
        }

    def action_view_refunds(self):
        """Voir les remboursements liés à cette commande."""
        self.ensure_one()
        refunds = self.env['pos.order'].search([
            ('lines.refunded_orderline_id', 'in', self.lines.ids)
        ])
        return {
            'name': _('Remboursements de %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'pos.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', refunds.ids)],
        }
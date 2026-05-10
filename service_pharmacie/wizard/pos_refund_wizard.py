# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class PosRefundWizard(models.TransientModel):
    _name = 'pos.refund.wizard'
    _description = 'Wizard Remboursement POS'

    order_id = fields.Many2one('pos.order', string='Commande', required=True, readonly=True)
    order_name = fields.Char(string='Référence commande', readonly=True)
    amount_total = fields.Float(string='Montant total original', readonly=True)

    refund_reason = fields.Selection([
        ('return',           'Retour produit'),
        ('defect',           'Produit défectueux'),
        ('error',            'Erreur de caisse'),
        ('customer_request', 'Demande client'),
        ('other',            'Autre'),
    ], string='Raison du remboursement', required=True, default='return')

    refund_note = fields.Text(string='Note interne')

    line_ids = fields.One2many(
        'pos.refund.wizard.line', 'wizard_id', string='Lignes à rembourser'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        order_id = res.get('order_id') or self.env.context.get('default_order_id')
        if not order_id:
            return res

        order = self.env['pos.order'].sudo().browse(int(order_id))
        if not order.exists():
            return res

        res['order_id']     = order.id
        res['order_name']   = order.name
        res['amount_total'] = order.amount_total

        lines = []
        for line in order.lines.sudo():
            qty_remaining = self._get_qty_remaining(line)
            if qty_remaining <= 0:
                continue  # ligne déjà totalement remboursée, ne pas l'afficher
            lines.append((0, 0, {
                'order_line_id': line.id,
                'qty_to_refund': qty_remaining,
            }))

        if not lines:
            # Toutes les lignes ont déjà été remboursées
            raise UserError(_("Cette commande a déjà été entièrement remboursée."))

        res['line_ids'] = lines
        return res

    @api.model
    def _get_qty_remaining(self, order_line):
        """Calcule la quantité encore remboursable pour une ligne donnée."""
        qty_original = abs(order_line.qty)

        # Chercher toutes les lignes de remboursement liées à cette ligne
        refund_lines = self.env['pos.order.line'].sudo().search([
            ('refunded_orderline_id', '=', order_line.id),
        ])
        qty_already_refunded = sum(abs(l.qty) for l in refund_lines)

        return max(0.0, qty_original - qty_already_refunded)

    def action_refund(self):
        self.ensure_one()
        order = self.order_id
        if not order:
            raise UserError(_("Aucune commande sélectionnée."))

        lines_to_refund = self.line_ids.filtered(lambda l: l.qty_to_refund > 0)
        if not lines_to_refund:
            raise UserError(_("Veuillez sélectionner au moins une ligne à rembourser."))

        # Validation : vérifier contre les quantités RÉELLEMENT remboursables
        for wline in lines_to_refund:
            original = wline.order_line_id.sudo()
            if not original.exists():
                raise ValidationError(_(
                    "La ligne '%s' n'existe plus en base.", wline.product_name or '?'
                ))

            qty_remaining = self._get_qty_remaining(original)

            if qty_remaining <= 0:
                raise ValidationError(_(
                    "La ligne '%s' a déjà été entièrement remboursée.",
                    wline.product_name or '?'
                ))

            if wline.qty_to_refund > qty_remaining:
                raise ValidationError(_(
                    "La quantité à rembourser (%(r)s) pour '%(p)s' dépasse "
                    "la quantité encore remboursable (%(o)s). "
                    "%(already)s unité(s) ont déjà été remboursées.",
                    r=wline.qty_to_refund,
                    p=wline.product_name or '?',
                    o=qty_remaining,
                    already=abs(original.qty) - qty_remaining,
                ))

        refund_order = self._create_refund_order(order, lines_to_refund)

        if self.refund_note:
            refund_order.sudo().write({'internal_note': self.refund_note})

        try:
            refund_order.sudo()._pharmacie_create_stock_picking()
        except Exception as e:
            _logger.error("[PHARMACIE] Erreur picking retour: %s", e)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title":   _("Remboursement effectué"),
                "message": _("Remboursement %s créé avec succès.") % refund_order.name,
                "type":    "success",
                "sticky":  False,
                "next":    {"type": "ir.actions.act_window_close"},
            },
        }

    def _create_refund_order(self, order, lines_to_refund):
        """Crée manuellement une commande POS de remboursement."""
        PosOrder     = self.env['pos.order'].sudo()
        PosOrderLine = self.env['pos.order.line'].sudo()

        session = self.env['pos.session'].sudo().search([
            ('config_id', '=', order.config_id.id),
            ('state', '=', 'opened'),
        ], limit=1) or order.session_id

        refund_order = PosOrder.create({
            'name':          '/',
            'session_id':    session.id,
            'config_id':     order.config_id.id,
            'partner_id':    order.partner_id.id if order.partner_id else False,
            'employee_id':   order.employee_id.id if order.employee_id else False,
            'is_refund':     True,
            'state':         'paid',
            'amount_tax':    0.0,
            'amount_total':  0.0,
            'amount_paid':   0.0,
            'amount_return': 0.0,
        })

        total = 0.0

        for wline in lines_to_refund:
            orig = wline.order_line_id.sudo()
            qty  = -wline.qty_to_refund  # négatif

            PosOrderLine.create({
                'order_id':              refund_order.id,
                'product_id':            orig.product_id.id,
                'full_product_name':     orig.full_product_name,
                'qty':                   qty,
                'price_unit':            orig.price_unit,
                'discount':              orig.discount,
                'tax_ids':               [(6, 0, orig.tax_ids.ids)],
                'price_subtotal':        qty * orig.price_unit,
                'price_subtotal_incl':   qty * orig.price_unit,
                'refunded_orderline_id': orig.id,  # ← clé anti-doublon
            })
            total += qty * orig.price_unit

        refund_order.write({
            'amount_total':  total,
            'amount_paid':   total,
            'amount_return': 0.0,
        })

        payment_method = order.payment_ids[:1].payment_method_id if order.payment_ids else False
        if payment_method:
            self.env['pos.payment'].sudo().create({
                'pos_order_id':      refund_order.id,
                'payment_method_id': payment_method.id,
                'amount':            total,
            })

        _logger.info(
            "[PHARMACIE] Remboursement %s créé pour commande %s",
            refund_order.name, order.name,
        )
        return refund_order


class PosRefundWizardLine(models.TransientModel):
    _name = 'pos.refund.wizard.line'
    _description = 'Ligne Wizard Remboursement POS'

    wizard_id     = fields.Many2one('pos.refund.wizard', required=True, ondelete='cascade')
    order_line_id = fields.Many2one('pos.order.line', string='Ligne originale', required=True)

    product_id = fields.Many2one(
        'product.product', string='Produit',
        compute='_compute_from_line', store=True,
    )
    product_name = fields.Char(
        string='Désignation',
        compute='_compute_from_line', store=True,
    )
    qty_original = fields.Float(
        string='Qté vendue',
        compute='_compute_from_line', store=True,
    )
    qty_already_refunded = fields.Float(
        string='Déjà remboursé',
        compute='_compute_from_line', store=True,
    )
    qty_remaining = fields.Float(
        string='Remboursable',
        compute='_compute_from_line', store=True,
    )
    price_unit = fields.Float(
        string='Prix unitaire',
        compute='_compute_from_line', store=True,
    )
    price_subtotal = fields.Float(
        string='Sous-total TTC',
        compute='_compute_from_line', store=True,
    )

    @api.depends('order_line_id')
    def _compute_from_line(self):
        for rec in self:
            line = rec.order_line_id.sudo()
            if not (line and line.exists()):
                rec.product_id          = False
                rec.product_name        = '?'
                rec.qty_original        = 0.0
                rec.qty_already_refunded = 0.0
                rec.qty_remaining       = 0.0
                rec.price_unit          = 0.0
                rec.price_subtotal      = 0.0
                continue

            qty_original = abs(line.qty)

            refund_lines = rec.env['pos.order.line'].sudo().search([
                ('refunded_orderline_id', '=', line.id),
            ])
            qty_already = sum(abs(l.qty) for l in refund_lines)
            qty_remaining = max(0.0, qty_original - qty_already)

            rec.product_id           = line.product_id.id if line.product_id else False
            rec.product_name         = line.full_product_name or (line.product_id.name if line.product_id else '?')
            rec.qty_original         = qty_original
            rec.qty_already_refunded = qty_already
            rec.qty_remaining        = qty_remaining
            rec.price_unit           = line.price_unit
            rec.price_subtotal       = line.price_subtotal_incl

    qty_to_refund = fields.Float(string='Qté à rembourser', default=0.0)

    amount_refund = fields.Float(
        string='Montant remboursé',
        compute='_compute_amount_refund',
        store=False,
    )

    @api.depends('qty_to_refund', 'price_unit')
    def _compute_amount_refund(self):
        for line in self:
            line.amount_refund = line.qty_to_refund * line.price_unit
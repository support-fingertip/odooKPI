# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class VisitCollection(models.Model):
    """Payment collection captured during a customer visit."""
    _name = 'visit.collection'
    _description = 'Visit Collection'
    _order = 'date desc, id'
    _rec_name = 'name'

    name = fields.Char(
        string='Reference', required=True, copy=False,
        readonly=True, default='New')
    visit_id = fields.Many2one(
        'visit.model', string='Visit', required=True, ondelete='cascade', index=True)
    partner_id = fields.Many2one(
        related='visit_id.partner_id', string='Customer', store=True, readonly=True)
    employee_id = fields.Many2one(
        related='visit_id.employee_id', string='Employee', store=True, readonly=True)
    date = fields.Date(string='Date', default=fields.Date.today, required=True)

    amount = fields.Monetary(string='Amount', required=True, currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id)
    payment_mode = fields.Selection([
        ('Cash', 'Cash'),
        ('UPI', 'UPI'),
        ('Cheque', 'Cheque'),
        ('NEFT', 'NEFT/RTGS'),
    ], string='Payment Mode', required=True, default='Cash')
    reference = fields.Char(string='Reference / Cheque No.')
    remarks = fields.Text(string='Remarks')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True)

    # Link to Odoo account.payment (created on confirm)
    payment_id = fields.Many2one('account.payment', string='Payment', readonly=True)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('visit.collection') or 'New'
        return super().create(vals)

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("Collection amount must be greater than zero."))

    def action_confirm(self):
        """Confirm collection and create account payment to reduce outstanding."""
        # Use lang=False to bypass Odoo 18 jsonb translation lookups on
        # partner.name / journal.name (avoids jsonb_path_query_first type errors).
        env_nt = self.env(context=dict(self.env.context, lang=False))
        for rec in self:
            if rec.state != 'draft':
                continue
            try:
                # Read partner ID without triggering translated field lookup
                partner_id = rec.visit_id.partner_id.id if rec.visit_id else False
                if not partner_id:
                    raise UserError(_("Customer is required to confirm collection."))

                # Find a suitable journal for the payment mode
                journal = self._get_payment_journal(rec.payment_mode)
                if not journal:
                    _logger.warning(
                        "No journal found for payment mode %s. "
                        "Collection confirmed without account.payment.", rec.payment_mode
                    )
                    rec.write({'state': 'confirmed'})
                    continue

                # Fetch currency without translation
                currency_id = rec.currency_id.id if rec.currency_id else env_nt['res.currency'].sudo().search(
                    [('name', '=', 'INR')], limit=1).id or 1

                payment_vals = {
                    'partner_id': partner_id,
                    'partner_type': 'customer',
                    'payment_type': 'inbound',
                    'amount': rec.amount,
                    'currency_id': currency_id,
                    'journal_id': journal.id,
                    'date': rec.date,
                    'ref': rec.reference or rec.name,
                }
                # Odoo 18: payment_method_line_id is required on account.payment
                if hasattr(journal, 'inbound_payment_method_line_ids') and journal.inbound_payment_method_line_ids:
                    payment_vals['payment_method_line_id'] = journal.inbound_payment_method_line_ids[0].id

                payment = env_nt['account.payment'].sudo().create(payment_vals)
                payment.sudo().action_post()

                rec.write({'state': 'confirmed', 'payment_id': payment.id})
            except Exception as e:
                _logger.error("Error confirming collection %s: %s", rec.id, e, exc_info=True)
                raise UserError(_("Failed to confirm collection: %s") % str(e))

    def action_cancel(self):
        for rec in self:
            if rec.payment_id and rec.payment_id.state == 'posted':
                try:
                    rec.payment_id.action_cancel()
                except Exception:
                    pass
            rec.write({'state': 'cancelled'})

    def _get_payment_journal(self, payment_mode):
        """Return accounting journal matching payment mode."""
        mode_map = {
            'Cash': 'cash',
            'UPI': 'bank',
            'Cheque': 'bank',
            'NEFT': 'bank',
        }
        journal_type = mode_map.get(payment_mode, 'bank')
        return self.env['account.journal'].sudo().search(
            [('type', '=', journal_type), ('company_id', '=', self.env.company.id)],
            limit=1
        )

    @api.model
    def get_customer_outstanding(self, partner_id):
        """Return outstanding info for a partner."""
        # lang=False prevents jsonb_path_query_first errors on translated fields
        env_nt = self.env(context=dict(self.env.context, lang=False))
        partner = env_nt['res.partner'].sudo().browse(partner_id)
        if not partner.exists():
            return {'total': 0, 'credit_limit': 0, 'overdue': 0, 'last_payment': None}

        # Unpaid outgoing invoices
        invoices = env_nt['account.move'].sudo().search([
            ('partner_id', '=', partner_id),
            ('move_type', '=', 'out_invoice'),
            ('payment_state', 'not in', ('paid', 'reversed')),
            ('state', '=', 'posted'),
        ])
        total_outstanding = sum(invoices.mapped('amount_residual'))

        from datetime import date as d_date
        today = d_date.today()
        overdue_amount = sum(
            inv.amount_residual for inv in invoices
            if inv.invoice_date_due and inv.invoice_date_due < today
        )

        # Credit limit from partner
        credit_limit = partner.credit_limit if hasattr(partner, 'credit_limit') else 0.0

        # Last payment
        last_payment = env_nt['account.payment'].sudo().search([
            ('partner_id', '=', partner_id),
            ('partner_type', '=', 'customer'),
            ('payment_type', '=', 'inbound'),
            ('state', '=', 'posted'),
        ], order='date desc', limit=1)

        return {
            'total': round(total_outstanding, 2),
            'credit_limit': round(credit_limit, 2),
            'overdue': round(overdue_amount, 2),
            'last_payment': str(last_payment.date) if last_payment else None,
            'last_payment_amount': round(last_payment.amount, 2) if last_payment else 0,
        }

from odoo import fields, models, api, _
from datetime import datetime,date
from odoo.exceptions import ValidationError, UserError
from odoo.osv import expression
import re
from odoo.tools import (
    date_utils,
    email_split,
    float_compare,
    float_is_zero,
    float_repr,
    format_amount,
    format_date,
    formatLang,
    frozendict,
    get_lang,
    groupby,
    is_html_empty,
    sql
)

import xmlrpc.client
# import pyodbc
import psycopg2
import psycopg2.extras

# Master Of Payments Month
class PaymentsMonth(models.Model):
    _name = 'payments.month'

    name = fields.Char(String='Payments Month')


class VouchersAccountsMaster(models.Model):

    _name = 'voucher.account.master'

    name = fields.Char(String='Payments Month')


# Master Of ATM ID
class AtmId(models.Model):
    _name = 'atm.id'

    name = fields.Char(String='ATM ID')


class HrExpenseInherit(models.Model):
    _inherit = 'hr.expense'

    atm_ids = fields.Many2many(comodel_name='atm.id', string='ATM ID')


class AnalyticPlanInherit(models.Model):
    _inherit = 'account.analytic.plan'

    is_dashboard = fields.Boolean(help="Enable it if you want to display it on Dashboard")


class AccountInvoiceReport(models.Model):
    _inherit = 'account.invoice.report'

    team_id = fields.Many2one(comodel_name='crm.team', string="Sales Team")

    # def _select(self):
    #     return super()._select() + ", move.team_id as team_id"
    #     pass


class ResPartner(models.Model):
    _inherit = 'res.partner'

    name = fields.Char(index=True, default_export_compatible=True, tracking=True)
    parent_id = fields.Many2one('res.partner', string='Related Company', index=True, tracking=True)
    vat = fields.Char(string='Tax ID', index=True,
                      help="The Tax Identification Number. Values here will be validated"
                           " based on the country format. You can use '/' to indicate that the partner is not subject "
                           "to tax.", tracking=True)

    street = fields.Char(tracking=True)
    street2 = fields.Char(tracking=True)
    zip = fields.Char(change_default=True, tracking=True)
    city = fields.Char(tracking=True)
    state_id = fields.Many2one("res.country.state", string='State', ondelete='restrict',
                               domain="[('country_id', '=?', country_id)]", tracking=True)
    country_id = fields.Many2one('res.country', string='Country', ondelete='restrict', tracking=True)



    cust_partner_type = fields.Selection([('customer', 'Customer'), ('vendor', 'Vendor'), ('individual', 'Individual'),('compliance','Compliance')],
                                         tracking=True)
    #  Making Tracking true for both the below fields
    property_account_payable_id = fields.Many2one('account.account', company_dependent=True,
                                                  string="Account Payable",
                                                  domain="[('company_ids', 'in', current_company_id)]",
                                                  help="This account will be used instead of the default one as the payable account for the current partner",
                                                  required=True, tracking=True)
    property_account_receivable_id = fields.Many2one('account.account', company_dependent=True,
                                                     string="Account Receivable",
                                                     domain="[('active','=',False),('company_ids', 'in', current_company_id)]",
                                                     help="This account will be used instead of the default one as the receivable account for the current partner",
                                                     required=True, tracking=True)


    @api.constrains('name')
    def _partner_unique_name(self):
        for rec in self:
            partner = self.env['res.partner'].search_count([('name', '=ilike', rec.name)])
            if partner > 1:
                raise ValidationError(f"Contact with the name {rec.name} is already been created.")


class AccountPaymentInherit(models.Model):
    _inherit = 'account.payment'

    payment_for_id = fields.Many2one('payment.for.master')
    payment_month_id = fields.Many2one(comodel_name='payments.month', string='Payments Month', tracking=True)
    approval_type = fields.Many2one(comodel_name='approval.category', string='Approval_type') ## No use till yet
    approval_request = fields.Many2one(comodel_name='approval.request', string='Approval Request')
    contact_type = fields.Selection(related="partner_id.cust_partner_type", store=True)
    partner_type = fields.Selection([
        ('customer', 'Customer'),
        ('supplier', 'Vendor'),
    ], default='customer', tracking=True, required=True)
    destination_account_id = fields.Many2one(
        comodel_name='account.account',
        string='Destination Account',
        store=True, readonly=False,
        compute='_compute_destination_account_id',
        domain="[('company_ids', 'in', company_id)]",
        check_company=True)
    reversal_move_id = fields.Many2one('account.move')

    @api.onchange('payment_for_id')
    def compute_destination_account(self):
        for rec in self:
            if rec.payment_for_id:
                rec.destination_account_id = rec.payment_for_id.account_id.id

    def _synchronize_from_moves(self, changed_fields):
        ''' Update the account.payment regarding its related account.move.
        Also, check both models are still consistent.
        :param changed_fields: A set containing all modified fields on account.move.
        '''
        if self._context.get('skip_account_move_synchronization'):
            return

        for pay in self.with_context(skip_account_move_synchronization=True):

            # After the migration to 14.0, the journal entry could be shared between the account.payment and the
            # account.bank.statement.line. In that case, the synchronization will only be made with the statement line.
            if pay.move_id.statement_line_id:
                continue

            move = pay.move_id
            move_vals_to_write = {}
            payment_vals_to_write = {}

            if 'journal_id' in changed_fields:
                if pay.journal_id.type not in ('bank', 'cash'):
                    raise UserError(_("A payment must always belongs to a bank or cash journal."))

            if 'line_ids' in changed_fields:
                all_lines = move.line_ids
                liquidity_lines, counterpart_lines, writeoff_lines = pay._seek_for_lines()

                if len(liquidity_lines) != 1:
                    raise UserError(_(
                        "Journal Entry %s is not valid. In order to proceed, the journal items must "
                        "include one and only one outstanding payments/receipts account.",
                        move.display_name,
                    ))

                # if len(counterpart_lines) != 1:
                #     raise UserError(_(
                #         "Journal Entry %s is not valid. In order to proceed, the journal items must "
                #         "include one and only one receivable/payable account (with an exception of "
                #         "internal transfers).",
                #         move.display_name,
                #     ))

                if any(line.currency_id != all_lines[0].currency_id for line in all_lines):
                    raise UserError(_(
                        "Journal Entry %s is not valid. In order to proceed, the journal items must "
                        "share the same currency.",
                        move.display_name,
                    ))

                if any(line.partner_id != all_lines[0].partner_id for line in all_lines):
                    raise UserError(_(
                        "Journal Entry %s is not valid. In order to proceed, the journal items must "
                        "share the same partner.",
                        move.display_name,
                    ))

                if counterpart_lines.account_id.account_type == 'asset_receivable':
                    partner_type = 'customer'
                else:
                    partner_type = 'supplier'

                liquidity_amount = liquidity_lines.amount_currency

                move_vals_to_write.update({
                    'currency_id': liquidity_lines.currency_id.id,
                    'partner_id': liquidity_lines.partner_id.id,
                })
                payment_vals_to_write.update({
                    'amount': abs(liquidity_amount),
                    'partner_type': partner_type,
                    'currency_id': liquidity_lines.currency_id.id,
                    'destination_account_id': counterpart_lines.account_id.id,
                    'partner_id': liquidity_lines.partner_id.id,
                })
                if liquidity_amount > 0.0:
                    payment_vals_to_write.update({'payment_type': 'inbound'})
                elif liquidity_amount < 0.0:
                    payment_vals_to_write.update({'payment_type': 'outbound'})

            move.write(move._cleanup_write_orm_values(move, move_vals_to_write))
            pay.write(move._cleanup_write_orm_values(pay, payment_vals_to_write))


    # Before posting the Payment adding the month is mandate as it will help us to determine salary
    def onchange_payment_month_id(self):
        for rec in self:
            cutoff_date = datetime(2025, 8, 31)
            if rec.payment_month_id and rec.payment_for == 'salary':
                payment =  self.env['account.payment'].search([('payment_month_id', '=', rec.payment_month_id.id),
                                                       ('partner_id', '=', rec.partner_id.id),
                                                       ('payment_for', '=', 'salary'),
                                                       ('id', '!=', rec.id),
                                                       ('state', '=', 'posted'),
                                                       # ('reversal_move_id', '=', False),
                                                       ('partner_bank_id', '=', rec.partner_bank_id.id),
                                                       ('create_date', '>', cutoff_date)], limit=1)
                if payment:
                    batch_numbers = ", ".join(payment.filtered(lambda p: p.source_doc).mapped('source_doc'))
                    raise ValidationError(f'Already made payment for {rec.partner_id.name} in {rec.payment_month_id.name} Batch Number {batch_numbers}')

    # if value is not set in approval request then user can edit and if approval request is set then validation
    # Error will be raised
    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.approval_request:
            raise ValidationError('You cannot change the value once the Approval request is set')

    # if value is not set in approval request then user can edit and if approval request is set then validation Error
    # will be raised
    @api.onchange('amount')
    def onchange_amount(self):
        if self.approval_request:
            raise ValidationError('You cannot change the value once the Approval request is set')

    # if value is not set in approval request then user can edit and if approval request is set then validation Error
    # will be raised
    @api.onchange('analytics_plan_id')
    def onchange_analytics_plan_id(self):
        if self.approval_request:
            raise ValidationError('You cannot change the value once the Approval request is set')

    # if value is not set in approval request then user can edit and if approval request is set then validation Error
    # will be raised
    @api.onchange('analytics_account_id')
    def onchange_analytics_account_id(self):
        if self.approval_request:
            raise ValidationError('You cannot change the value once the Approval request is set')

    # if value is not set in approval request then user can edit and if approval request is set then validation
    # Error will be raised
    @api.onchange('partner_bank_id')
    def onchange_partner_bank_id(self):
        if self.approval_request:
            raise ValidationError('You cannot change the value once the Approval request is set')

    @api.depends('state')
    def _compute_batch_payment_id(self):
        for payment in self.filtered(lambda p: p.state != 'posted'):
            # unlink the payment from the batch payment ids, hovewer _compute_amount
            # is not triggered by the ORM when setting batch_payment_id to None
            payment.batch_payment_id.update({'payment_ids': [(4, payment.id)]})

    # def action_draft(self):
    #     if self.payment_state == 'reversed' and self.reversal_move_id.filtered(lambda x: x.state == 'posted' and x.payment_state != 'reversed'):
    #         raise ValidationError("Kindly reset to draft the reversal entry first.")
    #     return super().action_draft()

    def action_post(self):
        self.onchange_payment_month_id()
        # if self.reversed_entry_id and self.reversed_entry_id.state != 'posted':
        #     raise ValidationError("Kindly post the entry from which this reversal entry was created")
        return super().action_post()

    def button_open_reversal_entry(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reversal Entry',
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': self.reversal_move_id.id,
        }

    def action_return_entry(self):
        if self.payment_type == 'outbound':
            if self.move_id:
                reversal_id = self.env['account.move.reversal'].create({'journal_id':self.journal_id.id,'date':date.today(),'move_ids':self.move_id.ids})
                # Run reverse (IGNORE return)
                reversal_id.refund_moves()

                # Now get created move from wizard
                reversed_move = reversal_id.new_move_ids

                # Link to payment
                self.reversal_move_id = reversed_move.id

                self.reversal_move_id = reversed_move.id
                # self.reversal_move_id = reversal_move_id.id
                # return {
                #     'name': f'Reverse of {self.name}',
                #     'type': 'ir.actions.act_window',
                #     'res_model': 'account.move',
                #     'view_mode': 'form',
                #     'res_id': reversal_move_id.id,
                # }



            # if self.reversed_entry_id:
            #     raise ValidationError("A reverse payment entry has already been created")
            # return_vend_pay = self.env['account.payment'].create(
            #     {'payment_type': 'inbound', 'journal_id': self.journal_id.id,
            #      'partner_id': self.partner_id.id, 'destination_account_id': self.destination_account_id.id,
            #      'partner_type': 'supplier', 'memo': f'Return Payment against {self.name}', 'amount': self.amount,
            #      'analytics_plan_id': self.analytics_plan_id.id,
            #      'analytics_account_id': self.analytics_account_id.id,
            #      'narration': self.narration,
            #      'partner_bank_id': self.partner_bank_id.id,
            #      'payment_month_id':self.payment_month_id.id,
            #      'month': self.month,
            #      'css_local_branch': self.css_local_branch,
            #      'css_state': self.css_state,
            #      })
            # return_vend_pay.message_post(body=f"Return Payment Created from {self._get_html_link(self.name)}")
            # self.message_post(body=f"Return Entry created {return_vend_pay._get_html_link(self.name)}")
            # # return_vend_pay.action_post()
            # self.move_id.payment_state = 'reversed'
            # return {
            #     'name': f'Reverse of {self.name}',
            #     'type': 'ir.actions.act_window',
            #     'res_model': 'account.payment',
            #     'view_mode': 'form',
            #     'res_id': return_vend_pay.id,
            # }


class ChangeJournalInBatch(models.TransientModel):
    _name = 'change.journal'

    journal_id = fields.Many2one(string='Journal', comodel_name='account.journal')
    batch_pay_id = fields.Many2one(string='Batch ', comodel_name='account.batch.payment')

    def change_journal_in_batch(self):
        self.batch_pay_id.changing_journal = True
        for rec in self.batch_pay_id.payment_ids:
            rec.state = 'draft'
            rec.posted_before = False
            seq = rec.name
            rec.name = False

            self.batch_pay_id.journal_id = self.journal_id.id
            rec.journal_id  = self.journal_id.id

            rec.posted_before = True
            rec.name = seq
            rec.state = 'posted'
            print('1111111')
        self.batch_pay_id.changing_journal = False
        print('change')


class BatchPaymentInherit(models.Model):
    _inherit = 'account.batch.payment'

    changing_journal = fields.Boolean(string='Allow Journal Change', default=False)

    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Low'),
        ('2', 'High'),
        ], string="Priority")

    # making a boolean field for high priority purpose
    prioritys = fields.Boolean()
    prioritys_1 = fields.Boolean()

    def validate_batch_button(self):
        res = super(BatchPaymentInherit, self).validate_batch_button()
        for payment in self.payment_ids:
            payment.date = self.bank_date
            # for line in payment.payment_ids:
            #     line.state = 'posted'
        return res

    def button_change_journal(self):
        return {
            'name': _('Change Journal'),
            'res_model': 'change.journal',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_batch_pay_id': self.id},
            # 'payment_id': self.id,
            'type': 'ir.actions.act_window'
        }

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = ['|', ('name', operator, name), ('ref_bank_no', operator, name)]
        return self._search(expression.OR([domain, args]), limit=limit, access_rights_uid=name_get_uid)

    @api.constrains('batch_type', 'journal_id', 'payment_ids')
    def _check_payments_constrains(self):
        for record in self:
            all_companies = set(record.payment_ids.mapped('company_id'))
            if len(all_companies) > 1:
                raise ValidationError(_("All payments in the batch must belong to the same company."))
            all_journals = set(record.payment_ids.mapped('journal_id'))
            if record.changing_journal is False:
                if (len(all_journals) > 1 or (record.payment_ids and record.payment_ids[:1].journal_id != record.journal_id)):
                    raise ValidationError(
                        _("The journal of the batch payment and of the payments it contains must be the same."))
            all_types = set(record.payment_ids.mapped('payment_type'))
            if all_types and record.batch_type not in all_types:
                raise ValidationError(_("The batch must have the same type as the payments it contains."))
            all_payment_methods = record.payment_ids.payment_method_id
            if len(all_payment_methods) > 1:
                raise ValidationError(_(f"All payments in the batch must share the same payment method."))
            if all_payment_methods and record.payment_method_id not in all_payment_methods:
                raise ValidationError(_("The batch must have the same payment method as the payments it contains."))
            payment_null = record.payment_ids.filtered(lambda p: p.amount == 0)
            if payment_null:
                raise ValidationError(_('You cannot add payments with zero amount in a Batch Payment.'))
            # non_posted = record.payment_ids.filtered(lambda p: p.state != 'posted')
            # if non_posted:
            #     raise ValidationError(_('You cannot add payments that are not posted.'))




class AnalyticItemsInherit(models.Model):
    _inherit = 'account.analytic.line'

    debit = fields.Float(compute="compute_debit_credit", store=True)
    credit = fields.Float(compute="compute_debit_credit", store=True)
    account_type = fields.Selection(related="general_account_id.account_type")
    month = fields.Char(compute="compute_month_transfer_date", store=True)
    transfer_date = fields.Date()

    @api.depends('move_line_id.payment_id.month', 'move_line_id.payment_id.transfer_date', 'move_line_id.payment_id')
    def compute_month_transfer_date(self):
        for rec in self:
            rec.month = rec.move_line_id.payment_id.month
            rec.transfer_date = rec.move_line_id.payment_id.transfer_date

    @api.depends('move_line_id.credit', 'move_line_id.debit', 'move_line_id')
    def compute_debit_credit(self):
        for rec in self:
            rec.debit = rec.credit = 0
            if rec.move_line_id and rec.account_type in ('asset_receivable', 'liability_payable'):
                if rec.amount < 0:
                    rec.debit = abs(rec.amount)
                elif rec.amount > 0:
                    rec.credit = rec.amount



class AccountMoveInherit(models.Model):
    _inherit = 'account.move'

    partner_type = fields.Selection([
        ('customer', 'Customer'),
        ('supplier', 'Vendor'),
    ], default='customer', tracking=True, required=True)



######## PURPUSOLY OVERIDING THE FUNCTION TO REMOVE CASH_ROUDING PARAMETER AS IT IS COMMMENTED BELOW IT WAS GIVING ADDONS ERROR ON LLIVE ####
    # @api.depends('invoice_payment_term_id', 'invoice_date', 'currency_id', 'amount_total_in_currency_signed', 'invoice_date_due')
    # def _compute_needed_terms(self):
    #     for invoice in self:
    #         is_draft = invoice.id != invoice._origin.id
    #         invoice.needed_terms = {}
    #         invoice.needed_terms_dirty = True
    #         sign = 1 if invoice.is_inbound(include_receipts=True) else -1
    #         if invoice.is_invoice(True) and invoice.invoice_line_ids:
    #             if invoice.invoice_payment_term_id:
    #                 if is_draft:
    #                     tax_amount_currency = 0.0
    #                     untaxed_amount_currency = 0.0
    #                     for line in invoice.invoice_line_ids:
    #                         untaxed_amount_currency += line.price_subtotal
    #                         for tax_result in (line.compute_all_tax or {}).values():
    #                             tax_amount_currency += -sign * tax_result.get('amount_currency', 0.0)
    #                     untaxed_amount = untaxed_amount_currency
    #                     tax_amount = tax_amount_currency
    #                 else:
    #                     tax_amount_currency = invoice.amount_tax * sign
    #                     tax_amount = invoice.amount_tax_signed
    #                     untaxed_amount_currency = invoice.amount_untaxed * sign
    #                     untaxed_amount = invoice.amount_untaxed_signed
    #                 invoice_payment_terms = invoice.invoice_payment_term_id._compute_terms(
    #                     date_ref=invoice.invoice_date or invoice.date or fields.Date.context_today(invoice),
    #                     currency=invoice.currency_id,
    #                     tax_amount_currency=tax_amount_currency,
    #                     tax_amount=tax_amount,
    #                     untaxed_amount_currency=untaxed_amount_currency,
    #                     untaxed_amount=untaxed_amount,
    #                     company=invoice.company_id,
    #                     # cash_rounding=invoice.invoice_cash_rounding_id,
    #                     sign=sign
    #                 )
    #                 for term in invoice_payment_terms:
    #                     key = frozendict({
    #                         'move_id': invoice.id,
    #                         'date_maturity': fields.Date.to_date(term.get('date')),
    #                         'discount_date': term.get('discount_date'),
    #                         'discount_percentage': term.get('discount_percentage'),
    #                     })
    #                     values = {
    #                         'balance': term['company_amount'],
    #                         'amount_currency': term['foreign_amount'],
    #                         'discount_amount_currency': term['discount_amount_currency'] or 0.0,
    #                         'discount_balance': term['discount_balance'] or 0.0,
    #                         'discount_date': term['discount_date'],
    #                         'discount_percentage': term['discount_percentage'],
    #                     }
    #                     if key not in invoice.needed_terms:
    #                         invoice.needed_terms[key] = values
    #                     else:
    #                         invoice.needed_terms[key]['balance'] += values['balance']
    #                         invoice.needed_terms[key]['amount_currency'] += values['amount_currency']
    #             else:
    #                 invoice.needed_terms[frozendict({
    #                     'move_id': invoice.id,
    #                     'date_maturity': fields.Date.to_date(invoice.invoice_date_due),
    #                     'discount_date': False,
    #                     'discount_percentage': 0
    #                 })] = {
    #                     'balance': invoice.amount_total_signed,
    #                     'amount_currency': invoice.amount_total_in_currency_signed,
    #                 }

class AccountMoveLineInherit(models.Model):
    _inherit = 'account.move.line'

    task_id = fields.Many2one('project.task')
    product_uom_id = fields.Many2one(
        comodel_name='uom.uom',
        string='Unit of Measure',
        compute='_compute_product_uom_id', store=True, readonly=False, precompute=True,
        domain=False,
        ondelete="restrict",
    )


class AccountTaxInherit(models.Model):
    _inherit = 'account.tax'

    journal_ids = fields.Many2many('account.journal')


class AccountAnalyticInherit(models.Model):
    _inherit = 'account.analytic.account'

    count = fields.Integer(string='Count')
    # count = fields.Integer(string='Count', compute="_compute_count")

    def name_get(self):
        result = []
        for partner in self:
            name = partner.name or ''
            result.append((partner.id, name))
        return result


    # def _compute_count(self):
    #     for rec in self:
    #         bank_journal_ids = self.env['account.journal'].search([('type', '=', 'bank')])
    #         outgoing_acc_ids = bank_journal_ids.outbound_payment_method_line_ids.mapped('payment_account_id')
    #         payment_outstanding_account = self.env.company.account_journal_payment_credit_account_id
    #         outgoing_account_ids = outgoing_acc_ids + payment_outstanding_account
    #         analytical_line_ids = self.env['account.analytic.line'].search_count(
    #             [('general_account_id', 'in', outgoing_account_ids.ids), ('account_id', '=', rec.id)])
    #
    #         rec.count = analytical_line_ids

    def action_view_payment(self):
        bank_journal_ids = self.env['account.journal'].search([('type', '=', 'bank')])
        outgoing_acc_ids = bank_journal_ids.outbound_payment_method_line_ids.mapped('payment_account_id')
        payment_outstanding_account = self.env.company.account_journal_payment_credit_account_id
        outgoing_account_ids = outgoing_acc_ids + payment_outstanding_account
        analytical_line_ids = self.env['account.analytic.line'].search([('general_account_id', 'in', outgoing_account_ids.ids), ('account_id', '=', self.id)])
        return{'name': 'Payments',
               'res_model': 'account.move.line',
               'type': 'ir.actions.act_window',
               'view_mode': 'tree,form',
               'context': {'create': 0, 'delete': 0},
               'domain': [('id', 'in', analytical_line_ids.move_line_id.ids)],
               'target': 'current',
               }


class SequenceMixin(models.AbstractModel):
    """Mechanism used to have an editable sequence number.

    Be careful of how you use this regarding the prefixes. More info in the
    docstring of _get_last_sequence.
    """

    _inherit = 'sequence.mixin'

    @api.constrains(lambda self: (self._sequence_field, self._sequence_date_field))
    def _constrains_date_sequence(self):
        # Make it possible to bypass the constraint to allow edition of already messed up documents.
        # /!\ Do not use this to completely disable the constraint as it will make this mixin unreliable.
        constraint_date = fields.Date.to_date(self.env['ir.config_parameter'].sudo().get_param(
            'sequence.mixin.constraint_start_date',
            '1970-01-01'
        ))
        for record in self:
            pass
            # if not record._must_check_constrains_date_sequence():
            #     continue
            # date = fields.Date.to_date(record[record._sequence_date_field])
            # sequence = record[record._sequence_field]
            # if (
            #         sequence
            #         and date
            #         and date > constraint_date
            #         and not record._sequence_matches_date()
            # ):
            #     raise ValidationError(_(
            #         "The %(date_field)s (%(date)s) doesn't match the sequence number of the related %(model)s (%(sequence)s)\n"
            #         "You will need to clear the %(model)s's %(sequence_field)s to proceed.\n"
            #         "In doing so, you might want to resequence your entries in order to maintain a continuous date-based sequence.",
            #         date=format_date(self.env, date),
            #         sequence=sequence,
            #         date_field=record._fields[record._sequence_date_field]._description_string(self.env),
            #         sequence_field=record._fields[record._sequence_field]._description_string(self.env),
            #         model=self.env['ir.model']._get(record._name).display_name,
            #     ))

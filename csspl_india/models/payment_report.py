from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, AccessError, MissingError


class PaymentReport(models.TransientModel):
    _name = 'payment.anal.report'
    _description = "Payment Report"
    _rec_name = 'date'

    payment_name = fields.Char('Name')
    payment_method_line_id = fields.Many2one('account.payment.method.line', string='Method')
    transfer_date = fields.Date('Transfer Date')
    partner_id = fields.Many2one('res.partner')
    journal_id = fields.Many2one('account.journal')
    analytics_plan_id = fields.Many2one('account.analytic.plan', string='Analytics Plan')
    analytics_account_id = fields.Many2one('account.analytic.account', string="Analytics Account")
    month = fields.Char('Month')
    date = fields.Date('Date')
    amount = fields.Monetary(currency_field="currency_id", readonly=1)
    currency_id = fields.Many2one('res.currency', )
    batch_payment_id = fields.Many2one('account.batch.payment')
    payment_id = fields.Many2one('account.payment')
    contigency = fields.Float()

    def fetch_data_query(self):
        user_id = self.env.user.id
        self.env.cr.execute("delete from payment_anal_report")
        outbound_query = """insert into payment_anal_report 
        (date,payment_name,payment_method_line_id,partner_id,transfer_date,month,analytics_plan_id,analytics_account_id,journal_id,amount,batch_payment_id,payment_id,contigency)
        select am.create_date,am.name,ap.payment_method_line_id,ap.partner_id,ap.transfer_date,ap.month,ap.analytics_plan_id,ap.analytics_account_id,
        am.journal_id,ap.amount,ap.batch_payment_id,ap.id,ap.contigency
        from account_payment as ap 
        join account_move am on ap.move_id = am.id 
        where ap.payment_type = 'outbound' and am.state = 'posted';  
        """
        outbound_morgify_query = self.env.cr.mogrify(outbound_query).decode(self.env.cr.connection.encoding)
        self._cr.execute(outbound_morgify_query)
        # inbound_query = """insert into payment_anal_report
        #         (date,payment_name,payment_method_line_id,partner_id,transfer_date,month,analytics_plan_id,analytics_account_id,journal_id,amount,batch_payment_id,payment_id)
        #         select am.create_date,am.name,ap.payment_method_line_id,ap.partner_id,ap.transfer_date,ap.month,ap.analytics_plan_id,ap.analytics_account_id,
        #         am.journal_id,-ap.amount,ap.batch_payment_id,ap.id
        #         from account_payment as ap
        #         join account_move am on ap.move_id = am.id
        #         where ap.payment_type = 'inbound' and am.state = 'posted' and am.reversed_entry_id is not null;
        #         """
        # inbound_morgify_query = self.env.cr.mogrify(inbound_query).decode(self.env.cr.connection.encoding)
        # self._cr.execute(inbound_morgify_query)
        return {
            'name': 'Payment Analytic Report',
            'type': 'ir.actions.act_window',
            'res_model': 'payment.anal.report',
            'view_mode': 'tree,pivot',
            'context': {'create': 0, 'delete': 0, 'edit': 0}
        }

    def action_open_payment(self):
        self.ensure_one()
        return {
            'res_model': "account.payment",
            'type': 'ir.actions.act_window',
            'views': [[self.env.ref('account.view_account_payment_form').id, "form"]],
            'res_id': self.payment_id.id,
        }

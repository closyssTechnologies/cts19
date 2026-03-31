from odoo import models, fields, api
import base64
from tempfile import TemporaryFile
import pandas as pd


class AccountDashboard(models.TransientModel):
    _name = 'account.dashboard.wiz'
    _description = "Account Dashboard to view sales, expense receivable and Outstanding"

    analytic_plan = fields.Many2one('account.analytic.plan')
    partner_id = fields.Many2one('res.partner')
    sales = fields.Float()
    received = fields.Float()
    outstanding = fields.Float()
    bills = fields.Float()
    payed = fields.Float()
    payable = fields.Float()
    date = fields.Date()
    partner_type = fields.Selection(related="partner_id.cust_partner_type")
    record_id = fields.Integer()
    model_name = fields.Char()

    def action_analytic_dashboard(self):
        self.env.cr.execute('delete from account_dashboard_wiz where create_uid = {}'.format(self.env.user.id))
        self.get_sales_query()
        self.get_expense_query()
        self.get_received_payments()
        return {
            'name': "Analytic Dashboard",
            'res_model': 'account.dashboard.wiz',
            'view_mode': 'list,pivot',
            'type': 'ir.actions.act_window',
            'domain': [('create_uid', '=', self.env.user.id)],
            'context': {'create': 0, 'delete': 0}
        }

    def get_sales_query(self):
        query = """insert into account_dashboard_wiz (date, partner_id, sales, outstanding, record_id, 
        model_name, create_uid) select al.date, al.partner_id, al.amount, al.amount, am.id , 'account.move', {} 
        from account_analytic_line as al
        join account_account as coa on al.general_account_id = coa.id and account_type = 'income'
        join account_move_line as aml on al.move_line_id = aml.id
        join account_move am on aml.move_id = am.id where am.move_type = 'out_invoice' and am.state = 'posted';
        ;""".format(self.env.user.id)
        self.env.cr.execute(query)

    def get_expense_query(self):
        query = """insert into account_dashboard_wiz (date, partner_id, payed, record_id, model_name, create_uid)
                        select am.date, pm.partner_id, pm.amount, pm.id, 'account.payment', {} from account_payment as pm
                        join account_move as am on pm.move_id = am.id
                        where pm.payment_type = 'outbound' and pm.analytics_plan_id is not null and am.state = 'posted';
                        """.format(self.env.user.id)
        self.env.cr.execute(query)
        query_2 = """insert into account_dashboard_wiz (date, partner_id, payed, record_id, model_name, create_uid)
        select al.date, al.partner_id, al.amount, am.id, 'account.move', {} from account_analytic_line as al
        join account_account as coa on al.general_account_id = coa.id and account_type = 'income'
        join account_move_line as aml on al.move_line_id = aml.id
        join account_move am on aml.move_id = am.id where am.move_type = 'out_refund' and am.state = 'posted';
        ;""".format(self.env.user.id)
        self.env.cr.execute(query_2)

    def get_received_payments(self):
        query = """insert into account_dashboard_wiz (date, partner_id, received, outstanding, record_id, model_name, create_uid)
                select am.date, pm.partner_id, pm.amount, pm.amount * -1, pm.id, 'account.payment', {} from account_payment as pm
                join account_move as am on pm.move_id = am.id
                where pm.payment_type = 'inbound' and pm.analytics_plan_id is not null and am.state = 'posted';""".format(self.env.user.id)
        self.env.cr.execute(query)

    def action_view_related_record(self):
        return {
            'name': 'Related Record',
            'res_model': self.model_name,
            'res_id': self.record_id,
            'view_mode': 'form',
            'context': {'create': 0, 'delete': 0},
            'type': 'ir.actions.act_window',
        }


class ImportInvoiceReceipt(models.TransientModel):
    _name = 'import.invoice.receipt'
    _description = "Class to import Invoice Receipt and reconcile it."

    file = fields.Binary()

    # Function to convert Excel file to Binary
    def convert_to_df(self):
        csv_data = self.file
        file_obj = TemporaryFile('wb+')
        csv_data = base64.decodebytes(csv_data)
        file_obj.write(csv_data)
        file_obj.seek(0)
        return pd.read_excel(file_obj).fillna(False)

    def search_invoice(self, invoice_no):
        invoice_id = self.env['account.move'].search([('move_type', '=', 'out_invoice'), ('name', '=', invoice_no)])
        if not invoice_id:
            return "Invoice is not found"
        return invoice_id

    def search_journal(self, journal_name):
        journal_id = self.env['account.journal'].search([('name', '=', journal_name)])
        if not journal_id:
            return "Journal Not found"
        return journal_id.id

    def validate_data(self, df):
        df['invoice_id'] = df['Invoice No'].apply(lambda x: self.search_invoice(x))
        df['journal_id'] = df['Journal'].apply(lambda x: self.search_journal(x))
        # df.style.apply(self.highlight_cols, axis=None)
        return df

    def print_excel(self):
        df = self.convert_to_df()
        df = self.validate_data(df)

        writer = pd.ExcelWriter('pandas_simple.xlsx', engine='xlsxwriter')
        df.to_excel(writer, sheet_name='Sheet1', index=False)
        writer.close()
        file = open("pandas_simple.xlsx", "rb")
        out = file.read()
        file.close()
        # self.download_payments_file = base64.b64encode(out)

        result = base64.b64encode(out)

        # get base url
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        attachment_obj = self.env['ir.attachment']
        # create attachment
        attachment_id = attachment_obj.create(
            {'name': "name.xlsx", 'datas': result})
        # prepare download url
        download_url = '/web/content/' + str(attachment_id.id) + '?download=true'
        # download
        return {
            "type": "ir.actions.act_url",
            "url": str(base_url) + str(download_url),
            "target": "current",
        }

    def import_invoice_receipt(self):
        df = self.convert_to_df()
        df = self.validate_data(df)
        # this code is for returning the excel filesss
        if len(df.loc[df['invoice_id'] == 'Invoice is not found']) > 0 or \
                len(df.loc[df['journal_id'] == 'Journal Not found']) > 0:
            return self.print_excel()
        data = df.to_dict('index')
        data = data.values()
        for rec in data:
            # customer = rec.get('Partner', False)
            invoice_no = rec.get('invoice_id', False)
            amount = float(rec.get('Amount', 0))
            payment_id = self.env['account.payment.register']
            journal_id = self.env['account.journal'].search([('name', '=', rec.get('Journal'))]).id
            date = rec.get('Date')
            fields_value = {
                'journal_id': journal_id,
                'payment_date': date,
                'payment_type': 'inbound',
                'amount': amount,
                'communication': invoice_no.name,
            }
            payment_id.sudo().with_context({'active_model': 'account.move',
                                            'active_ids': invoice_no.ids}).create(fields_value).action_create_payments()


class PaymentReport(models.TransientModel):
    _name = 'payment.report'
    _description = "Payment Report"

    journal_id = fields.Many2one('account.journal', string="Bank", readonly=1)
    move_id = fields.Many2one('account.move',  readonly=1)
    partner_id = fields.Many2one('res.partner',  readonly=1)
    company_currency_id = fields.Many2one('res.currency',  readonly=1)
    credit = fields.Monetary(currency_field="company_currency_id",  readonly=1)
    debit = fields.Monetary(currency_field="company_currency_id",  readonly=1)
    date = fields.Date( readonly=1)
    amount_in_currency = fields.Monetary(currency_field="currency_id",  readonly=1)
    currency_id = fields.Many2one('res.currency',  readonly=1)
    analytic_account_id = fields.Many2one('account.analytic.account')
    analytic_plan_id = fields.Many2one('account.analytic.plan')
    transfer_date = fields.Date('Transfer Date')
    month = fields.Char()
    payment_method_line_id = fields.Many2one('account.payment.method.line', string='Method')
    batch_payment_id = fields.Many2one('account.batch.payment')
    account_id = fields.Many2one("account.account")

    def action_run_report(self):
        user_id = self.env.user.id
        self.env.cr.execute("delete from payment_report where create_uid={}".format(user_id))
        bank_journal_ids = self.env['account.journal'].search([('type', '=', 'bank')])
        incoming_acc_ids = bank_journal_ids.inbound_payment_method_line_ids.mapped('payment_account_id')
        outgoing_acc_ids = bank_journal_ids.outbound_payment_method_line_ids.mapped('payment_account_id')
        payment_outstanding_account = self.env.company.account_journal_payment_credit_account_id
        receipt_outstanding_account = self.env.company.account_journal_payment_debit_account_id
        outgoing_account_ids = outgoing_acc_ids + payment_outstanding_account
        incoming_account_ids = incoming_acc_ids + receipt_outstanding_account
        outgoing_query = """insert into payment_report (move_id, partner_id, credit, debit, date, journal_id, currency_id,
        amount_in_currency, company_currency_id,analytic_account_id,analytic_plan_id,account_id,payment_method_line_id,batch_payment_id, create_uid,transfer_date,month)
        select aml.move_id, aml.partner_id, aml.credit, aml.debit, aml.date, aml.journal_id, aml.currency_id, 
        aml.amount_currency,aml.company_currency_id,anl.account_id,anl.plan_id,aml.account_id,ap.payment_method_line_id,ap.batch_payment_id, %(creator)s,
        (case 
        when (aml.payment_id IS NOT NULL) THEN ap.transfer_date
        when (aml.payment_id IS NULL) THEN am.date
        ELSE NULL END) as transfer_date,
        (case 
        when (aml.payment_id IS NOT NULL) THEN ap.month
        when (aml.payment_id IS NULL) THEN TO_CHAR(am.date,'Mon yyyy')
        ELSE NULL END) as month
        from account_move_line as aml
        left join account_analytic_line anl on aml.id = anl.move_line_id
        left join account_payment ap on aml.payment_id = ap.id
        join account_move am on aml.move_id = am.id
        where aml.account_id IN %(outstanding_account)s and aml.journal_id in %(journal_ids)s and 
        aml.parent_state = 'posted' and aml.statement_id is null and aml.statement_line_id is null;"""
        self.env.cr.execute(outgoing_query, {'outstanding_account': tuple(outgoing_account_ids.ids), 'journal_ids': tuple(bank_journal_ids.ids),
                                    'creator': user_id})
        # Incoming Query
        incoming_query = """insert into payment_report (move_id, partner_id, credit, debit, date, journal_id, currency_id,
                amount_in_currency, company_currency_id,analytic_account_id,analytic_plan_id,account_id,payment_method_line_id,batch_payment_id, create_uid,transfer_date,month)
                select aml.move_id, aml.partner_id, aml.credit, aml.debit, aml.date, aml.journal_id, aml.currency_id, 
                aml.amount_currency,aml.company_currency_id,anl.account_id,anl.plan_id,aml.account_id,ap.payment_method_line_id,ap.batch_payment_id, %(creator)s,
                (case 
                when (aml.payment_id IS NOT NULL) THEN ap.transfer_date
                when (aml.payment_id IS NULL) THEN am.date
                ELSE NULL END) as transfer_date,
                (case 
                when (aml.payment_id IS NOT NULL) THEN ap.month
                when (aml.payment_id IS NULL) THEN TO_CHAR(am.date,'Mon yyyy')
                ELSE NULL END) as month
                from account_move_line as aml
                left join account_analytic_line anl on aml.id = anl.move_line_id
                left join account_payment ap on aml.payment_id = ap.id
                join account_move am on aml.move_id = am.id
                where am.reversed_entry_id IS NOT NULL and aml.account_id IN %(incoming_account)s and aml.journal_id in %(journal_ids)s and 
                aml.parent_state = 'posted' and aml.statement_id is null and aml.statement_line_id is null;"""
        self.env.cr.execute(incoming_query, {'incoming_account': tuple(incoming_account_ids.ids),
                                             'journal_ids': tuple(bank_journal_ids.ids),
                                             'creator': user_id})
        return {
            'name': 'Payment Report',
            'type': 'ir.actions.act_window',
            'res_model': 'payment.report',
            'view_mode': 'tree,form,pivot',
            'domain': [('create_uid', '=', user_id)],
            'context': {'create': 0, 'delete': 0, 'edit': 0}
        }

    def action_open_reference(self):
        """ Open the form view of the move's reference document, if one exists, otherwise open form view of self
        """
        self.ensure_one()
        return {
            'res_model': "account.move",
            'type': 'ir.actions.act_window',
            'views': [[False, "form"]],
            'res_id': self.move_id.id,
        }

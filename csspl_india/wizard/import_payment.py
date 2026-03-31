import xlsxwriter

from odoo import api, fields, models, _
import logging
import csv
import io, base64
from tempfile import TemporaryFile
import pandas as pd
from odoo.exceptions import ValidationError
from datetime import datetime
import xlwt

_logger = logging.getLogger(__name__)


class ImportFailedContacts(models.TransientModel):
    _name = 'import.failed.contacts'
    _description = 'Import Failed Contacts'

    contact_name = fields.Char(string='Name')
    analytics_account = fields.Char(string='Analytics Account')
    bank_account = fields.Char(string='Bank Account')
    ifsc_code = fields.Char(string='IFSC Code')
    pay_method = fields.Char(string='Pay method')
    journal_id = fields.Char(string='Journal id')
    mail_by = fields.Char(string='Mail By')
    missing_data_id = fields.Many2one("import.payment", string="")


class ImportPaymentWizard(models.TransientModel):
    _name = "import.payment"
    _description = "Import Payment"

    import_type = fields.Selection([('batch_payment', 'Batch Payment'), ('update_utr', 'Update UTR')])
    load_file = fields.Binary("Load File")
    file_name = fields.Char()
    missing_data_ids = fields.One2many("import.failed.contacts", "missing_data_id", string="Missing Accounts")

    def download_report_missing(self):
        return self.env.ref('csspl_india.wizard_button_report_missing_xlsx').report_action(self)

    def validate_utr_data(self, data):
        row_data = data.to_dict()
        error = []
        payment_id = False
        if not row_data.get('Reference'):
            error.append('Reference is blank')
        if not row_data.get('UTR'):
            error.append('UTR is blank')
        if not row_data.get('Amount'):
            error.append('Amount Field is Blank')
        if not row_data.get('Account'):
            error.append('Account number is Blank')
        if not error:
            payment_id = self.env['account.payment'].search([('batch_payment_id', '=', row_data.get('Reference')),
                                                             ('partner_bank_id', '=', row_data.get('Account')),
                                                             ('amount', '=', row_data.get('Amount'))])
            if not payment_id:
                error.append('Combination not found')
            if payment_id and payment_id.filtered(lambda x: x.utr_no == row_data.get('UTR')):
                error.append("UTR Already set")
        return error and ("Error " + " ".join(error)) or ""

    def print_error_file(self, df):
        writer = pd.ExcelWriter('UTRImportFile.xlsx', engine='xlsxwriter')
        df.to_excel(writer, sheet_name='Sheet1', index=False)
        writer.close()
        file = open("UTRImportFile.xlsx", "rb")
        out = file.read()
        file.close()
        # self.download_payments_file = base64.b64encode(out)

        result = base64.b64encode(out)

        # get base url
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        attachment_obj = self.env['ir.attachment']
        # create attachment
        attachment_id = attachment_obj.create(
            {'name': f"{self.file_name.split('.')[0]}_error.xlsx", 'datas': result})
        # prepare download url
        download_url = '/web/content/' + str(attachment_id.id) + '?download=true'
        # download
        return {
            "type": "ir.actions.act_url",
            "url": str(base_url) + str(download_url),
            "target": "current",
        }

    def import_payment(self):
        if self.load_file and self.import_type == 'batch_payment':
            data = pd.read_excel(io.BytesIO(base64.b64decode(self.load_file)), dtype={'Recipient Bank Account': str})
            # df = pd.read_excel(self.load_file)
            _id = False
            vals_data = {}
            missing_data = []
            vals_list = []
            for index, row in data.iterrows():
                batch_journal_id = row['batch_journal_id'] if str(row['batch_journal_id']) != 'nan' else ''
                batch_type = str(row['batch_type']) if str(row['batch_type']) != 'nan' else ''
                analytics_plan_batch = row['analytics_plan_id']
                b_payment_method_id = row['payment_method_id'] if str(row['payment_method_id']) != 'nan' else ''
                follower_ids = str(row['follower_ids']).split(",") if str(row['follower_ids']) != 'nan' else ''
                payment = row['Payment Type'] if str(row['Payment Type']) != 'nan' else ''
                cust_name = row['Customer/Vendor']
                amount = row['Amount']
                payment_date = row['Date']
                journal = row['Journal']
                payment_method = row['Payment Method']
                check_no = row['check_no'] if str(row['check_no']) != 'nan' else ''
                check_date = row['check_date']
                sal_payment = str(row['Salary Payment']).upper()
                c_bookings = str(row['Conveyence Payment']).upper()
                analytics_plan = row['Analytics Plan']
                acc_analytic = row['Analytics Account']
                recip_bank_acc = str(row['Recipient Bank Account'])
                recip_bank_ifsc = row['bank_isfc']
                req_by = row['REQUEST BY']
                req_receive_date = row['REQUEST RECEIVED DATE']
                sup_name = row['SUP NAME']
                cust = row['CUSTOMER']
                bank = row['BANK']
                atm = row['ATM ID']
                mail_by = row['Mail By']
                # req_mail_id = row['Requester Mail id']
                css_local_branch = row['Local Branch'] if str(row['Local Branch']) != 'nan' else ''
                css_state = row['State'] if str(row['State']) != 'nan' else ''
                month = row['Month'] if str(row['Month']) != 'nan' else ''
                narration = row['Description'] if str(row['Description']) != 'nan' else ''
                customer_name = self.env["res.partner"].search([('name', '=', cust_name)], limit=1)
                analyt_plan = self.env["account.analytic.plan"].search([('name', '=', analytics_plan_batch)])
                req_by_name = self.env["res.partner"].search([('name', '=', req_by)], limit=1)
                customer = self.env["res.partner"].search([('name', '=', cust)], limit=1)
                recipient_bank_acc = self.env["res.partner.bank"].search([('partner_id', '=', cust_name)])
                b_journal_id = self.env["account.journal"].search([('name', '=', batch_journal_id)])
                journal_id = self.env["account.journal"].search([('name', '=', journal)])
                b_pay_method = self.env["account.payment.method.line"].search([('name', '=', b_payment_method_id), ('journal_id', '=', b_journal_id.id)], limit=1)
                pay_method = self.env["account.payment.method.line"].search([('name', '=', payment_method), ('journal_id', '=', journal_id.id)], limit=1)
                b_analyt_plan = self.env["account.analytic.plan"].search([('name', '=', analytics_plan)])
                analyt_acc_code = self.env["account.analytic.account"].search([('name', '=', acc_analytic)])
                # check_uniq_id = self.env["account.payment"].search([('unique_id', '=', uniq_id)])
                check_mail_by = self.env["res.users"].search([('name', '=', mail_by)])
                check_bank_acc = self.env["res.bank"].search([('name', '=', bank)])
                # check_recipient_bank_acc = self.env["res.partner.bank"].search([('acc_number', '=', recip_bank_acc)])
                check_recipient_bank_acc = self.env["res.partner.bank"].search(
                    [('partner_id', '=', customer_name.id), ('acc_number', '=', recip_bank_acc)])
                payment_for = row.get('payment_for', 'other')
                date_object = False
                if payment_date:
                    date_object = datetime.strptime(payment_date, '%d-%m-%Y')

                date_req = False
                if req_receive_date:
                    date_req = datetime.strptime(req_receive_date, '%d-%m-%Y')

                date_cheque = False
                if check_date and not check_date != 'nan':
                    date_cheque = datetime.strptime(check_date, '%d-%m-%Y')

                # Created batch payment first
                if batch_journal_id and batch_type and b_payment_method_id:
                    followers_lst = []
                    for follower in follower_ids:
                        followers = self.env['res.partner'].search([
                            ('name', '=', follower)]).id
                        followers_lst.append(followers)

                    vals_b = {
                        'batch_type': batch_type,
                        'journal_id': b_journal_id.id,
                        'analytics_plans_batch_id': analyt_plan.id,
                        # 'analytics_account_id': b_analyt_plan.id if b_analyt_plan else '',
                        'payment_method_id': b_pay_method.payment_method_id.id,
                    }

                    new_record2 = self.env['account.batch.payment'].sudo().create(vals_b)
                    new_record2.message_subscribe(followers_lst)

                vals_pay = {
                    'payment_type': payment,
                    'partner_type': 'supplier',
                    'partner_id': customer_name.id,
                    'amount': float(amount),
                    'date': date_object,
                    'journal_id': journal_id.id,
                    'payment_method_line_id': pay_method.id,
                    'cheque_number': check_no or '',
                    'cheque_date': date_cheque if date_cheque else False,
                    'payment_for': payment_for,
                    # 's_check': True if sal_payment == '1' else False,
                    # 'c_check': True if c_bookings == '1' else False,
                    'analytics_plan_id': b_analyt_plan.id or False,
                    'analytics_account_id': analyt_acc_code.id or False,
                    'partner_bank_id': check_recipient_bank_acc.id,
                    'request_by': req_by_name.id,
                    'request_received_date': date_req if date_req else False,
                    'sup_name': sup_name if sup_name else '',
                    'customer_ch': cust if cust else '',
                    'bank': bank if bank else '',
                    'atm_id': atm if atm else '',
                    'mail_by': check_mail_by.id,
                    # 'requester_mail_id': req_mail_id if req_mail_id else '',
                    'css_local_branch': css_local_branch if css_local_branch else '',
                    'css_state': css_state if css_state else '',
                    'month': month if month else '',
                    'narration': narration if narration else '',
                    'batch_payment_id': new_record2.id,
                    'source_doc': new_record2.name
                }
                new_record = self.env['account.payment'].sudo().create(vals_pay)

    def import_missing_data(self):
        if self.load_file and self.import_type == 'update_utr':
            data = pd.read_excel(io.BytesIO(base64.b64decode(self.load_file)), dtype={'Account': str, 'Reference': str, 'Amount': float})
            data['error'] = data.apply(lambda x: self.validate_utr_data(x), axis=1)
            if len(data[data['error'].str.contains('Error')]) > 0:
                return self.print_error_file(data)
            for index, row in data.iterrows():
                payment_id = self.env['account.payment'].search([('batch_payment_id', '=', row.get('Reference')),
                                                                 ('partner_bank_id', '=', row.get('Account')),
                                                                 ('amount', '=', row.get('Amount')),
                                                                 ('utr_no', '=', False)])
                payment_id[0].utr_no = row.get('UTR')
            notification = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': "Success",
                    'type': 'success',
                    'message': 'UTR Number uploaded Successfully',
                    'sticky': True,
                }
            }
            return notification
        elif self.load_file and self.import_type != 'update_utr':
            data = pd.read_excel(io.BytesIO(base64.b64decode(self.load_file)),dtype={'Recipient Bank Account': str})
            _id = False
            vals_data = {}
            missing_data = []
            vals_list = []
            for index, row in data.iterrows():
                batch_journal_id = row['batch_journal_id']
                batch_type = row['batch_type']
                analytics_plan = row['analytics_plan_id']
                b_payment_method_id = row['payment_method_id']
                follower_ids = str(row['follower_ids']).split(",")
                payment = row['Payment Type']
                cust_name = row['Customer/Vendor']
                amount = row['Amount']
                payment_date = row['Date']
                journal = row['Journal']
                payment_method = row['Payment Method']
                check_no = row['check_no']
                check_date = row['check_date']
                sal_payment = row['Salary Payment']
                c_bookings = row['Conveyence Payment']
                acc_analytic_plan = row['Analytics Plan']
                acc_analytic = row['Analytics Account']
                recip_bank_acc = str(row['Recipient Bank Account'])
                recip_bank_ifsc = row['bank_isfc']
                req_by = row['REQUEST BY']
                req_receive_date = row['REQUEST RECEIVED DATE']
                sup_name = row['SUP NAME']
                cust = row['CUSTOMER']
                bank = row['BANK']
                atm = row['ATM ID']
                mail_by = row['Mail By']
                # req_mail_id = row['Requester Mail id']
                month = row['Month'] if str(row['Month']) != 'nan' else ''
                customer_name = self.env["res.partner"].search([('name', '=', cust_name)])
                recipient_bank_acc = self.env["res.partner.bank"].search([('partner_id', '=', cust_name)])
                b_journal_id = self.env["account.journal"].search([('name', '=', batch_journal_id)])
                journal_id = self.env["account.journal"].search([('name', '=', journal)])
                b_pay_method = self.env["account.payment.method.line"].search([('name', '=', b_payment_method_id)], limit=1)
                pay_method = self.env["account.payment.method.line"].search([('name', '=', payment_method)], limit=1)
                # b_analyt_acc = self.env["account.analytic.account"].search([('name', '=', analytics_account)])
                analyt_acc_plan = self.env["account.analytic.plan"].search([('name', '=', acc_analytic_plan)])
                if not analyt_acc_plan:
                    raise ValidationError("Analytic Plan Doesn't Exist!!")
                analyt_acc_code = self.env["account.analytic.account"].search([('name', '=', acc_analytic)])
                # check_uniq_id = self.env["account.payment"].search([('unique_id', '=', uniq_id)])
                check_mail_by = self.env["res.users"].search([('name', '=', mail_by)])
                check_bank_acc = self.env["res.bank"].search([('name', '=', bank)])
                check_recipient_bank_acc = self.env["res.partner.bank"].search([('acc_number', '=', recip_bank_acc)])
                check_recipient_bank_ifsc = self.env["res.bank"].search([('bic', '=', recip_bank_ifsc)])
                payment_for = row.get('payment_for', 'other')
                if payment_for == 'salary' and not month:
                    raise ValidationError("For Salary Payment month is mandatory")
                # elif payment_for == 'salary' and month:
                #     if not self.env['payment.month'].search([('name', '=', month)]):
                #         raise ValidationError(f'Payment month {month} not found in the system, Kindly verify it.')
                if self.env["account.payment"].search([('analytics_account_id', '=', acc_analytic),
                                                       ('partner_id', '=', cust_name),
                                                       ('payment_for', '=', 'salary'),
                                                       ('partner_bank_id.acc_number', '=', recip_bank_acc),
                                                       ('month', '=', month), ('state', '!=', 'cancel'),
                                                       ('payment_type', '=', 'outbound'),
                                                       ('reversal_move_id', '=', [])]):
                    raise ValidationError(f"Payment for {cust_name}, {acc_analytic}, {recip_bank_acc} for {month} already Exists!! Please check in Vendor-> Payments")

                vals_data = (0, 0, {
                    'contact_name': cust_name if not customer_name else True,
                    'analytics_account': acc_analytic if not analyt_acc_code else True,
                    'journal_id': journal if not journal_id else True,
                    'pay_method': payment_method if not pay_method else True,
                    'mail_by': mail_by if not check_mail_by else True,
                    'bank_account': recip_bank_acc if not check_recipient_bank_acc else True,
                    'ifsc_code': recip_bank_ifsc if not check_recipient_bank_ifsc else True,
                })

                # all_true = all(value for value in vals_data[2].values())
                if any(value is not True for value in list(vals_data[2].values())):
                    missing_data.append(vals_data)
                vals_list.extend([cust_name if not customer_name else True,
                                  acc_analytic if not analyt_acc_code else True,
                                  journal if not journal_id else True,
                                  payment_method if not pay_method else True,
                                  mail_by if not check_mail_by else True,
                                  recip_bank_acc if not check_recipient_bank_acc else True,
                                  recip_bank_ifsc if not check_recipient_bank_ifsc else True])

            if any(value is not True for value in vals_list):
                _id = self.env['import.payment'].create({'load_file': self.load_file,
                                                         'missing_data_ids': missing_data})

                return {
                    'name': _("Import Payment"),
                    'view_mode': 'form',
                    'res_model': 'import.payment',
                    'res_id': _id.id if id else False,
                    'type': 'ir.actions.act_window',
                    'target': 'new',
                }
            else:
                self.import_payment()

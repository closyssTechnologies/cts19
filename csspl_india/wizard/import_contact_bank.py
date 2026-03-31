import base64
import io
import pandas as pd
from odoo import fields, models
from odoo.exceptions import ValidationError


class ContactCust(models.TransientModel):
    _name = "contact.cust"

    import_type = fields.Selection([('parent', 'Parent'), ('child', 'Child')], required=True)
    load_file = fields.Binary("load file", required=True)
    file_name = fields.Char()

    def print_error_file(self, df):

        writer = pd.ExcelWriter('ContactErrorFile.xlsx', engine='xlsxwriter')
        df.to_excel(writer, sheet_name='Sheet1', index=False)
        writer.close()
        file = open("ContactErrorFile.xlsx", "rb")
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

    def validate_data(self, df, data):
        row_data = data.to_dict()
        error = []
        if not row_data.get('name'):
            error.append("Name Missing")
        if not row_data.get('account_payable'):
            error.append('Account Payable Missing')
        if row_data.get('account_payable') and not self.env['account.account'].search([('name', '=', row_data.get('account_payable'))]):
            error.append('Incorrect Account Payable')
        if not row_data.get('acc_number'):
            error.append('Account number missing')
        if not row_data.get('bank_id'):
            error.append('Bank missing')
        if not row_data.get('ifsc_code'):
            error.append('IFSC missing')
        # if row_data.get('acc_number') and self.env['res.partner.bank'].search([('acc_number', 'ilike', row_data.get('acc_number'))]).exists():
        #     error.append("Account Number already Exist")
        if row_data.get('acc_number') and len(df[df['acc_number'] == row_data.get('acc_number')]) > 1:
            error.append("Duplicate Account number in File")
        if error:
            return "Error: " + "\n ".join(error)
        return ""

    def validate_child_data(self, data):
        row_data = data.to_dict()
        error = []
        parent_accc_num = row_data.get('parent_account_number')
        if not row_data.get('contact_name'):
            error.append("Contact Name Missing")
        if not parent_accc_num:
            error.append("Parent Account Number Missing")
        if parent_accc_num:
            acc_no = self.env['res.partner.bank'].search(
                [('acc_number', '=', str(parent_accc_num))])
            if not acc_no:
                error.append("Parent Account Number not found")
            if acc_no and len(acc_no) > 1:
                error.append("More than 1 record found for this account number")
            if acc_no and len(acc_no) == 1 and not acc_no.partner_id:
                error.append("Account holder not set for this Account Number")
        if error:
            return "Error: " + "\n ".join(error)
        return ""

    def prepare_child_contact_data(self, row):
        row_data = row.to_dict()
        return {
            'parent_id': self.env['res.partner.bank'].search([('acc_number', '=', str(row_data.get('parent_account_number')))]).partner_id.id,
            'name': row_data.get('contact_name'),
            'street': row_data.get('street', ""),
            'street2': row_data.get('street2', ""),
            'city': row_data.get('city', ""),
            'zip': row_data.get('zip', ""),
            'phone': row_data.get('phone', ""),
            'email': row_data.get('email', ""),
            'type': 'other',
        }

    def import_missing_contact(self):   
        if self.load_file:
            data = pd.read_excel(io.BytesIO(base64.b64decode(self.load_file)), dtype={'acc_number': str, 'parent_account_number': str}).fillna(False)
            if self.import_type == 'child':
                data['error'] = data.apply(lambda x: self.validate_child_data(x), axis=1)
                if len(data[data['error'].str.contains('Error')]) > 0:
                    return self.print_error_file(data)
                child_contact_data = data.apply(lambda x: self.prepare_child_contact_data(x), axis=1)
                self.env['res.partner'].sudo().create(child_contact_data.to_list())
                notification = {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': "Success",
                        'type': 'success',
                        'message': 'Child Contact Records Uploaded Successfully',
                        'sticky': True,
                    }
                }
                return notification
            data['error'] = data.apply(lambda x: self.validate_data(data, x), axis=1)
            # if data['error'].str.contains('Error'):
            if len(data[data['error'].str.contains('Error')]) > 0:
                return self.print_error_file(data)
            # if 'name' not in data.columns not in data.columns:
            #     raise ValidationError('Contact/Bank/Account or IFSC missing')

            for index, row in data.iterrows():
                account_payable = self.env['account.account'].search([('name', '=', row['account_payable'])])
                row_data = row.to_dict()
                if not row_data.get('name'):
                    raise ValidationError(f"Contact Name Missing, Kindly Verify the sheet.")
                if not account_payable:
                    raise ValidationError(f"Account Payable Account Missing For Contact {row_data.get('name')}")
                contact_import = {
                    'name': row_data.get('name') if not pd.isnull(row_data.get('name')) else '',
                    'property_account_payable_id': account_payable.id if not pd.isnull(row_data.get('account_payable')) else '',
                    'street': row_data.get('street') if not pd.isnull(row_data.get('street')) else '',
                    'street2': row_data.get('street2') if not pd.isnull(row_data.get('street2')) else '',
                    'city': row_data.get('city') if not pd.isnull(row_data.get('city')) else '',
                    'zip': row_data.get('zip') if not pd.isnull(row_data.get('zip')) else '',
                    'phone': row_data.get('phone') if not pd.isnull(row_data.get('phone')) else '',
                    'email': row_data.get('email') if not pd.isnull(row_data.get('email')) else '',
                }
                new_record = self.env['res.partner'].sudo().create(contact_import)
                cust_name = row['name']
                bank_names = row['bank_id']
                account_no = str(row['acc_number'])
                ifsc = row['ifsc_code']

                # if cust_name or account_no or bank_names or ifsc == None:
                #     raise ValidationError("Contact/Bank/Account or IFSC missing")
                if bank_names and account_no and ifsc:
                    bank = self.env['res.bank'].search([('name', '=', bank_names), ('bic', '=', ifsc)], limit=1).id
                    if not bank:
                        bank_create = self.env['res.bank'].create([{
                            'name': bank_names,
                            'bic': str(ifsc),
                        }]).id
                    else:
                        bank_create = bank
                    bank_acc_no = self.env['res.partner.bank'].search([('acc_number', '=', account_no)])
                    if not bank_acc_no:
                        bank_data = {
                            'partner_id': new_record.id,
                            'bank_id': bank_create,
                            'acc_number': account_no,
                        }
                        self.env['res.partner.bank'].create(bank_data)
            notification = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': "Success",
                    'type': 'success',
                    'message': 'Contact Imported Successfully',
                    'sticky': True,
                }
            }
            return notification


class IfscUpdate(models.TransientModel):
    _name = "ifsc.update"

    load_file_ic = fields.Binary("load file")

    def import_missing_ifsc(self):
        if self.load_file_ic:
            data = pd.read_excel(io.BytesIO(base64.b64decode(self.load_file_ic)), dtype={'acc_number': str})

            for index, row in data.iterrows():

                bank_names = row['bank_id']
                account_no = str(row['acc_number'])
                ifsc = row['ifsc_code']

                if bank_names and account_no and ifsc:
                    bank = self.env['res.bank'].search([('name', '=', bank_names), ('bic', '=', ifsc)], limit=1).id
                    if not bank:
                        bank_create = self.env['res.bank'].create([{
                            'name': bank_names,
                            'bic': ifsc,
                        }]).id
                    else:
                        bank_create = bank
                    bank_acc_no = self.env['res.partner.bank'].search([('acc_number', '=', account_no)])
                    if not bank_acc_no:
                        raise ValidationError(f"AccountNo not set{account_no}")
                    else:
                        bank_acc_no.write({'bank_id': bank_create})

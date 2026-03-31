from odoo import fields, models, api, _


class ReasonWiz(models.TransientModel):
    _name = 'reason.wiz'
    _description = 'Reason and Description Wizard'

    reason = fields.Text("Reject Reason")

    def save_data_to_reject_reason(self):
        payment_line = self.env['account.payment'].browse(self._context.get('active_id'))
        payment_line.write({'reason_text': self.reason})


class UpdateBankRef(models.TransientModel):
    _name = 'bank.ref'
    _description = 'Update Bank Reference Wizard'

    bank_ref = fields.Char("Bank Ref No")

    def save_data_to_bank_ref(self):
        bank_ref_search = self.env['account.batch.payment'].browse(self._context.get('active_id'))
        bank_ref_search.write({'ref_bank_no': self.bank_ref})
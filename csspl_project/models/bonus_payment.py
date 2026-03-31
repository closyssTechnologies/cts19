

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class PaymentForMaster(models.Model):
    _name = 'payment.for.master'
    _description = 'Payments For'

    name = fields.Char(string='Payments For')

    account_id = fields.Many2one('account.account', required=True,
                                 domain=[('account_type', 'in', ['asset_receivable', 'liability_payable'])])

    @api.constrains('name')
    def get_unique_name(self):
        for rec in self:
            name = self.env['payment.for.master'].search_count([('name', '=ilike', rec.name)])
            if name > 1:
                raise ValidationError(f"Please note {rec.name} has already been used.")


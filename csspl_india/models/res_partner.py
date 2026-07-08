from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    supplier_code = fields.Char(
        string="Supplier/Vendor Code",
        copy=False,
        readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)

        for partner in partners:
            if not partner.supplier_code:
                partner.supplier_code = self.env['ir.sequence'].next_by_code(
                    'res.partner.supplier.code'
                ) or '/'

        return partners
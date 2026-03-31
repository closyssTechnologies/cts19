from odoo.models import AbstractModel
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class InheritBaseModel(AbstractModel):
    _inherit = 'base'

    def unlink(self):
        model_name = self._name
        res = super().unlink()
        return res


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.constrains()
    def _partner_unique_name(self):
        for rec in self:
            partner = self.env['res.partner'].search_count([('name', '=ilike', rec.name)])
            if len(partner) > 1:
                raise ValidationError(f"Contact with the name {rec.name} is already been created.")





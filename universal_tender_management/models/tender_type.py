from odoo import models, fields

class TenderType(models.Model):
    _name = 'tender.type'
    _description = 'Tender Type'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

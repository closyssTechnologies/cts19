from odoo import models, fields

class TenderStage(models.Model):
    _name = 'tender.stage'
    _description = 'Tender Stage'
    _order = 'sequence'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    is_lost = fields.Boolean()
    is_contract_active = fields.Boolean()
    is_completed = fields.Boolean()

from odoo import fields, api, models


class StockPickingTypeInherit(models.Model):
    _inherit = 'stock.picking.type'

    is_outgoing = fields.Boolean()
    is_incoming = fields.Boolean()


class StockPickingInherit(models.Model):
    _inherit = 'stock.picking'

    is_outgoing = fields.Boolean()
    is_incoming = fields.Boolean()
    helpdesk_id = fields.Many2one('helpdesk.ticket')
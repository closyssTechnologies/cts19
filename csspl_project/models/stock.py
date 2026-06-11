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


class StockMoveInherit(models.Model):
    _inherit = 'stock.move'

    atm_id = fields.Many2one("atm_id.master", string="Atm ID")
    atm_ids = fields.Many2many("atm_id.master",string="Atm ID",)


class AtmId(models.Model):
    _name = "atm_id.master"
    _rec_name = "name"

    name = fields.Char("ATM ID")
    city = fields.Char("City")
    address = fields.Char("Address")
    state = fields.Char("State")
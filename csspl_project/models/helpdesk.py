from odoo import api, fields, models


class HelpdeskTicketInherit(models.Model):
    _inherit = 'helpdesk.ticket'

    count_outgoing_transfer = fields.Integer(compute="compute_count_of_outgoing")
    count_incoming_transfer = fields.Integer(compute="compute_count_of_incoming")
    requester_name = fields.Char(string='Requester Name', tracking=1)
    project_name = fields.Char(string='Project Name', tracking=1)
    receiver_name = fields.Char(string='Receiver Name', tracking=1)
    receiver_no = fields.Char(string='Receiver Contact No', tracking=1)
    type_id = fields.Many2one('helpdesk.type', string='Type', tracking=1)

    def action_create_outgoing_transfer(self):
        return {
            'name': "Product",
            'type': 'ir.actions.act_window',
            'res_model': 'stock.wizard',
            'view_mode': 'form',
            'context': {'default_helpdesk_id': self.id, 'default_picking': 'out'},
            'target': 'new'
        }

    def action_create_incoming_transfer(self):
        return {
            'name': "Product",
            'type': 'ir.actions.act_window',
            'res_model': 'stock.wizard',
            'view_mode': 'form',
            'context': {'default_helpdesk_id': self.id, 'default_picking': 'in'},
            'target': 'new'
        }

    def compute_count_of_outgoing(self):
        for rec in self:
            rec.count_outgoing_transfer = self.env['stock.picking'].search_count(
                [('helpdesk_id', '=', rec.id), ('is_outgoing', '=', True)])

    def compute_count_of_incoming(self):
        for rec in self:
            rec.count_incoming_transfer = self.env['stock.picking'].search_count(
                [('helpdesk_id', '=', rec.id), ('is_incoming', '=', True)])

    def action_view_outgoing_transfer(self):
        return {
            'name': 'Transfer Created',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('helpdesk_id', '=', self.id), ('is_outgoing', '=', True)],
            'target': 'current',
            'context': {'create': 0}
        }

    def action_view_incoming_transfer(self):
        return {
            'name': 'Transfer Created',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'view_type': 'list,form',
            'domain': [('helpdesk_id', '=', self.id), ('is_incoming', '=', True)],
            'target': 'current',
        }

class StockWizard(models.TransientModel):
    _name = "stock.wizard"
    _description = 'To Get product details'

    helpdesk_id = fields.Many2one('helpdesk.ticket')
    sale_id = fields.Many2one('sale.order')
    picking = fields.Selection([('in', 'IN'), ('out', 'Out')])
    product_ids = fields.Many2many('product.product',
                                   help="Product selected here will be created in Transfer. And please note service type product will not be reflected in Transfer as they are not stored")

    def create_picking(self):
        for rec in self:
            picking_out = self.env['stock.picking.type'].search([('is_outgoing', '=', True),
                                                                 ('company_id', '=', rec.helpdesk_id.company_id.id)],
                                                                limit=1)
            picking_in = self.env['stock.picking.type'].search([('is_incoming', '=', True),
                                                                ('company_id', '=', rec.helpdesk_id.company_id.id)],
                                                               limit=1)
            picking_type = picking_out if rec.picking == 'out' else picking_in
            move_lines = []
            for product in rec.product_ids:
                move_lines.append((0, 0, {
                    'product_id': product.id,
                    'name': product.name,
                    'product_uom': product.uom_id.id,
                    'product_uom_qty': 1,
                    'location_id': picking_type.default_location_src_id.id,
                    'location_dest_id': picking_type.default_location_dest_id.id,
                }))
            picking_vals = {
                'origin': rec.helpdesk_id.name or rec.helpdesk_id.display_name,
                'picking_type_id': picking_type.id,
                'location_id': picking_type.default_location_src_id.id,
                'location_dest_id': picking_type.default_location_dest_id.id,
                'helpdesk_id': rec.helpdesk_id.id if rec.helpdesk_id else False,
                # 'sale_order_id': rec.sale_id.id if rec.sale_id else False,
                'move_ids': move_lines,
                'is_outgoing': True if rec.picking == 'out' else False,
                'is_incoming': True if rec.picking == 'in' else False
            }
            res = self.env['stock.picking'].create(picking_vals)
            return {
                'name': 'Transfer Created',
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': res.id,
                'target': 'new',
            }


class HelpdeskTypeMaster(models.Model):
    _name = 'helpdesk.type'
    _description = "Helpdesk Ticket Type"

    name = fields.Char()







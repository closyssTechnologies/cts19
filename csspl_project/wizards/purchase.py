import datetime
from odoo import fields, api, models
from odoo.exceptions import ValidationError


class DispatchMaterial(models.TransientModel):
    _name = 'dispatch.material'
    _description = "Table to create Delivery Order from Project"

    product_id = fields.Many2one('product.product', readonly=True)
    pending_qty = fields.Float(readonly=True)
    to_dispatch = fields.Float()
    boq_line_id = fields.Many2one('boq.lines')
    project_id = fields.Many2one('project.project')

    @api.onchange('to_dispatch')
    def validate_quantity(self):
        for rec in self:
            if rec.to_dispatch < 0:
                raise ValidationError("Negative quantity not allowed")
            elif rec.to_dispatch > rec.pending_qty:
                raise ValidationError("You cannot deliver more than pending qty")

    def get_picking_type(self):
        picking_type = self.env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)
        if not picking_type:
            raise ValidationError("No Outgoing Picking Found.")
        return picking_type

    def get_from_location(self):
        warehouse_id = self.env['stock.warehouse'].search([], limit=1)
        if not warehouse_id:
            raise "No Warehouse found"
        return warehouse_id.lot_stock_id

    def get_to_location(self):
        to_location = self.env['stock.location'].search([('usage', '=', 'customer')], limit=1)
        if not to_location:
            raise ValidationError("Destination Location not found")
        return to_location

    def create_do(self):
        if self.filtered(lambda x: x.to_dispatch <= 0):
            raise ValidationError("No Materials found to deliver.")
        picking_type = self.get_picking_type()
        partner_id = self.boq_line_id.partner_id
        origin = f"{self.project_id.name}"
        from_location = self.get_from_location()
        to_location = self.get_to_location()
        picking_data = {
            'picking_type_id': picking_type.id, 'location_id': from_location.id, 'origin': origin,
            'move_type': 'one', 'partner_id': partner_id.id,
            'move_ids_without_package': [(0, 0, {"product_id": rec.product_id.id, 'name': rec.product_id.name,
                                                 'product_uom_qty': rec.to_dispatch, 'location_id': from_location.id,
                                                 'location_dest_id': to_location.id,'boq_line_id': rec.boq_line_id.id,
                                                 }) for rec in self]
        }
        picking_id = self.env['stock.picking'].create(picking_data)
        picking_id.action_confirm()


class TaskInvoices(models.TransientModel):
    _name = 'task.invoices'
    _description = "Transient model to enter quantity, amount and invoice product for Invoice creation"

    task_id = fields.Many2one('project.task', readonly=1)
    product_id = fields.Many2one('product.product', domain=[('detailed_type', '=', 'service')])
    task_amount = fields.Float(readonly=1)
    quantity = fields.Float()
    amount = fields.Float(string="Unit Price")
    amount_total = fields.Float(string="Total", readonly="1")

    @api.onchange('amount', 'quantity')
    def calculate_amount_total(self):
        if self.amount < 0:
            raise ValidationError("Unit Price cannot be negative")
        elif self.quantity < 0:
            raise ValidationError("Quantity cannot be negative")
        amount_total = self.quantity * self.amount
        if amount_total > self.task_amount:
            raise ValidationError("You cannot invoice more than task invoice")
        self.amount_total = amount_total

    def create_invoice(self):
        if self.filtered(lambda x: not x.product_id):
            raise ValidationError("Please select the Invoice product.")
        project_id = self.task_id.project_id
        invoice_data = {
            'partner_id': project_id.partner_id.id,
            'journal_id': project_id.invoice_branch.id,
            'move_type': 'out_invoice',
            'invoice_line_ids': [(0, 0, {'product_id': rec.product_id.id, 'quantity': rec.quantity, 'price_unit': rec.amount,
                                         'ref': project_id.name, 'task_id':  rec.task_id.id}) for rec in self]
        }
        self.env['account.move'].create(invoice_data)


class BOQMaterialsWiz(models.Model):
    _name = 'boq.materials.wiz'
    _description = "Class to Show Materials required in Project and Task"

    project_id = fields.Many2one('project.project')
    task_id = fields.Many2many('project.task', domain="[('project_id', '=', project_id)]")
    boq_line_id = fields.Many2one('boq.lines')
    product_id = fields.Many2one('product.product')
    uom_id = fields.Many2one('uom.uom', related="product_id.uom_id")
    demand_qty = fields.Float()
    quantity = fields.Float()
    material_ids = fields.One2many('boq.materials.wiz', 'parent_id', auto_join=True)
    parent_id = fields.Many2one('boq.materials.wiz')
    purchase_order = fields.Many2one('purchase.order')
    description = fields.Char(string="Description")
    price_unit = fields.Float()

    @api.onchange('project_id')
    def fetch_materials(self):
        self.task_id = False
        self.material_ids = False
        if self.project_id:
            boq_line = self.project_id.boq_line_ids
            if boq_line:
                self.material_ids = False
            for rec in boq_line:
                self.material_ids.create({'task_id': [(4, rec.task_id.id)], 'project_id': rec.task_id.project_id.id,
                                          'product_id': rec.product_id.id, 'parent_id': self.id,
                                          'demand_qty': rec.required_qty, 'boq_line_id': rec.id,
                                          'price_unit': rec.product_id.standard_price,
                                          'description': rec.product_id.name})

    @api.onchange('task_id')
    def filter_material(self):
        self.material_ids = False
        if self.task_id and self.project_id:
            boq_line = self.task_id.boq_line_ids
            if boq_line:
                self.material_ids = False
            for rec in boq_line:
                self.material_ids.create({'task_id': [(4, rec.task_id.id)], 'product_id': rec.product_id.id,
                                          'demand_qty': rec.required_qty, 'boq_line_id': rec._origin.id,
                                          'parent_id': self.id,
                                          'price_unit': rec.product_id.standard_price,
                                          'description': rec.product_id.name})
        elif self.project_id:
            self.fetch_materials()

    def action_add_material(self):
        for rec in self.material_ids.filtered(lambda x: x.quantity > 0):
            purchase_order_line = self.purchase_order.order_line.create({'product_id': rec.product_id.id, 'task_id': rec.task_id.id,
                                                                         'boq_line_id': rec.boq_line_id.id,
                                                                         'product_qty': rec.quantity,
                                                                         'name': getattr(rec, 'description', rec.product_id.name),
                                                                         'product_uom': rec.product_id.uom_po_id.id,
                                                                         'analytic_distribution': {rec.task_id.project_id.analytic_account_id.id: 100},
                                                                         'order_id': self.purchase_order.id,
                                                                         'price_unit': rec.price_unit,
                                                                 })

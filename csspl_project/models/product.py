from odoo import fields, models, api


class ProductTemplateInherit(models.Model):
    _inherit = 'product.template'
    _rec_names_search = ['name', 'service_code', 'default_code']

    order_type_product = fields.Selection([('civil', 'Civil'), ('electrical', 'Electrical'), ('plumbing', 'Plumbing'),
                                           ('fire_sprinkler', 'Fire Sprinkler'), ('structural', 'Structural')], tracking=True)
    order_type_product_id = fields.Many2one('work.order.type')
    kit_ids = fields.One2many('product.kit', 'product_templ_id', auto_join=True)

    name = fields.Char('Name', index='trigram', required=True, translate=True, tracking=True)
    # type = fields.Selection(
    #     [('consu', 'Consumable'),
    #      ('service', 'Service')],
    #     compute='_compute_type', store=True, readonly=False, precompute=True, tracking=True)
    list_price = fields.Float(
        'Sales Price', default=1.0,
        digits='Product Price',
        help="Price at which the product is sold to customers.", tracking=True
    )
    standard_price = fields.Float(
        'Cost', compute='_compute_standard_price',
        inverse='_set_standard_price', search='_search_standard_price',
        digits='Product Price', groups="base.group_user",
        help="""In Standard Price & AVCO: value of the product (automatically computed in AVCO).
            In FIFO: value of the next unit that will leave the stock (automatically computed).
            Used to value the product when the purchase cost is not known (e.g. inventory adjustment).
            Used to compute margins on sale orders.""", tracking=True)

    uom_name = fields.Char(string='Unit of Measure Name', related='uom_id.name', readonly=True, tracking=True)
    # purchase_hsn = fields.Many2one('hsn.code',string='Purchase HSN', domain="[('type', '=', 'p')]",
    #                                tracking=True)
    # sale_hsn = fields.Many2one('hsn.code',string='Sales HSN', domain="[('type', '=', 's')]", tracking=True)


    @api.onchange('detailed_type')
    def clear_order_type_product_field(self):
        if self.detailed_type != 'service':
            self.order_type_product = False
            self.clear_kit_data()

    @api.onchange('order_type_product')
    def clear_kit_data(self):
        if not self.order_type_product:
            self.kit_ids.unlink()


class ProductKit(models.Model):
    _name = 'product.kit'
    _description = "Class to store all the kit"

    product_templ_id = fields.Many2one('product.template')
    product_id = fields.Many2one('product.product', required=1, domain="[('type', '=', 'consu')]")
    uom_id = fields.Many2one('uom.uom', related="product_id.uom_id", store=True)
    quantity = fields.Float()


class UOMConversion(models.Model):
    _name = 'uom.conversion'
    _description = "Table to convert UOM Quantity"

    from_uom = fields.Many2one('uom.uom')
    to_uom = fields.Many2one('uom.uom')
    formula = fields.Char()


class StockMovesInherit(models.Model):
    _inherit = 'stock.move'

    boq_line_id = fields.Many2one('boq.lines')
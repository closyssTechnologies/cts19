from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
from datetime import datetime


class ApprovalCategoryInherit(models.Model):
    _inherit = 'approval.category'

    approval_type = fields.Selection(selection_add=[('approve_payment', 'Approve Payment')])
    analytic = fields.Selection([('required', 'Required'), ('optional', 'Optional'), ('no', 'None')], string="Analytic",
                                default="optional", required=True)
    bank_account = fields.Selection([('required', 'Required'), ('optional', 'Optional'), ('no', 'None')], string="Bank Account",
                                    default="no", required=True)


class ApprovalRequestInherit(models.Model):
    _inherit = 'approval.request'

    analytical_account_id = fields.Many2one(comodel_name='account.analytic.account', string='Analytical Account', )
    analytic = fields.Selection(related='category_id.analytic')
    is_payment_created = fields.Boolean(default=False) # check box to just hide a button i.e create payment
    model_name = fields.Char()
    res_id = fields.Many2oneReference(model_field= 'model_name')
    bank_account = fields.Many2one('res.partner.bank', string="Bank Account",
                                   domain="[('partner_id', '=', partner_id)]")
    bank_account_selection = fields.Selection(related='category_id.bank_account')

    # over rided the confirm button and added a function to show message in channel
    def action_confirm(self):
        res = super(ApprovalRequestInherit, self).action_confirm()
        recipient_links = [user_id.user_id.partner_id.id for user_id in self.approver_ids]
        record = self.env.ref('csspl_project.project_update_channel')
        record.message_post(body=f"Approval request {self._get_html_link(self.name)} has been submitted. Kindly approved it",
                            message_type='comment', subtype_xmlid='mail.mt_comment',
                            partner_ids=recipient_links)
        return res

    # over rided the approve button and added a function to show message in channel
    def action_approve(self):
        res = super(ApprovalRequestInherit, self).action_approve()
        record = self.env.ref('csspl_project.project_update_channel')
        record.message_post(body=f"Approval request {self._get_html_link(self.name)} approved",
                            message_type='comment', subtype_xmlid='mail.mt_comment',
                            partner_ids= [self.request_owner_id.partner_id.id])
        return res

    # Action caused by Button click (Create Payment)
    def create_payment(self):
        if self.category_id.approval_type == 'approve_payment':
            if self.env['account.payment'].search([('approval_request', '=', self.id)]).exists():
                raise ValidationError('Payment already created against this approval.')
            else:
                payment_id = self.env['account.payment'].create(({'ref': self.reference, 'amount': self.amount,
                            'analytics_plan_id': self.analytical_account_id.plan_id.id,
                            'analytics_account_id': self.analytical_account_id.id,
                            'approval_request': self.id,
                            'partner_id': self.partner_id.id,
                            'payment_type': 'outbound',
                            'request_by': self.request_owner_id.partner_id.id,
                            'request_received_date': self.date,
                            'partner_bank_id': self.bank_account.id,
                            'destination_account_id': self.partner_id.property_account_payable_id.id,
                            }))
                self.is_payment_created = True
                # channel message variable created to show message in mail.channel #
                channel_message = self.env.ref('csspl_project.project_payments_channel')
                channel_message.message_post(body=f'Payment created for project {payment_id._get_html_link(self.analytical_account_id.name)}. Kindly verify and post it ',
                message_type='comment', subtype_xmlid='mail.mt_comment')
                self.message_post(body=('Payment Created'))
        elif self.category_id.approval_type == 'ticket_payment' and self.request_status == 'approved':
            if self.env['account.payment'].search([('approval_request', '=', self.id)]).exists():
                raise ValidationError('Payment already created against this approval.')
            else:
                month = datetime.now().strftime("%b")  # for month in short form
                year = datetime.now().year  # for short number of year ("%y")
                months = str(month) + "-" + str(year)
                data = {
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'approval_request': self.id,
                    'analytics_account_id': self.analytical_account_id.id,
                    'partner_id': self.partner_id.id,
                    'amount': self.amount,
                    'date': datetime.now(),
                    'ref': self.helpdesk_id.name,
                    'css_state': self.helpdesk_id.state_id.name,
                    'month': months, }
                self.env['account.payment'].create(data)

    # function for action to view Payment details created w.r.t. approval
    def view_payment(self):
        pay_id = self.env['account.payment'].search([('approval_request', '=', self.id)])
        if not pay_id:
            raise ValidationError('No Payment is created against this approval.')
        else:
            return {
                'name': 'Payments',
                'res_model': 'account.payment',
                'res_id': pay_id.id,
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'context': {'create': 0, 'delete': 0},
                'domain': [('approval_request', '=', self.id)]
            }


class ProjectInherit(models.Model):
    _inherit = 'project.project'

    boq_line_ids = fields.One2many('boq.lines', 'project_id')
    invoice_branch = fields.Many2one('account.journal', domain="[('type', '=', 'sale')]", tracking=True)
    delivery_count = fields.Integer(compute="compute_delivery_count")
    purchase_line_count = fields.Integer(compute="compute_purchase_line_count")
    project_invoice_count = fields.Integer(readonly=1)
    project_value = fields.Float(compute="compute_project_value", store=True)
    tax_amount = fields.Float(readonly=True)
    price_total = fields.Float(readonly=True)
    rfq_value = fields.Float(compute="compute_purchase_values", store=True)
    purchase_value = fields.Float(readonly=1)
    bill_amount = fields.Float(compute='compute_amount_from_analytic_lines')
    invoice_amount = fields.Float(readonly=1)
    payment_amount = fields.Float(readonly=1)
    price_list_id = fields.Many2one('product.pricelist', tracking=True)
    tax_ids = fields.Many2many('account.tax', string="Taxes")
    work_order_amt = fields.Float()
    payment_approval_count = fields.Integer(compute='_compute_payment_approval_count', string="Payment Count")
    payment_count = fields.Integer(compute='_compute_payment_count')
    bill_count = fields.Integer(compute='_compute_account_move_count', string="Payment Counts")
    margin = fields.Float(compute="compute_project_margin", store=True)
    old_invoice_amt = fields.Float(tracking=True)
    old_payment_amt = fields.Float(tracking=True)
    billing_type = fields.Selection([('month', 'Monthly'), ('otb', "One Time Billing")], string="Billing Type")

    # @api.model_create_multi
    # def create(self, vals_list):
    #     res = super().create(vals_list)
    #     self.analytic_account_id = False
    #     return res

    # def write(self, vals):
    #     # create the AA for project still allowing timesheet
    #     res = super().create(vals)
    #
    #     return res

    @api.depends('invoice_amount', 'payment_amount', 'old_invoice_amt', 'old_payment_amt')
    def compute_project_margin(self):
        for rec in self:
            rec.margin = (rec.invoice_amount + rec.old_invoice_amt) - (rec.payment_amount + rec.old_payment_amt)

    # Computing Bill Amount, Invoice Amount and Payment Amount from Analytic Items using Analytical Account
    def compute_amount_from_analytic_lines(self):
        for rec in self:
            rec.bill_amount, rec.invoice_amount, rec.payment_amount = 0, 0, 0
            if rec.account_id:
                analytic_items = self.env['account.analytic.line'].sudo().search([('account_id', '=', rec.account_id.id)])
                rec.bill_amount = sum(analytic_items.filtered(lambda x: x.category == 'vendor_bill').move_line_id.move_id.mapped('amount_total_signed'))
                rec.invoice_amount = sum(analytic_items.filtered(lambda x: x.category == 'invoice').move_line_id.move_id.mapped('amount_total_signed'))
                rec.payment_amount = sum(analytic_items.filtered(lambda x: x.general_account_id.account_type == 'liability_payable'
                                                                 and x.move_line_id.payment_id and x.move_line_id.parent_state == 'posted').move_line_id.mapped('debit')) \
                                     - sum(analytic_items.filtered(lambda x: x.general_account_id.account_type == 'liability_payable'and
                                                                             x.move_line_id.parent_state == 'posted' and x.move_line_id.payment_id).move_line_id.mapped('credit'))

    # Total no of payments approval already made through
    def _compute_payment_approval_count(self):
        for rec in self:
            total_payment = self.env['approval.request'].search([('res_id', '=', rec.id)]).ids
            rec.payment_approval_count = len(total_payment)

    # Function to count number of delivery orders
    def compute_delivery_count(self):
        for rec in self:
            rec.delivery_count = len(rec.boq_line_ids.stock_move_ids.picking_id)

    # Function to count number of Purchase Order line
    def compute_purchase_line_count(self):
        for rec in self:
            rec.purchase_line_count = len(rec.boq_line_ids.purchase_line_id)

    # Function to  calculate project value
    @api.depends('task_ids', 'task_ids.price_total', 'task_ids.tax_amount')
    def compute_project_value(self):
        for rec in self:
            # rec.project_value = sum(rec.task_ids.mapped('untaxed_amt'))
            rec.tax_amount = sum(rec.task_ids.mapped('tax_amount'))
            rec.price_total = sum(rec.task_ids.mapped('price_total'))

    # Function to calculate purchase value
    @api.depends('boq_line_ids.rfq_value', 'boq_line_ids.purchase_value', 'boq_line_ids.bill_amount')
    def compute_purchase_values(self):
        for rec in self:
            rec.rfq_value = sum(rec.boq_line_ids.mapped('rfq_value'))
            rec.purchase_value = sum(rec.boq_line_ids.mapped('purchase_value'))

    # Function to set partner on all the related Tasks
    @api.onchange('partner_id')
    def set_partner_in_tasks(self):
        partner = self.partner_id
        if self.project_invoice_count > 0 or self.delivery_count > 0:
            raise ValidationError('You cannot change the customer once the invoice or delivery order has been created.')
        if partner:
            self.task_ids.partner_id = partner.id
            self.price_list_id = getattr(partner.property_product_pricelist, 'id', False)
            # self.set_price_list()

    @api.onchange('tax_ids')
    def set_tax_on_tasks(self):
        self._origin.task_ids.tax_ids = False
        if self.tax_ids:
            self._origin.task_ids.tax_ids = [(4, _id) for _id in self.tax_ids._origin.ids]

    # This function is used to display all the delivery orders related to the project
    def action_view_deliveries(self):
        return {
            'name': 'Transfers',
            'res_model': 'stock.picking',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'context': {'create': 0, 'delete': 0},
            'domain': [('id', 'in', self.boq_line_ids.stock_move_ids.picking_id.ids)]
        }

    # This function is used to display all the purchase.order.lines related to the project
    def action_view_purchase_lines(self):
        return {
            'name': 'Purchase Lines',
            'res_model': 'purchase.order.line',
            'type': 'ir.actions.act_window',
            'view_mode': 'list',
            'context': {'create': 0, 'delete': 0},
            'domain': [('id', 'in', self.boq_line_ids.purchase_line_id.ids)]
        }

    # This function is used to display all the Invoices related to the project
    def action_view_invoices(self):
        analytic_lines = self.env['account.analytic.line'].sudo().search([('account_id', '=', self.account_id.id), ('category', '=', 'invoice')])
        invoices = set([rec.move_line_id.move_id.id for rec in analytic_lines])
        return {
            'name': 'Invoices',
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'context': {'create': 0, 'delete': 0},
            'domain': [('id', 'in', list(invoices))]
        }

    # Action cause by Button(Create payment)
    def action_create_payment_approval(self):
        return {
            'name': "Create Payment",
            'type': 'ir.actions.act_window',
            'res_model': 'approval.request',
            'view_mode': 'form,list',
            'context': {'default_request_owner_id': self.user_id.id,
                        'default_date': datetime.now().strftime('%Y-%m-%d'),
                        'default_analytical_account_id': self.account_id.id,
                        'default_res_id': self.id,
                        'default_model_name': 'project.project',
                        'default_name': 'New'
                        },
            'target': 'new',
        }

    # Action for Smart button(payments)
    def action_view_payment_approval(self):
        return {
            'name': 'Payments',
            'res_model': 'approval.request',
            'type': 'ir.actions.act_window',
            'view_mode': 'list,form',
            'context': {'create': 0, 'delete': 0},
            'domain': [('res_id', '=', self.id)]
        }

    def action_view_tasks(self):
        res = super().action_view_tasks()
        res.update({'view_mode': 'list,kanban,form,calendar,pivot,graph,activity', 'context': {'create': 0}})
        return res

    # smart button made from account payment
    def action_view_payments(self):
        analytic_items = self.env['account.analytic.line'].search([('account_id', '=', self.account_id.id), ('category', '=', 'other')])
        payments = analytic_items.filtered(lambda ai: ai.general_account_id.account_type == 'liability_payable' and ai.move_line_id.payment_id)
        return{'name': 'Payments',
               'res_model': 'account.payment',
               'type': 'ir.actions.act_window',
               'view_mode': 'list,form',
               'context': {'create': 0, 'delete': 0},
               'domain': [('id', 'in', payments.move_line_id.mapped('payment_id').ids)],
               'target': 'current',
        }

    def _compute_payment_count(self):
        for rec in self:
            analytic_items = self.env['account.analytic.line'].search(
                [('account_id', '=', rec.account_id.id), ('category', '=', 'other')])
            payments = analytic_items.filtered(lambda ai: ai.general_account_id.account_type == 'liability_payable' and ai.move_line_id.payment_id)
            rec.payment_count = len(payments.move_line_id.mapped('move_id'))

    def action_view_bills(self):
        analytic_lines = self.env['account.analytic.line'].search([('account_id', '=', self.account_id.id), ('category', '=', 'vendor_bill')])
        return{'name': 'Bills',
               'res_model': 'account.move',
               'type': 'ir.actions.act_window',
               'view_mode': 'list,form',
               'context': {'create': 0, 'delete': 0},
               'target': 'current',
               'domain': [('id', 'in', analytic_lines.move_line_id.move_id.ids)]
               }

    def _compute_account_move_count(self):
        for rec in self:
            rec.bill_count = len(self.env['account.analytic.line'].search([('account_id', '=', self.account_id.id),
                                                                           ('category', '=', 'vendor_bill')]).move_line_id.mapped('move_id'))
            rec.project_invoice_count = len(self.env['account.analytic.line'].search([('account_id', '=', self.account_id.id),
                                                                                      ('category', '=', 'invoice')]).move_line_id.mapped('move_id'))


class WorkOrderType(models.Model):
    _name = 'work.order.type'
    _description = 'To display data in project_task'

    name = fields.Char()


class ProjectTaskInherit(models.Model):
    _inherit = 'project.task'

    work_order_type_id = fields.Many2one('work.order.type')
    product_id = fields.Many2one('product.product',
                                 domain=[('detailed_type', '=', 'service')],
                                 tracking=True)
    uom_id = fields.Many2one('uom.uom', related="product_id.uom_id", store=True)
    service_code = fields.Char(tracking=True)
    work_order_type = fields.Selection([('civil', 'Civil'), ('electrical', 'Electrical'), ('plumbing', 'Plumbing'),
                                        ('fire_sprinkler', 'Fire Sprinkler'), ('structural', 'Structural')],
                                       tracking=True)
    boq_line_ids = fields.One2many('boq.lines', 'task_id')
    invoice_product = fields.Many2one('product.product', readonly=False)
    invoice_lines = fields.One2many('account.move.line', 'task_id', auto_join=True)
    invoice_amount = fields.Float(readonly=1)
    quantity = fields.Float()
    price_unit = fields.Float()
    untaxed_amt = fields.Float()
    rfq_value = fields.Float(compute="compute_purchase_values", store=True)
    purchase_value = fields.Float(readonly=1)
    bill_amount = fields.Float(readonly=1)
    price_list_id = fields.Many2one('product.pricelist', compute="get_price_list")
    tax_ids = fields.Many2many('account.tax', tracking=True, string="Taxes")
    tax_amount = fields.Float()
    price_total = fields.Float()

    @api.depends('project_id.price_list_id')
    def get_price_list(self):
        for rec in self:
            rec.price_list_id = getattr(rec.project_id.price_list_id, 'id', False)
            # rec.price_unit = rec.get_product_price()

    @api.depends('boq_line_ids.rfq_value', 'boq_line_ids.purchase_value', 'boq_line_ids.bill_amount')
    def compute_purchase_values(self):
        for rec in self:
            rec.rfq_value = sum(rec.boq_line_ids.mapped('rfq_value'))
            rec.purchase_value = sum(rec.boq_line_ids.mapped('purchase_value'))
            rec.bill_amount = sum(rec.boq_line_ids.mapped('bill_amount'))

    @api.onchange('quantity', 'price_unit')
    def calculate_amount_total(self):
        if self.price_unit < 0:
            raise ValidationError("Unit Price cannot be negative")
        elif self.quantity < 0:
            raise ValidationError("Quantity cannot be negative")
        self.untaxed_amt = self.quantity * self.price_unit
        # for boq_line in self.boq_line_ids:
        #     boq_line.required_qty = self.calculate_quantity(boq_line.uom_id)

    def calculate_quantity(self, to_uom):
        uom_conversion = self.env['uom.conversion'].search(
            [('from_uom', '=', self.uom_id.id), ('to_uom', '=', to_uom.id)])
        if not uom_conversion:
            return self.quantity
        return eval(uom_conversion[0].formula.replace("value", str(self.quantity)))

    def get_product_price(self):
        price_list = self.price_list_id
        if price_list and self.product_id:
            price_unit = price_list._get_product_price(self.product_id, self.quantity or 1.0)
            return price_unit
        return self.product_id.list_price

    @api.onchange('product_id')
    def set_task_name(self):
        self.name = ""
        if self.product_id and self.boq_line_ids.purchase_line_id:
            raise ValidationError(
                "You cannot change the product as purchase order has been generated against the below materials.")
        if self.product_id:
            self.name = self.product_id.name
            self.service_code = self.product_id.default_code
            self.price_unit = self.get_product_price()
            self.boq_line_ids = [(0, 0, {'product_id': rec.product_id.id,
                                         'required_qty': rec.quantity,
                                         'kit_qty': rec.quantity})
                                 for rec in self.product_id.kit_ids]
        else:
            self.boq_line_ids = False

    # @api.depends('quantity', 'price_unit', 'tax_ids', 'project_id.tax_ids')
    # def _compute_amount(self):
    #     """
    #     Compute the amounts of the SO line.
    #     """
    #     for line in self:
    #         tax_results = self.env['account.tax']._compute_taxes([line._convert_to_tax_base_line_dict()])
    #         totals = list(tax_results['totals'].values())[0]
    #         amount_untaxed = totals['amount_untaxed']
    #         amount_tax = totals['amount_tax']
    #         line.update({
    #             'untaxed_amt': amount_untaxed,
    #             'tax_amount': amount_tax,
    #             'price_total': amount_untaxed + amount_tax,
    #         })

    def _convert_to_tax_base_line_dict(self):
        """ Convert the current record to a dictionary in order to use the generic taxes computation method
        defined on account.tax.

        :return: A python dictionary.
        """
        self.ensure_one()
        return self.env['account.tax']._convert_to_tax_base_line_dict(
            self,
            partner=self.project_id.partner_id,
            currency=self.project_id.currency_id,
            product=self.product_id,
            taxes=self.tax_ids,
            price_unit=self.price_unit,
            quantity=self.quantity,
            price_subtotal=self.untaxed_amt,
        )


class BOQLines(models.Model):
    _name = "boq.lines"
    _description = "Materials needed for a project"
    _rec_name = 'product_id'

    _sql_constraints = [
        ('boq_unique_lines', 'unique(product_id, company_id, task_id)', 'You cannot add 2 product for same task.'),
    ]

    partner_id = fields.Many2one('res.partner', related="project_id.partner_id")
    product_id = fields.Many2one('product.product', domain="[('type', '=', 'consu')]")
    uom_id = fields.Many2one('uom.uom', related="product_id.uom_id", store=True)
    kit_qty = fields.Float()
    required_qty = fields.Float()
    rfq_qty = fields.Float(compute="compute_purchase_details", store=True)
    incoming_qty = fields.Float()
    purchased_qty = fields.Float()
    in_progress_delivery = fields.Float(string="In-Progress", help="In Progress Delivery",
                                        compute="compute_transfer_qty", store=True)
    delivered_qty = fields.Float(string="Delivered", help="Quantities which have been delivered at client's location",
                                 readonly=1)
    task_id = fields.Many2one('project.task')
    project_id = fields.Many2one('project.project', store=True, related="task_id.project_id")
    company_id = fields.Many2one('res.company', related="task_id.company_id", store=True)
    rfq_value = fields.Float(readonly="1")
    purchase_value = fields.Float(readonly="1")
    purchase_line_id = fields.One2many('purchase.order.line', 'boq_line_id', auto_join=True)
    line_readonly = fields.Boolean(compute="compute_readonly_prop")
    bill_amount = fields.Float(compute='compute_bill_amount', store=True)
    stock_move_ids = fields.One2many('stock.move', 'boq_line_id', auto_join=True)
    add_product = fields.Boolean(compute="check_product_in_kit")
    remove_product = fields.Boolean(compute="check_product_in_kit")

    def check_product_in_kit(self):
        for rec in self:
            if rec.task_id.product_id.kit_ids.filtered(lambda x: x.product_id.id == rec.product_id.id):
                rec.remove_product = True
                rec.add_product = False
            else:
                rec.add_product = True
                rec.remove_product = False

    @api.onchange('required_qty')
    def validate_required_qty(self):
        if self.required_qty < 0:
            raise ValidationError("Negative quantity not allowed")

    def compute_readonly_prop(self):
        for rec in self:
            if any((rec.rfq_qty, rec.incoming_qty, rec.purchased_qty, rec.in_progress_delivery, rec.delivered_qty)):
                rec.line_readonly = True
            else:
                rec.line_readonly = False

    @api.depends('purchase_line_id.invoice_lines.parent_state', 'purchase_line_id.invoice_lines.price_subtotal')
    def compute_bill_amount(self):
        for rec in self:
            rec.bill_amount = sum(rec.purchase_line_id.invoice_lines.mapped('price_subtotal'))

    @api.depends('purchase_line_id.order_id.state', 'purchase_line_id.product_qty', 'purchase_line_id.qty_received',
                 'purchase_line_id.price_subtotal')
    def compute_purchase_details(self):
        for rec in self:
            rec.rfq_qty = sum(
                rec.purchase_line_id.filtered(lambda x: x.state in ('draft', 'sent')).mapped('product_qty')) or 0
            rec.incoming_qty = sum(
                rec.purchase_line_id.move_ids.filtered(lambda x: x.state not in ('done', 'draft', 'cancel')).mapped(
                    'product_uom_qty')) or 0
            rec.purchased_qty = sum(
                rec.purchase_line_id.filtered(lambda x: x.state in ('done', 'purchase')).mapped('qty_received')) or 0
            rec.rfq_value = sum(
                rec.purchase_line_id.filtered(lambda x: x.state in ('draft', 'sent')).mapped('price_subtotal')) or 0
            rec.purchase_value = sum(
                rec.purchase_line_id.filtered(lambda x: x.state not in ('draft', 'sent', 'cancel')).mapped(
                    'price_subtotal')) or 0

    @api.depends('stock_move_ids.state', 'stock_move_ids.quantity', 'stock_move_ids.product_uom_qty')
    def compute_transfer_qty(self):
        for rec in self:
            rec.in_progress_delivery = sum(
                rec.stock_move_ids.filtered(lambda x: x.state not in ('done', 'cancel')).mapped('product_uom_qty'))
            rec.delivered_qty = sum(rec.stock_move_ids.filtered(lambda x: x.state == 'done').mapped('quantity'))

    def action_add(self):
        self.task_id.product_id.kit_ids = [(0, 0, {'product_id': self.product_id.id, 'quantity': self.required_qty})]

    def action_remove(self):
        kit_id = self.task_id.product_id.kit_ids.filtered(lambda x: x.product_id.id == self.product_id.id)
        self.task_id.product_id.kit_ids = [(2, kit_id.id)]

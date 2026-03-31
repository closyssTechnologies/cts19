from odoo import fields, api, models
from odoo.exceptions import ValidationError


class PurchaseOrderInherit(models.Model):
    _inherit = 'purchase.order'

    analytic_distribution = fields.Many2one('account.analytic.account', 'Analytic Distribution',
                                            required=True)

    def action_view_project_materials(self):
        return {
            'name': 'Select Project Materials',
            'type': 'ir.actions.act_window',
            'res_model': 'boq.materials.wiz',
            'view_mode': 'form',
            'target': 'new',
            'context': {'create': False, 'default_purchase_order': self.id}
        }

    @api.onchange('analytic_distribution')
    def validate_analytic_distribution(self):
        if self.order_line:
            for rec in self.order_line:
                rec.analytic_distribution = {self.analytic_distribution.id: 100}


class PurchaseOrderLineInherit(models.Model):
    _inherit = 'purchase.order.line'

    task_id = fields.Many2one('project.task')
    boq_line_id = fields.Many2one('boq.lines')
    # journal_relate_id = fields.Many2one('account.journal', related='order_id.l10n_in_journal_id')

    @api.onchange('task_id', 'product_id')
    def validate_task(self):
        self.analytic_distribution = {self.order_id.analytic_distribution.id: 100}
        if self.task_id and self.product_id:
            boq_line_id = self.task_id.boq_line_ids.filtered(lambda x: self.product_id == x.product_id)
            if not boq_line_id:
                raise ValidationError(f"Product {self.product_id.name} is not present in the Task Materials.")
            self.boq_line_id = boq_line_id.id
            self.analytic_distribution = {self.task_id.project_id.analytic_account_id.id: 100}


class DeletedRecords(models.Model):
    _name = 'deleted.records'
    _description = "All the deleted records will be store in this table"

    name = fields.Char(readonly=True)
    user_id = fields.Many2one('res.users', readonly=True)
    model_id = fields.Many2one('ir.model', readonly=True)

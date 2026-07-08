from odoo import fields, api, models
from odoo.exceptions import ValidationError


class PurchaseOrderInherit(models.Model):
    _inherit = 'purchase.order'

    analytic_distribution = fields.Many2one(
        'account.analytic.account',
        string='Analytic Distribution',
        required=True
    )

    def action_view_project_materials(self):
        return {
            'name': 'Select Project Materials',
            'type': 'ir.actions.act_window',
            'res_model': 'boq.materials.wiz',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'create': False,
                'default_purchase_order': self.id
            }
        }

    @api.onchange('analytic_distribution')
    def validate_analytic_distribution(self):
        for order in self:
            for line in order.order_line:
                if order.analytic_distribution:
                    line.analytic_distribution = {
                        order.analytic_distribution.id: 100
                    }
                else:
                    line.analytic_distribution = False


class PurchaseOrderLineInherit(models.Model):
    _inherit = 'purchase.order.line'

    task_id = fields.Many2one('project.task')
    boq_line_id = fields.Many2one('boq.lines')

    @api.onchange('task_id', 'product_id')
    def validate_task(self):
        for line in self:
            if line.product_id and not line.order_id.analytic_distribution:
                raise ValidationError(
                    "Please select Analytic Distribution first before adding product lines."
                )

            if line.order_id.analytic_distribution:
                line.analytic_distribution = {
                    line.order_id.analytic_distribution.id: 100
                }

            if line.task_id and line.product_id:
                boq_line_id = line.task_id.boq_line_ids.filtered(
                    lambda x: line.product_id == x.product_id
                )

                if not boq_line_id:
                    raise ValidationError(
                        f"Product {line.product_id.name} is not present in the Task Materials."
                    )

                line.boq_line_id = boq_line_id.id

                if line.task_id.project_id.analytic_account_id:
                    line.analytic_distribution = {
                        line.task_id.project_id.analytic_account_id.id: 100
                    }


class DeletedRecords(models.Model):
    _name = 'deleted.records'
    _description = "All the deleted records will be store in this table"

    name = fields.Char(readonly=True)
    user_id = fields.Many2one('res.users', readonly=True)
    model_id = fields.Many2one('ir.model', readonly=True)
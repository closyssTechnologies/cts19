# from odoo import models, fields, api
#
# class PurchaseCancelWizard(models.TransientModel):
#     _name = 'purchase.cancel.wizard'
#
#     reason = fields.Text(string="Reason", required=True)
#
#     @api.model_create_multi
#     def create(self, vals_list):
#         records = super().create(vals_list)
#         for record in records:
#             record._do_cancel()
#         return records
#
#
#     def _do_cancel(self):
#         active_ids = self.env.context.get('active_ids', [])
#         print(f"_do_cancel called, active_ids: {active_ids}, reason: {self.reason}")
#         if not active_ids or not self.reason:
#             print("SKIPPING - no active_ids or reason")
#             return
#         pos = self.env['purchase.order'].browse(active_ids)
#         for po in pos:
#             po.write({'cancel_reason': self.reason})
#         pos.with_context(from_cancel_wizard=True).button_cancel()
#

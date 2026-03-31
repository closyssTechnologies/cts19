from odoo import api, fields, models,_
from odoo.exceptions import UserError
from lxml import etree
import json

class SendChecker(models.TransientModel):
    _name = "send.checker"

    checker_id = fields.Many2one('res.users',"User")
    #
    # @api.model
    # def get_view(self, view_id=None, view_type='form', **options):
    #     res = super(SendChecker, self).get_view(view_id, view_type, **options)
    #     res_model = self.env.context.get('active_model')
    #
    #     # if res_model == 'account.move':
    #     #     user_ids = self.env.ref('csspl_india.group_account_checker').users.ids
    #     # elif res_model == 'account.payment':
    #     #     user_ids = self.env.ref('csspl_india.group_payments_checker').users.ids
    #     # else:
    #     #     user_ids = self.env.ref('csspl_india.group_purchase_checker').users.ids
    #
    #     if view_type == 'form':
    #         doc = etree.XML(res['arch'])
    #         for node in doc.xpath("//field[@name='checker_id']"):
    #             node.set('domain', f"{[('id','in',user_ids)]}")
    #             # modifiers = json.loads(node.get("modifiers"))
    #             # modifiers['domain'] = f"{[('id','in',user_ids)]}"
    #             # node.set("modifiers", json.dumps(modifiers))
    #         res['arch'] = etree.tostring(doc)
    #     return res

    def send_for_checking(self):
        res_model = self.env.context.get('active_model')

        res_id = self.env.context.get('active_id')
        record = self.env[res_model].sudo().search([('id','=',res_id)])
        record.to_check = True
        record.checker_id = self.checker_id.id

        self.env['mail.activity'].sudo().create({
            'res_model_id': self.env['ir.model'].sudo().search([('model','=',res_model)]).id,
            'res_id': res_id,
            'user_id': self.checker_id.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': "Request to check "+str(record.name),
            'note': "Request to check "+str(record.name),
        })

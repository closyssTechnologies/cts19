from odoo import models, fields, api, _
from odoo.api import ondelete
from odoo.exceptions import ValidationError

class TenderMaster(models.Model):
    _name = 'tender.master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Tender Master'

    name = fields.Char("Tender Title", tracking=True)
    tender_number = fields.Char(string="Tender number", default=lambda self: _('New'),tracking=True, copy=False)
    reference = fields.Char("Tender Reference",  tracking=True)
    partner_id = fields.Many2one('res.partner', string="Client", required=True, tracking=True)
    tender_type_id = fields.Many2one('tender.type', tracking=True)
    source = fields.Char(tracking=True)
    estimated_value = fields.Monetary(tracking=True)
    submission_due_date = fields.Date(tracking=True)
    contract_duration = fields.Char(tracking=True)
    owner_id = fields.Many2one('res.users', default=lambda self: self.env.user,tracking=True)
    stage_id = fields.Many2one(
        'tender.stage',group_expand='_group_expand_stage_id',
        default=lambda self: self.env.ref(
            'universal_tender_management.stage_identified'
        ),tracking=True
    )
    is_completed = fields.Boolean(related="stage_id.is_completed")
    is_lost = fields.Boolean(related="stage_id.is_lost")
    # Contract
    contract_number = fields.Char(tracking=True)
    contract_start_date = fields.Date(tracking=True)
    contract_end_date = fields.Date(tracking=True)
    project_id = fields.Many2one('project.project', copy=False, tracking=True)

    # Finance
    final_payment_received = fields.Boolean(tracking=True)
    bg_ids = fields.One2many('tender.bg', 'tender_id')
    emd_ids = fields.One2many('emd.master', 'tender_emd_id')
    currency_id = fields.Many2one('res.currency',default=lambda self: self.env.company.currency_id)

    @api.model_create_multi
    def create(self, vals_list):
        """Creating sequence"""
        for vals in vals_list:
            if not vals.get('tender_number') or vals['tender_number'] == _('New'):
                vals['tender_number'] = self.env['ir.sequence'].next_by_code(
                    'tender.master') or _('New')
        return super().create(vals_list)

    @api.onchange('contract_start_date', 'contract_end_date')
    def check_valid_date(self):
        for rec in self:
            if rec.contract_start_date and rec.contract_end_date:
                if rec.contract_start_date > rec.contract_end_date:
                    raise ValidationError("Please enter Start Date and End Date properly as Start Date cannot be greater then your End Date")

    @api.onchange('stage_id')
    def _onchange_stage(self):
        if self.stage_id.is_lost:
            self.emd_status = 'returned'

        if self.stage_id.is_contract_active and not self.project_id:
            self.project_id = self.env['project.project'].create({
                'name': self.name,
                'partner_id': self.partner_id.id
            })

    def action_reset_draft(self):
        for rec in self:
            tender_stage = self.env['tender.stage'].search([('name', 'ilike', 'Tender Identified')], limit=1)
            if not tender_stage:
                raise ValidationError("Stage 'Tender Identified' is not configured.")
            rec.stage_id =tender_stage.id
            rec.message_post(body="Tender has been set back as Tender Identified")

    def action_mark_completed(self):
        complete_stage = self.env['tender.stage'].search([('is_completed', '=', True)], limit=1)
        if not complete_stage:
            raise ValidationError("Completed stage is not configured.")
        for rec in self:
            # if rec.bg_ids.filtered(lambda b: b.status != 'released'):
            #     raise ValidationError("All BGs must be released.")
            if not rec.final_payment_received:
                raise ValidationError("Final payment not received.")
            rec.stage_id = complete_stage.id
            rec.message_post(body=f"{rec.name} has been completed successfully.")

    def action_mark_lost(self):
        lost_stage = self.env['tender.stage'].search([('is_lost', '=', True)], limit=1)
        if not lost_stage:
            raise ValidationError("Lost stage is not configured.")
        for rec in self:
            rec.stage_id = lost_stage.id
            rec.message_post(body=f"{rec.name} has been mark as lost.")

    @api.model
    def _group_expand_stage_id(self, stages, domain, order):
        return self.env['tender.stage'].search([], order=order)

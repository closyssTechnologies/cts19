from odoo import models, fields


class TenderBG(models.Model):
    _name = 'tender.bg'
    _description = 'Tender Bank Guarantee'

    tender_id = fields.Many2one('tender.master', ondelete='cascade')
    purpose = fields.Selection([('bid', 'Bid Security'), ('performance', 'Performance'),
                                ('advance', 'Advance'), ('retention', 'Retention'),
                                ('earnest_money', "Earnest Money Deposit (EMD)")], required=True)
    amount = fields.Monetary(required=True)
    bank_name = fields.Char()
    bg_number = fields.Char()
    start_date = fields.Date()
    expiry_date = fields.Date()
    claim_end_date = fields.Date()
    status = fields.Selection([('required', 'Required'), ('submitted', 'Submitted'), ('active', 'Active'),
                               ('released', 'Released'), ('invoked', 'Invoked')], default='required')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)


class emdmaster(models.Model):
    _name = 'emd.master'
    _description = 'EMD'

    tender_emd_id = fields.Many2one('tender.master', ondelete='cascade')
    emd_required = fields.Boolean()
    emd_amount = fields.Monetary()
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    emd_status = fields.Selection([
        ('not_submitted', 'Not Submitted'),
        ('submitted', 'Submitted'),
        ('returned', 'Returned'),
        ('forfeited', 'Forfeited'),
        ('adjusted', 'Adjusted in BG')
    ], default='not_submitted')
    emd_type = fields.Selection([('dd', 'DD'), ('rtgs', 'RTGS'), ('neft', 'NEFT'), ('bg', 'BG'),
                                 ('surety_bond', "Surety Bond"), ('credit_card', "Credit Card"),
                                 ('internet', "Internet Banking")])
    emd_attachment = fields.Many2many('ir.attachment')
    bank_name = fields.Char()
    submitted_date = fields.Date()
    expiry_date = fields.Date()
    emd_purpose = fields.Selection([('bid', 'Bid Security'), ('performance', 'Performance'),
                                ('advance', 'Advance'), ('retention', 'Retention'),
                                ('earnest_money', "Earnest Money Deposit (EMD)"),
                                ('tender_fees', "Tender Fees/Processing Fees"),
                                ('surety_bond', "Surety Bond"), ('bank_guarantee', "Bank Guarantee")])

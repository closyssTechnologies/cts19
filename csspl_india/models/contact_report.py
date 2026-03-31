from odoo import api, fields, models
from odoo.exceptions import ValidationError

import io
import base64
import xlsxwriter


class ContactTrailReport(models.TransientModel):
    _name = "contact.report"
    _description = "Generate Contact Report dynamic date wise"

    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    company_ids = fields.Many2many('res.company', string="Company", relation="company_ids",
                                   domain=lambda self: [('id', 'in', self.env.user.company_ids.ids)])
    file = fields.Binary("Download File")
    filename = fields.Char("File Name")
    account_type = fields.Selection([('debtor', 'Debtors'), ('creditor', 'Creditors')])
    chart_account_id = fields.Many2many('account.account',
                                        domain="[('account_type', 'in', ('asset_receivable', 'liability_payable'))]", )

    @api.onchange('account_type', 'company_ids')
    def _get_chart_account_id(self):
        if self.account_type == 'debtor':
            receivable = self.env['account.account'].search([('account_type', '=', 'asset_receivable'),
                                                             ('active', '=', False),
                                                             ('company_ids', 'in', self.company_ids.ids)])
            self.chart_account_id = [(6, 0, receivable.ids)]
        elif self.account_type == 'creditor':
            payable = self.env['account.account'].search([('account_type', '=', 'liability_payable'),
                                                          ('active', '=', False),
                                                          ('company_ids', 'in', self.company_ids.ids)])
            self.chart_account_id = [(6, 0, payable.ids)]

    def action_report_of_contact(self):
        if not self.account_type:
            raise ValidationError('Please Select the Account Type')
        if not self.chart_account_id:
            raise ValidationError('No Accounts Found. Please select account type again.')
        if not (self.start_date and self.end_date and self.company_ids):
            raise ValidationError('Please fill the detail properly')
        if self.start_date > self.end_date:
            raise ValidationError('Please select the date properly. Start Date cannot be greater than end Date')
        file_data = io.BytesIO()
        workbook = xlsxwriter.Workbook(file_data, {'in_memory': True})

        def generate_sheet(sheet_name, comp_ids):

            sheet = workbook.add_worksheet(sheet_name)

            bold = workbook.add_format({'bold': True})
            money = workbook.add_format({'num_format': '#,##0.00'})

            start = self.start_date.strftime('%d-%b-%Y')
            end = self.end_date.strftime('%d-%b-%Y')

            headers = [
                "Partner Name",
                "Initial Balance",
                f"Debit ({start} to {end})",
                f"Credit ({start} to {end})",
                "End Balance"
            ]

            for col, h in enumerate(headers):
                sheet.write(0, col, h, bold)

            query = """
                SELECT
                    COALESCE(p.id, i.partner_id, r.partner_id) AS partner_id,
                    COALESCE(parent.name || ' / ' || p.name, p.name) AS partner_name,

                
                    (COALESCE(i.initial_debit, 0) - COALESCE(i.initial_credit, 0)) AS initial_balance,
                
                    COALESCE(r.range_debit, 0) AS range_debit,
                    COALESCE(r.range_credit, 0) AS range_credit,
                
                    (
                        (COALESCE(i.initial_debit, 0) + COALESCE(r.range_debit, 0))
                        -
                        (COALESCE(i.initial_credit, 0) + COALESCE(r.range_credit, 0))
                    ) AS end_balance
                
                FROM res_partner p
                    LEFT JOIN res_partner parent ON parent.id = p.parent_id
                    LEFT JOIN (
                        SELECT
                            aml.partner_id,
                            SUM(aml.debit) AS initial_debit,
                            SUM(aml.credit) AS initial_credit
                        FROM account_move_line aml
                        WHERE aml.company_id IN %(company_id)s
                          AND aml.date < %(start_date)s
                          AND aml.account_id IN %(chart_account_id)s
                          AND aml.parent_state = 'posted'
                        GROUP BY aml.partner_id
                    ) i ON i.partner_id = p.id
                    LEFT JOIN (
                        SELECT
                            aml.partner_id,
                            SUM(aml.debit) AS range_debit,
                            SUM(aml.credit) AS range_credit
                        FROM account_move_line aml
                        WHERE aml.company_id IN %(company_id)s
                          AND aml.date >= %(start_date)s
                          AND aml.date <= %(end_date)s
                          AND aml.account_id IN %(chart_account_id)s
                          AND aml.parent_state = 'posted'
                        GROUP BY aml.partner_id
                    ) r ON r.partner_id = p.id

                WHERE p.id IN (
                    SELECT DISTINCT partner_id
                    FROM account_move_line aml
                    WHERE aml.company_id IN %(company_id)s
                      AND aml.account_id IN %(chart_account_id)s
                      AND aml.parent_state = 'posted'
                )
                ORDER BY p.name;

            """
            params = {'company_id': tuple(comp_ids),
                      'start_date': self.start_date,
                      'end_date': self.end_date,
                      'chart_account_id': tuple(self.chart_account_id.ids)}
            self.env.cr.execute(query, params)
            rows = self.env.cr.dictfetchall()
            row_no = 1

            for rec in rows:
                sheet.write(row_no, 0, rec['partner_name'])
                # sheet.write(row_no, 1, rec['parent_name'] or '')
                sheet.write(row_no, 1, rec['initial_balance'], money)
                sheet.write(row_no, 2, rec['range_debit'], money)
                sheet.write(row_no, 3, rec['range_credit'], money)
                sheet.write(row_no, 4, rec['end_balance'], money)

                row_no += 1

        generate_sheet("Consolidated", self.company_ids.ids)
        for company in self.company_ids:
            generate_sheet(company.name, [company.id])

        workbook.close()
        file_data.seek(0)

        # Save to wizard
        self.file = base64.b64encode(file_data.getvalue())
        self.filename = "Contact_Report.xlsx"
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self.id}?model=contact.report&field=file&filename_field=filename&download=true",
            "target": "self",
        }

import datetime
import math
import re

from odoo.exceptions import ValidationError
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

from odoo import models
import json


class CustomBankFormat(models.AbstractModel):
    _name = 'report.csspl_india.payment_lines_report'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, lines):
        bold_one = workbook.add_format({'font_size': 12, 'align': 'vcenter', 'bg_color': '#b7b7b7'})
        title_date_format = workbook.add_format(
            {'num_format': 'd-mm-yyyy'})
        sheet = workbook.add_worksheet('TransactionPayeeDetails')
        sheet.set_column(0, 0, 20)
        sheet.set_column(0, 1, 25)
        sheet.set_column(0, 2, 25)
        sheet.set_column(0, 3, 25)
        sheet.set_column(0, 4, 25)
        sheet.set_column(0, 5, 25)
        sheet.set_column(0, 6, 25)
        sheet.set_column(0, 7, 25)
        sheet.set_column(0, 8, 25)
        sheet.set_column(0, 9, 25)
        sheet.set_column(0, 10, 25)
        sheet.set_column(0, 11, 25)
        sheet.set_column(0, 12, 25)
        sheet.set_column(0, 13, 25)
        sheet.set_column(0, 14, 25)
        sheet.set_column(0, 15, 25)
        sheet.set_column(0, 16, 25)
        sheet.set_column(0, 17, 25)
        sheet.set_column(0, 18, 25)
        sheet.set_column(0, 19, 25)

        # # **************************************************
        # sheet.write(0, 0, 'TRANSACTION TYPE')
        # sheet.write(0, 1, 'AMOUNT')
        # sheet.write(0, 2, 'DATE')
        # sheet.write(0, 3, 'BENEFICIARY NAME')
        # sheet.write(0, 4, 'BENEFICIARY ACCOUNT NO')
        # sheet.write(0, 5, '')
        # sheet.write(0, 6, 'REMARKS')
        # sheet.write(0, 7, 'DEBIT ACCOUNT NO')
        # sheet.write(0, 8, '')
        # sheet.write(0, 9, 'BENEFICIARY IFSC')
        # sheet.write(0, 10, 'LENTH OF IFSC')
        #
        row = 0
        col = 0
        # # For Detailed Tds Report and Summary

        pay_method = ""
        for line in lines.payment_ids:
                if not line.partner_bank_id.bank_id.bic:
                    raise ValidationError('Bank not set in partner')
                if not line.batch_payment_id.journal_id.bank_id.bic:
                    raise ValidationError('Bank not set in Journal')
                if line.batch_payment_id.journal_id.bank_id.bic[0:4] == line.partner_bank_id.bank_id.bic[0:4]:
                    pay_method = "I"
                elif line.amount > 200000:
                    pay_method = "R"
                else:
                    pay_method = "N"

                sheet.write(row, col, str(pay_method))
                sheet.write(row, col + 1, str(line.amount) or ' ')
                sheet.write(row, col + 2, line.date, title_date_format)
                sheet.write(row, col + 3, re.sub(r"[-\d]+", "", line.partner_id.name))
                sheet.write(row, col + 4, line.partner_bank_id.acc_number or ' ')
                sheet.write(row, col + 5, '')
                sheet.write(row, col + 6, line.narration)
                sheet.write(row, col + 7, line.batch_payment_id.journal_id.bank_account_id.acc_number)
                sheet.write(row, col + 8, '')
                sheet.write(row, col + 9, line.partner_bank_id.bank_id.bic)
                sheet.write(row, col + 10, '11')

                row = row + 1

import datetime
import math
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

from odoo import models
import json


class MissingXlsx(models.AbstractModel):
    _name = 'report.csspl_india.missing_data'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, lines):

        bold = workbook.add_format(
            {'font_size': 11, 'align': 'vcenter', 'bold': True, 'bg_color': '#b7b7b7', 'font': 'Calibri Light',
             'text_wrap': True, 'border': 1})
        bold_red = workbook.add_format(
            {'font_size': 11,'color':'#FF0000', 'align': 'vcenter', 'bold': True, 'bg_color': '#b7b7b7', 'font': 'Calibri Light',
             'text_wrap': True, 'border': 1})
        bold_one = workbook.add_format({'font_size': 12, 'align': 'vcenter', 'bg_color': '#b7b7b7'})
        sheet = workbook.add_worksheet('Missing Data')
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
        sheet.write(0, 0, 'name', bold_red)
        sheet.write(0, 1, 'acc_number', bold_red)
        sheet.write(0, 2, 'ifsc_code', bold_red)
        sheet.write(0, 3, 'bank_id', bold_red)
        sheet.write(0, 4, 'account_payable', bold_red)
        sheet.write(0, 5, 'Journal id', bold)
        sheet.write(0, 6, 'Mail By', bold)
        sheet.write(0, 7, 'street', bold)
        sheet.write(0, 8, 'street2', bold)
        sheet.write(0, 9, 'city', bold)
        sheet.write(0, 10, 'zip', bold)
        sheet.write(0, 11, 'phone', bold)
        sheet.write(0, 12, 'email', bold)
        row = 1
        col = 0

        for line in lines.missing_data_ids:
            sheet.write(row, col, line.contact_name)
            sheet.write(row, col + 1, line.bank_account)
            sheet.write(row, col + 2, line.ifsc_code)
            sheet.write(row, col + 3, '')
            sheet.write(row, col + 5, line.journal_id)
            sheet.write(row, col + 6, line.mail_by)

            row = row + 1

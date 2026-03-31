from lxml import etree
from odoo.tools.misc import formatLang, format_date
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from num2words import num2words
import logging
from collections import defaultdict
import base64
import json
import datetime
import xlwt
from io import BytesIO





gstr_keys = {
        'b2b': {'type': 'inv', 'num': 'inum', 'date': 'idt', 'val': 'val'},
        'b2ba': {'type': 'inv', 'num': 'inum', 'date': 'idt', 'val': 'val'},
        'exp': {'type': 'inv', 'num': 'inum', 'date': 'idt', 'val': 'val'},
        'b2bur': {'type': 'inv', 'num': 'inum', 'date': 'idt', 'val': 'val'},
        'imp_s': {'num': 'inum', 'date': 'idt', 'val': 'val'},
        'imp_g': {'num': 'boe_num', 'date': 'boe_dt', 'val': 'boe_val'},
        'cdnr': {'type': 'nt', 'num': 'nt_num', 'date': 'nt_dt', 'val': 'val'},
        'cdn': {'type': 'nt', 'num': 'nt_num', 'date': 'nt_dt', 'val': 'val'},
        'cdnur': {'num': 'nt_num', 'date': 'nt_dt', 'val': 'val'},
        'tcs': {'num': 'inum', 'date': 'idt', 'val': 'val'}
    }


# Inherited functions from Po gstrs reco module
class Po_gst_reco_inherit(models.TransientModel):
    _inherit = "upload.gstr.reco"

    # Inherited for GSTR Reco functions
    def upload_file_data(self):
        json_file = base64.decodebytes(self.file_data)
        json_data = json.loads(json_file)
        active_id = self.env.context.get('active_id')
        reco_id = self.env['gstr.reconciliation'].sudo().search([('id', '=', active_id)])

        reco_id.b2b_reconciled_moves.unlink()
        reco_id.b2ba_reconciled_moves.unlink()
        reco_id.cdn_reconciled_moves.unlink()

        reco_id.b2b_odoo_missing_moves.unlink()
        reco_id.b2ba_odoo_missing_moves.unlink()
        reco_id.cdn_odoo_missing_moves.unlink()

        reco_id.b2b_file_missing_moves.unlink()
        reco_id.b2ba_file_missing_moves.unlink()
        reco_id.cdn_file_missing_moves.unlink()

        if reco_id.reco_type == 'gstr1':
            # self.sync_gstr_data(json_data, 'b2b', reco_id)
            if json_data.get('b2b'):
                self.sync_gstr_data(json_data, 'b2b', reco_id)
            if json_data.get('b2ba'):
                self.sync_gstr_data(json_data, 'b2ba', reco_id)
            if json_data.get('cdn'):
                self.sync_gstr_data(json_data, 'cdn', reco_id)
            if json_data.get('cdnr'):
                self.sync_gstr_data(json_data, 'cdnr', reco_id)

        if reco_id.reco_type == 'gstr2':
            if json_data.get('b2b'):
                self.sync_gstr_data(json_data, 'b2b', reco_id)
            if json_data.get('b2ba'):
                self.sync_gstr_data(json_data, 'b2ba', reco_id)
            if json_data.get('cdn'):
                self.sync_gstr_data(json_data, 'cdn', reco_id)
            if json_data.get('cdnr'):
                self.sync_gstr_data(json_data, 'cdnr', reco_id)

    def sync_gstr_data(self, json_data,type,reco_id):
        json_moves = json_data[type]
        keys = gstr_keys[type]
        reconciled_moves = []
        odoo_missing_moves = []
        file_missing_moves = []
        domain = [('invoice_date', '>=', reco_id.from_period_id.date_start),
                  ('invoice_date', '<=', reco_id.to_period_id.date_stop),
                  ('journal_id', 'in', reco_id.journal_ids.ids),
                  ('company_id', '=', reco_id.company_id.id), ('state', '=', 'posted')]
        # commented ('reconciled', '=', False) in domain

        if reco_id.reco_type == 'gstr2':
            if type in ('b2b', 'b2ba'):
                domain.append(('move_type', '=', 'in_invoice'))
            elif type in ('cdn', 'cdnr'):
                domain.append(('move_type', '=', 'in_refund'))
        elif reco_id.reco_type == 'gstr1':
            if type in ('b2b', 'b2ba'):
                domain.append(('move_type', '=', 'out_invoice'))
            elif type in ('cdn', 'cdnr'):
                domain.append(('move_type', '=', 'out_refund'))

        moves = self.env['account.move'].sudo().search(domain)
        for rec in json_moves:
            if keys.get('type'):
                invoices = rec.get(keys.get('type'))
            else:
                invoices = rec

            if invoices:
                for inv in invoices:
                    #########################################################
                    file_inum = inv.get(keys.get('num'))
                    file_idate = datetime.datetime.strptime(str(inv.get(keys.get('date'))), '%d-%m-%Y').strftime('%Y-%m-%d')
                    file_amount = float(inv.get(keys.get('val')))
                    partner_id = self.env['res.partner'].sudo().search([('vat', '=', rec.get('ctin'))], limit=1)
                    reco_domain = [('id', 'in', moves.ids)]
                    if reco_id.reco_type == 'gstr1':
                        if type in ('cdn', 'cdnr'):
                            reco_domain.append('|')
                            reco_domain.append(('cdn_ref', '=', file_inum))
                        reco_domain.append(('name', '=', file_inum))

                    if reco_id.reco_type == 'gstr2':
                        if type in ('cdn', 'cdnr'):
                            reco_domain.append('|')
                            reco_domain.append(('cdn_ref', '=', file_inum))
                        reco_domain.append(('ref', '=', file_inum))

                    reco_domain.append(('partner_id.vat', '=', rec.get('ctin')))
                    reconciled_move = self.env['account.move'].sudo().search(reco_domain)
                    # reconciled_move = reconciled_move.filtered(lambda i: i.ref == file_inum)

                    tds_total = sum(reconciled_move.line_ids.filtered(lambda line: line.tax_line_id and line.price_subtotal < 0).mapped('price_subtotal'))
                    # tds_total = sum(self.env['account.move.line'].search([('move_id','=',reconciled_move.id),('tax_line_id','!=',False),('price_subtotal','<',0)]).price_subtotal)
                    amount_to_add = tds_total or 0
                    amount_to_compare = reconciled_move.amount_total + abs(amount_to_add)
                    if reconciled_move and ((amount_to_compare - file_amount) <= 2 and ((amount_to_compare - file_amount) >= 0)):
                        moves = moves.filtered(lambda i: i.id != reconciled_move.id)

                        ######## To avoid duplications in Odoo missing and File Missing tab ##################
                        odoo_missing_to_remove = self.env['odoo.missing.move.line'].sudo().search(['|', '|', ('b2b_gstr_reco_id','=',reco_id.id),('b2ba_gstr_reco_id','=',reco_id.id),('cdn_gstr_reco_id','=',reco_id.id),('file_invoice','=',file_inum)])
                        file_missing_to_remove = self.env['file.missing.move.line'].sudo().search(['|', '|', ('b2b_gstr_reco_id','=',reco_id.id),('b2ba_gstr_reco_id','=',reco_id.id),('cdn_gstr_reco_id','=',reco_id.id),('move_id.id','=',reconciled_move.id)])

                        if odoo_missing_to_remove:
                            for om in odoo_missing_to_remove:
                                om.unlink()

                        if file_missing_to_remove:
                            for fm in file_missing_to_remove:
                                fm.unlink()
                        reconciled_dict = {
                            'inv_date': reconciled_move.invoice_date,
                            'move_id': reconciled_move.id,
                            'partner_id': reconciled_move.partner_id.id,
                            'inv_amt': reconciled_move.amount_total,
                            'state': reconciled_move.state,
                            'move_type': reconciled_move.move_type,
                            'invoice_type': reconciled_move.invoice_type,
                            'currency_id': reconciled_move.currency_id.id,
                            'file_date': file_idate,
                            'file_vendor': rec.get('ctin'),
                            'file_invoice': file_inum,
                            'file_amt': file_amount,
                            'diff_amt': reconciled_move.amount_total - file_amount
                        }
                        if type == 'b2b':
                            reconciled_dict.update({'b2b_gstr_reco_id': reco_id.id})
                        if type == 'b2ba':
                            reconciled_dict.update({'b2ba_gstr_reco_id': reco_id.id})
                        if type in ('cdnr', 'cdn'):
                            reconciled_dict.update({'cdn_gstr_reco_id': reco_id.id})

                        reconciled_moves.append((4,self.env['reconciled.move.line'].sudo().create(reconciled_dict).id))
                        reconciled_move.reconciled = True
                    else:
                        odoo_missing_dict = {
                            'partner_id': partner_id.id,
                            'file_vendor': rec.get('ctin'),
                            'file_invoice': file_inum

                            ,
                            'file_date': file_idate,
                            'file_amt': file_amount,
                        }
                        if type == 'b2b':
                            odoo_missing_dict.update({'b2b_gstr_reco_id': reco_id.id})
                        if type == 'b2ba':
                            odoo_missing_dict.update({'b2ba_gstr_reco_id': reco_id.id})
                        if type in ('cdnr', 'cdn'):
                            odoo_missing_dict.update({'cdn_gstr_reco_id': reco_id.id})

                        odoo_missing_moves.append((0, 0, odoo_missing_dict))

        for move in moves:
            file_missing_dict = {
                'inv_date': move.invoice_date,
                'move_id': move.id,
                'partner_id': move.partner_id.id,
                'inv_amt': move.amount_total,
                'state': move.state,
                'move_type': move.move_type,
                'invoice_type': move.invoice_type,
                'currency_id': move.currency_id.id,
            }
            if type == 'b2b':
                file_missing_dict.update({'b2b_gstr_reco_id': reco_id.id})
            if type == 'b2ba':
                file_missing_dict.update({'b2ba_gstr_reco_id': reco_id.id})
            if type in ('cdnr', 'cdn'):
                file_missing_dict.update({'cdn_gstr_reco_id': reco_id.id})

            file_missing_moves.append((0, 0, file_missing_dict))

        if reconciled_moves:
            if type == 'b2b':
                reco_id.b2b_reconciled_moves = reconciled_moves
            if type == 'b2ba':
                reco_id.b2ba_reconciled_moves = reconciled_moves
            if type in ('cdnr', 'cdn'):
                reco_id.cdn_reconciled_moves = reconciled_moves

        if odoo_missing_moves:
            if type == 'b2b':
                reco_id.b2b_odoo_missing_moves = odoo_missing_moves
            if type == 'b2ba':
                reco_id.b2ba_odoo_missing_moves = odoo_missing_moves
            if type in ('cdnr', 'cdn'):
                reco_id.cdn_odoo_missing_moves = odoo_missing_moves

        if file_missing_moves:
            if type == 'b2b':
                reco_id.b2b_file_missing_moves = file_missing_moves
            if type == 'b2ba' and reco_id.reco_type != 'gstr2':
                reco_id.b2ba_file_missing_moves = file_missing_moves
            if type in ('cdnr', 'cdn'):
                reco_id.cdn_file_missing_moves = file_missing_moves


class GSTRReconciliationInherit(models.Model):
    _inherit = "gstr.reconciliation"

    def write_xls(self, tab, data, worksheet, style):
        title_date_format = xlwt.easyxf(num_format_str='d-MMM-yyyy')
        row_index = 2
        worksheet.col(0).width = 8000
        worksheet.col(1).width = 8000
        worksheet.col(2).width = 8000
        worksheet.col(3).width = 8000
        worksheet.col(4).width = 8000
        worksheet.col(5).width = 8000
        worksheet.col(6).width = 8000
        worksheet.col(7).width = 8000
        worksheet.col(8).width = 8000
        worksheet.col(9).width = 8000
        worksheet.col(10).width = 8000
        for rec in data:
            if tab in ('reconciled', 'missing_file'):
                worksheet.write(row_index, 0, rec.move_type, style)
                worksheet.write(row_index, 1, rec.move_id.name, style)

                worksheet.write(row_index, 3, rec.inv_date,title_date_format)
                # worksheet.write(row_index, 4, rec.move_id.due_days, style)
                worksheet.write(row_index, 4, rec.inv_amt, style)
                worksheet.write(row_index, 5, rec.move_id.igst, style)
                worksheet.write(row_index, 6, rec.move_id.sgst, style)
                worksheet.write(row_index, 7, rec.move_id.cgst, style)
                worksheet.write(row_index, 8, rec.currency_id.name, style)
                # worksheet.write(row_index, 6, rec.invoice_type, style)
                worksheet.write(row_index, 9, rec.state, style)
            if tab in ('reconciled', 'missing_odoo'):
                worksheet.write(row_index, 10 if tab == 'reconciled' else 0, rec.file_invoice, style)
                worksheet.write(row_index, 11 if tab == 'reconciled' else 2, rec.file_vendor, style)
                worksheet.write(row_index, 12 if tab == 'reconciled' else 3, rec.file_date, title_date_format)
                worksheet.write(row_index, 13 if tab == 'reconciled' else 4, rec.file_amt, style)
                worksheet.write(row_index, 15 if tab == 'reconciled' else 6, rec.move_id.amount_untaxed, style)
            if tab in ('missing_file'):
                worksheet.write(row_index, 10, rec.partner_id.vat, style)
                worksheet.write(row_index, 11, rec.move_id.amount_untaxed, style)
                worksheet.write(row_index, 12, rec.move_id.ref, style)
            worksheet.write(row_index, 1 if tab == 'missing_odoo' else 2, rec.partner_id.name, style)
            row_index += 1

    def print_gstr_data(self):
        context = self.env.context.get('inv_type')
        if context == 'b2b':
            reconciled_moves = self.b2b_reconciled_moves
            missing_odoo_moves = self.b2b_odoo_missing_moves
            missing_file_moves = self.b2b_file_missing_moves
        if context == 'b2ba':
            reconciled_moves = self.b2ba_reconciled_moves
            missing_odoo_moves = self.b2ba_odoo_missing_moves
            missing_file_moves = self.b2ba_file_missing_moves
        if context == 'cdn':
            reconciled_moves = self.cdn_reconciled_moves
            missing_odoo_moves = self.cdn_odoo_missing_moves
            missing_file_moves = self.cdn_file_missing_moves
        if context == 'cdnra':
            reconciled_moves = self.cdnra_reconciled_moves
            missing_odoo_moves = self.cdnra_odoo_missing_moves
            missing_file_moves = self.cdnra_file_missing_moves
        if context == 'isd':
            reconciled_moves = self.isd_reconciled_moves
            missing_odoo_moves = self.isd_odoo_missing_moves
            missing_file_moves = self.isd_file_missing_moves
        if context == 'impg':
            reconciled_moves = self.impg_reconciled_moves
            missing_odoo_moves = self.impg_odoo_missing_moves
            missing_file_moves = self.impg_file_missing_moves

        workbook = xlwt.Workbook(encoding='utf-8')
        reconciled_worksheet = workbook.add_sheet("Reconciled")
        missing_odoo_worksheet = workbook.add_sheet("Missing In Odoo")
        missing_file_worksheet = workbook.add_sheet("Missing In File")

        reconciled_headers =["Type","Invoice", "Vendor","Invoice Date","Invoice Amount","IGST","SGST","CGST","Currency","Status","File Invoice","File Vendor","File Date","File Amount","Difference Amount","Taxable Amt"]
        missing_file_headers =["Type","Invoice", "Vendor", "Invoice Date", "Invoice Amount", "IGST", "SGST","CGST","Currency","Status","Vendor Gst","Taxable Amt","Ref"]
        missing_odoo_headers =["File Invoice", "Vendor", "File Vendor", "File Date", "File Amount"]

        fp = BytesIO()

        header_style = xlwt.easyxf('font: bold on, height 220; align: wrap 1,  horiz center; borders: bottom thin, top thin, left thin, right thin ; pattern: pattern fine_dots, fore_color white, back_color gray_ega;')
        base_style = xlwt.easyxf('align: wrap 1; borders: bottom thin, top thin, left thin, right thin')

        self.print_headers(reconciled_worksheet, reconciled_headers, header_style)
        self.print_headers(missing_odoo_worksheet, missing_odoo_headers, header_style)
        self.print_headers(missing_file_worksheet, missing_file_headers, header_style)
        if reconciled_moves:
            self.write_xls('reconciled', reconciled_moves, reconciled_worksheet, base_style)
        if missing_odoo_moves:
            self.write_xls('missing_odoo', missing_odoo_moves, missing_odoo_worksheet, base_style)
        if missing_file_moves:
            self.write_xls('missing_file', missing_file_moves, missing_file_worksheet, base_style)
        workbook.save(fp)

        out = base64.encodebytes(fp.getvalue())
        gst = self.env.company.partner_id.vat
        filename = str(context).capitalize() + gst + '.xls'
        if context == 'b2b':
            self.b2b_xlx = out
            self.b2b_filename = filename
        if context == 'b2ba':
            self.b2ba_xlx = out
            self.b2ba_filename = filename
        if context == 'cdn':
            self.cdn_xlx = out
            self.cdn_filename = filename

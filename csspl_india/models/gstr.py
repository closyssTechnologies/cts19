from odoo import models, fields, api, _
from urllib.parse import unquote_plus
import json
import base64


def _unescape(text):
    try:
        text = unquote_plus(text.encode('utf8'))
        return text
    except Exception as e:
        return text


# Inherited for tax changes in GST Module
class GstrtoolInherit(models.Model):
    _inherit = 'gstr1.tool'

    def getHSNData(self, invoiceObj, count, hsnDict={}, hsnDataDict={}):
        mainData = []
        jsonData = []
        currency = invoiceObj.currency_id or None
        ctx = dict(self._context or {})
        sign = -1 if invoiceObj.move_type in ('out_refund', 'in_refund') else 1

        for invoiceLineObj in invoiceObj.invoice_line_ids.filtered(lambda l: l.product_id and l.tax_ids):
            quantity = invoiceLineObj.quantity or 1.0
            price = invoiceLineObj.price_subtotal / quantity
            taxedAmount, cgst, sgst, igst, rt = 0.0, 0.0, 0.0, 0.0, 0
            rateObjs = invoiceLineObj.tax_ids.filtered(lambda rec: "gst" in rec.tax_group_id.name.lower())
            if rateObjs:
                taxData = self.getTaxedAmount(
                    rateObjs, price, currency, invoiceLineObj, invoiceObj)
                rateAmount = taxData[1]
                taxedAmount = taxData[0]
                # if currency.name != 'INR':
                #     taxedAmount = taxedAmount * (currency.rate_ids.filtered(lambda x: x.name == invoiceObj.invoice_date).inverse_company_rate or currency.inverse_rate)
                taxedAmount = round(taxedAmount, 2)
                # if invoiceObj.partner_id.country_id.code == 'IN':
                rateObj = rateObjs[0]
                if rateObj.amount_type == "group":
                    rt = rateObj.children_tax_ids and rateObj.children_tax_ids[0].amount * 2 or 0
                    cgst, sgst = round(taxedAmount / 2, 2), round(taxedAmount / 2, 2)
                else:
                    rt = rateObj.amount
                    igst = round(taxedAmount, 2)
            invUntaxedAmount = round(invoiceLineObj.price_subtotal, 2)
            if currency.name != 'INR':
                invUntaxedAmount = round(invUntaxedAmount * (currency.rate_ids.filtered(lambda x: x.name == invoiceObj.invoice_date).inverse_company_rate
                                         or currency.inverse_rate), 2)
                # invUntaxedAmount = round(invoiceLineObj.credit, 2)
            productObj = invoiceLineObj.product_id
            # hsnvalue = productObj.l10n_in_hsn_code or ''
            hsnVal = productObj.l10n_in_hsn_code
            # hsnVal = hsnvalue.replace('.', '').replace(" ", "").strip() or 'False'
            hsnName = ''  # productObj.name or 'name'
            uqc = 'OTH'
            if productObj.uom_id:
                uqc = productObj.uom_id.name
                # uom = productObj.uom_id.id
                # uqcObj = self.env['uom.mapping'].search([('uom', '=', uom)])
                # if uqcObj:
                #     uqc = uqcObj[0].name.code
            hsnTuple = (uqc, rt)
            invQty = sign * invoiceLineObj.quantity
            invAmountTotal = sign * (invUntaxedAmount + taxedAmount)
            invUntaxedAmount *= sign
            igst *= sign
            cgst *= sign
            sgst *= sign
            invoice_no = invoiceObj.name


            if hsnDataDict.get(hsnVal):
                hsnTupleDict = hsnDataDict.get(hsnVal).get(hsnTuple) or {}
                if hsnTupleDict:
                    if hsnTupleDict.get('qty'):
                        invQty += hsnTupleDict.get('qty')
                        hsnTupleDict['qty'] = invQty
                    else:
                        hsnTupleDict['qty'] = invQty

                    if hsnTupleDict.get('val'):
                        invAmountTotal = round(hsnTupleDict.get('val') + invAmountTotal, 2)
                        hsnTupleDict['val'] = invAmountTotal
                    else:
                        invAmountTotal = round(invAmountTotal, 2)
                        hsnTupleDict['val'] = invAmountTotal

                    if hsnTupleDict.get('txval'):
                        invUntaxedAmount = round(hsnTupleDict.get('txval') + invUntaxedAmount, 2)
                        hsnTupleDict['txval'] = invUntaxedAmount
                    else:
                        invUntaxedAmount = round(invUntaxedAmount, 2)
                        hsnTupleDict['txval'] = invUntaxedAmount

                    if hsnTupleDict.get('iamt'):
                        igst = round(hsnTupleDict.get('iamt') + igst, 2)
                        hsnTupleDict['iamt'] = igst
                    else:
                        igst = round(igst, 2)
                        hsnTupleDict['iamt'] = igst

                    if hsnTupleDict.get('camt'):
                        cgst = round(hsnTupleDict.get('camt') + cgst, 2)
                        hsnTupleDict['camt'] = cgst
                    else:
                        cgst = round(cgst, 2)
                        hsnTupleDict['camt'] = cgst

                    if hsnTupleDict.get('samt'):
                        sgst = round(hsnTupleDict.get('samt') + sgst, 2)
                        hsnTupleDict['samt'] = sgst
                    else:
                        sgst = round(sgst, 2)
                        hsnTupleDict['samt'] = sgst

                    if hsnTupleDict.get('invoice_no'):
                        invoice_no = hsnTupleDict['invoice_no'] +','+ invoice_no
                        hsnTupleDict['invoice_no'] = invoice_no
                    else:
                        hsnTupleDict['invoice_no'] = invoice_no

                else:
                    count += 1
                    hsnDataDict.get(hsnVal)[hsnTuple] = {
                        'num': count,
                        'hsn_sc': hsnVal,
                        'desc': hsnName,
                        'uqc': uqc,
                        'qty': invQty,
                        'val': invAmountTotal,
                        'rt': rt,
                        'txval': invUntaxedAmount,
                        'iamt': igst,
                        'camt': cgst,
                        'samt': sgst,
                        'csamt': 0.0,
                        'invoice_no': invoice_no if not hsnVal else ''
                    }
            else:
                count += 1
                hsnDataDict[hsnVal] = {
                    hsnTuple: {
                        'num': count,
                        'hsn_sc': hsnVal,
                        'desc': hsnName,
                        'uqc': uqc,
                        'qty': invQty,
                        'val': invAmountTotal,
                        'rt': rt,
                        'txval': invUntaxedAmount,
                        'iamt': igst,
                        'camt': cgst,
                        'samt': sgst,
                        'csamt': 0.0,
                        'invoice_no': invoice_no if not hsnVal else '',
                    }

                }
            hsnvalue = productObj.l10n_in_hsn_code
            if not hsnvalue:
                print("Lets check")

            hsnData = [
                hsnvalue, hsnName, uqc, invQty,
                invAmountTotal, rt, invUntaxedAmount, igst, cgst, sgst, 0.0, invoice_no if not hsnVal else ''
            ]
            if hsnDict.get(hsnVal):
                hsnDict.get(hsnVal)[hsnTuple] = hsnData
            else:
                hsnDict[hsnVal] = {hsnTuple: hsnData}
            mainData.append(hsnData)
        return [mainData, jsonData, hsnDict, hsnDataDict]

    def getInvoiceData(self, active_ids, invoiceType, gstType):
        mainData = []
        jsonData = []
        count = 0
        b2csDataDict = {}
        b2csJsonDataDict = {}
        b2clJsonDataDict = {}
        b2burDataDict = {}
        b2bDataDict = {}
        cdnrDataDict = {}
        cdnurDataDict = {'cdnur': []}
        hsnDict = {}
        hsnDataDict = {}
        reverseChargeMain = self.reverse_charge and 'Y' or 'N'
        counterFilingStatus = self.counter_filing_status and 'Y' or 'N'
        gstcompany_id = self.company_id or self.env.company
        invoiceObjs = self.env['account.move'].browse(active_ids)
        for invoiceObj in invoiceObjs:
            invData = {}
            reverseCharge = 'Y' if invoiceObj.reverse_charge else 'N' if reverseChargeMain == 'N' else reverseChargeMain
            invType = invoiceObj.export_type or 'regular'
            invType_val = dict(invoiceObj._fields['export_type'].selection).get(
                invoiceObj.export_type)
            jsonInvType = 'R'
            if invType == 'sez_with_payment':
                jsonInvType = 'SEWP'
            elif invType == 'sez_without_payment':
                jsonInvType = 'SEWOP'
            elif invType == 'deemed':
                jsonInvType = 'DE'
            elif invType == 'intra_state_igst':
                jsonInvType = 'CBW'
            currency = invoiceObj.currency_id
            invoiceNumber = invoiceObj.name or ''
            if gstType == 'gstr2':
                invoiceNumber = invoiceObj.ref or ''
                if invoiceType == 'cdnr':
                    invoiceNumber = invoiceObj.name or ''
            if len(invoiceNumber) > 16:
                invoiceNumber = invoiceNumber[-16:]
            invoiceDate = invoiceObj.move_type in [
                'out_invoice', 'out_refund'] and invoiceObj.date or invoiceObj.invoice_date
            invoiceJsonDate = invoiceDate.strftime('%d-%m-%Y')
            invoiceDate = invoiceDate.strftime('%d-%b-%Y')
            originalInvNumber, originalInvDate, originalInvJsonDate = '', '', ''
            originalInvObj = invoiceObj.reversed_entry_id
            if originalInvObj:
                originalInvNumber = originalInvObj.name or ''
                if gstType == 'gstr2':
                    originalInvNumber = originalInvObj.ref or ''
                if len(originalInvNumber) > 16:
                    originalInvNumber = originalInvNumber[-16:]
                originalInvDate = originalInvObj.move_type in [
                    'out_invoice', 'out_refund'] and originalInvObj.date or originalInvObj.invoice_date
                originalInvJsonDate = originalInvDate.strftime('%d-%b-%Y')
                originalInvDate = originalInvDate.strftime('%d-%m-%Y')
            invoiceTotal = invoiceObj.amount_total
            if currency.name != 'INR':
                invoiceTotal = invoiceTotal * (currency.rate_ids.filtered(lambda x: x.name == invoiceObj.invoice_date).inverse_company_rate or currency.inverse_rate)
                # invoiceTotal = invoiceObj.amount_total_signed
            invoiceObj.inr_total = invoiceTotal
            invoiceTotal = round(invoiceTotal, 2)
            state = invoiceObj.partner_id.state_id
            code = _unescape(state.l10n_in_tin) or 0
            sname = _unescape(state.name)
            stateName = "{}-{}".format(code, sname)
            data = []
            if invoiceType == 'b2b':
                customerName = invoiceObj.partner_id.parent_id.name if invoiceObj.partner_id.parent_id.name else invoiceObj.partner_id.name
                invData = {
                    "inum": invoiceNumber,
                    "idt": invoiceDate,
                    "val": invoiceTotal,
                    "pos": code,
                    "rchrg": reverseCharge,
                    "inv_typ": jsonInvType
                }
                # if gstType == 'gstr1':
                #     invData['etin'] = ""
                #     invData['diff_percent'] = 0.0
                gstrData = [invoiceObj.l10n_in_gstin, invoiceNumber, invoiceDate,
                            invoiceTotal, stateName, reverseCharge, invType_val]
                if gstType == 'gstr1':
                    gstrData = [invoiceObj.l10n_in_gstin, customerName, invoiceNumber,
                                invoiceDate, invoiceTotal, stateName, reverseCharge, 0.0, invType_val, '']
                data.extend(gstrData)
                respData = self.getGSTInvoiceData(
                    invoiceObj, invoiceType, data, gstType)
                data = respData[0]
                invData['itms'] = respData[1]
                invData['idt'] = invoiceJsonDate
                if b2bDataDict.get(invoiceObj.l10n_in_gstin):
                    b2bDataDict[invoiceObj.l10n_in_gstin].append(invData)
                else:
                    b2bDataDict[invoiceObj.l10n_in_gstin] = [invData]
            elif invoiceType == 'b2bur':
                sply_ty = 'INTER'
                sply_type = 'Inter State'
                if invoiceObj.partner_id.state_id.code != gstcompany_id.state_id.code:
                    sply_ty = 'INTRA'
                    sply_type = 'Intra State'
                invData = {
                    "inum": invoiceNumber,
                    "idt": invoiceDate,
                    "val": invoiceTotal,
                    "pos": code,
                    "sply_ty": sply_ty
                }
                supplierName = invoiceObj.partner_id.name
                data.extend([supplierName, invoiceNumber,
                             invoiceDate, invoiceTotal, stateName, sply_type])
                respData = self.getGSTInvoiceData(
                    invoiceObj, invoiceType, data, gstType)
                data = respData[0]
                invData['itms'] = respData[1]
                invData['idt'] = invoiceJsonDate
                if b2burDataDict.get(supplierName):
                    b2burDataDict[supplierName].append(invData)
                else:
                    b2burDataDict[supplierName] = [invData]
            elif invoiceType == 'b2cl':
                invData = {
                    "inum": invoiceNumber,
                    "idt": invoiceDate,
                    "val": invoiceTotal,
                    # "etin": "",
                }
                # invData['diff_percent'] = 0.0
                data.extend([invoiceNumber, invoiceDate,
                             invoiceTotal, stateName, 0.0])
                respData = self.getGSTInvoiceData(
                    invoiceObj, invoiceType, data, gstType)
                data = respData[0]
                invData['itms'] = respData[1]
                invData['idt'] = invoiceJsonDate
                if b2clJsonDataDict.get(code):
                    b2clJsonDataDict[code].append(invData)
                else:
                    b2clJsonDataDict[code] = [invData]
            elif invoiceType == 'b2cs':
                invData = {
                    "pos": code
                }
                b2bData = ['OE', stateName]
                respData = self.getGSTInvoiceData(
                    invoiceObj, invoiceType, b2bData, gstType)
                b2bData = respData[0]
                rateDataDict = respData[2]
                rateJsonDict = respData[3]
                if b2csDataDict.get(stateName):
                    for key in rateDataDict.keys():
                        if b2csDataDict.get(stateName).get(key):
                            for key1 in rateDataDict.get(key).keys():
                                if key1 in ['rt']:
                                    continue
                                if b2csDataDict.get(stateName).get(key).get(key1):
                                    b2csDataDict.get(stateName).get(key)[key1] = b2csDataDict.get(
                                        stateName).get(key)[key1] + rateDataDict.get(key)[key1]
                                else:
                                    b2csDataDict.get(stateName).get(
                                        key)[key1] = rateDataDict.get(key)[key1]
                        else:
                            b2csDataDict.get(stateName)[
                                key] = rateDataDict[key]
                else:
                    b2csDataDict[stateName] = rateDataDict
                if b2csJsonDataDict.get(code):
                    for key in rateJsonDict.keys():
                        if b2csJsonDataDict.get(code).get(key):
                            for key1 in rateJsonDict.get(key).keys():
                                if b2csJsonDataDict.get(code).get(key).get(key1):
                                    if key1 in ['rt', 'sply_ty', 'typ']:
                                        continue
                                    b2csJsonDataDict.get(code).get(key)[key1] = b2csJsonDataDict.get(
                                        code).get(key)[key1] + rateJsonDict.get(key)[key1]
                                    b2csJsonDataDict.get(code).get(key)[key1] = round(
                                        b2csJsonDataDict.get(code).get(key)[key1], 2)
                                else:
                                    b2csJsonDataDict.get(code).get(
                                        key)[key1] = rateJsonDict.get(key)[key1]
                        else:
                            b2csJsonDataDict.get(code)[key] = rateJsonDict[key]
                else:
                    b2csJsonDataDict[code] = rateJsonDict
                if respData[1]:
                    invData.update(respData[1][0])
            elif invoiceType == 'imps':
                state = self.env.company.state_id
                code = _unescape(state.l10n_in_tin) or 0
                sname = _unescape(state.name)
                stateName = "{}-{}".format(code, sname)
                invData = {
                    "inum": invoiceNumber,
                    "idt": invoiceDate,
                    "ival": invoiceTotal,
                    "pos": code
                }
                supplierName = invoiceObj.partner_id.name
                data.extend([invoiceNumber, invoiceDate,
                             invoiceTotal, stateName])
                respData = self.getGSTInvoiceData(
                    invoiceObj, invoiceType, data, gstType)
                data = respData[0]
                invData['itms'] = respData[1]
                invData['idt'] = invoiceJsonDate
                jsonData.append(invData)
            elif invoiceType == 'impg':
                companyGST = self.env.company.vat
                portcode = ''
                if invoiceObj.l10n_in_shipping_port_code_id:
                    portcode = invoiceObj.l10n_in_shipping_port_code_id.name
                invData = {
                    "boe_num": invoiceNumber,
                    "boe_dt": invoiceJsonDate,
                    "boe_val": invoiceTotal,
                    "port_code": portcode,
                    "stin": companyGST,
                    'is_sez': 'Y'
                }
                supplierName = invoiceObj.partner_id.name
                data.extend([portcode, invoiceNumber, invoiceDate,
                             invoiceTotal, 'Imports', companyGST])
                respData = self.getGSTInvoiceData(
                    invoiceObj, invoiceType, data, gstType)
                data = respData[0]
                invData['itms'] = respData[1]
                jsonData.append(invData)
            elif invoiceType == 'export':
                portcode = ''
                if invoiceObj.l10n_in_shipping_port_code_id:
                    portcode = invoiceObj.l10n_in_shipping_port_code_id.name
                shipping_bill_number = invoiceObj.l10n_in_shipping_bill_number or ''
                shipping_bill_date = invoiceObj.l10n_in_shipping_bill_date and invoiceObj.l10n_in_shipping_bill_date.strftime(
                    '%d-%m-%Y') or ''
                invData = {
                    "inum": invoiceNumber,
                    "idt": invoiceDate,
                    "val": invoiceTotal,
                    "sbpcode": portcode,
                    "sbnum": shipping_bill_number,
                    "sbdt": shipping_bill_date,
                }
                # invData['diff_percent'] = 0.0
                data.extend([
                    invoiceObj.export, invoiceNumber, invoiceDate,
                    invoiceTotal, portcode, shipping_bill_number,
                    shipping_bill_date, 0.0
                ])
                respData = self.getGSTInvoiceData(
                    invoiceObj, invoiceType, data, gstType)
                data = respData[0]
                invData['itms'] = respData[1]
                invData['idt'] = invoiceJsonDate
                jsonData.append(invData)
            elif invoiceType in ['cdnr', 'cdnur']:
                customerName = invoiceObj.partner_id.parent_id.name if invoiceObj.partner_id.parent_id.name else invoiceObj.partner_id.name
                pre_gst = 'N'
                if invoiceObj.pre_gst:
                    pre_gst = 'Y'
                invoiceObjRef = invoiceObj.ref or ''
                reasonList = invoiceObjRef.split(',')
                reasonNote = reasonList[1].strip() if len(
                    reasonList) > 1 else invoiceObjRef
                sply_ty = 'INTER'
                sply_type = 'Inter State'
                if invoiceObj.partner_id.state_id.code != gstcompany_id.state_id.code:
                    sply_ty = 'INTRA'
                    sply_type = 'Intra State'
                invData = {
                    "nt_num": invoiceNumber,
                    "nt_dt": invoiceJsonDate,
                    "ntty": "C",
                    "val": invoiceTotal,
                    "pos": code,
                }
                if invoiceType == 'cdnr':
                    invData.update({
                        "rchrg": reverseCharge,
                        "inv_typ": jsonInvType,
                    })
                    if gstType == 'gstr2':
                        invData['ntty'] = "D"
                    gstrData = [invoiceObj.partner_id.vat, invoiceNumber, invoiceDate, originalInvNumber,
                                originalInvJsonDate, reverseCharge, 'D', reasonNote, sply_type, invoiceTotal]
                    if gstType == 'gstr1':
                        gstrData = [invoiceObj.partner_id.vat, customerName, invoiceNumber,
                                    invoiceDate, 'C', stateName, reverseCharge, invType_val, invoiceTotal, 0.0]
                else:
                    ur_type = 'B2CL'
                    gstrData = [ur_type, invoiceNumber, invoiceDate,
                                'C', stateName, invoiceTotal, 0.0]
                data.extend(gstrData)
                respData = self.getGSTInvoiceData(
                    invoiceObj, invoiceType, data, gstType)
                data = respData[0]
                invData['itms'] = respData[1]
                if invoiceType == 'cdnr':
                    if cdnrDataDict.get(invoiceObj.l10n_in_gstin):
                        cdnrDataDict[invoiceObj.l10n_in_gstin].append(invData)
                    else:
                        cdnrDataDict[invoiceObj.l10n_in_gstin] = [invData]
                else:
                    cdnurDataDict['cdnur'].append(invData)
            elif invoiceType == 'hsn':
                respData = self.getHSNData(
                    invoiceObj, count, hsnDict, hsnDataDict)
                data = respData[0]
                jsonData.extend(respData[1])
                hsnDict = respData[2]
                hsnDataDict = respData[3]
                invoiceObj.gst_status = 'ready_to_upload'
            if data:
                mainData.extend(data)

        if b2csJsonDataDict:
            for pos, val in b2csJsonDataDict.items():
                for line in val.values():
                    line['pos'] = pos
                    # line['diff_percent'] = 0.0
                    jsonData.append(line)
        if b2csDataDict:
            b2csData = []
            for state, data in b2csDataDict.items():
                for rate, val in data.items():
                    b2csData.append(['OE', state, 0.0, rate, round(
                        val['taxval'], 2), round(val['cess'], 2), ''])
            mainData = b2csData
        if b2bDataDict:
            for ctin, inv in b2bDataDict.items():
                jsonData.append({
                    # 'cfs': counterFilingStatus,
                    'ctin': ctin,
                    'inv': inv
                })
        if b2burDataDict:
            for ctin, inv in b2burDataDict.items():
                jsonData.append({
                    'inv': inv
                })
        if b2clJsonDataDict:
            for pos, inv in b2clJsonDataDict.items():
                jsonData.append({
                    'pos': pos,
                    'inv': inv
                })
        if cdnrDataDict:
            for ctin, nt in cdnrDataDict.items():
                jsonData.append({
                    # 'cfs': counterFilingStatus,
                    'ctin': ctin,
                    'nt': nt
                })
        if cdnurDataDict:
            if cdnurDataDict.get('cdnur'):
                jsonData = cdnurDataDict['cdnur']
        if hsnDict:
            vals = hsnDict.values()
            hsnMainData = []
            for val in vals:
                hsnMainData.extend(val.values())
            mainData = hsnMainData
        if hsnDataDict:
            vals = hsnDataDict.values()
            hsnMainData = []
            for val in vals:
                hsnMainData.extend(val.values())
            jsonData = hsnMainData
        return [mainData, jsonData]

    def getGSTInvoiceData(self, invoiceObj, invoiceType, data, gstType=''):
        jsonItemData = []
        count = 0
        rateDataDict = {}
        rateDict = {}
        rateJsonDict = {}
        itcEligibility = 'Ineligible'
        ctx = dict(self._context or {})
        if gstType == 'gstr2':
            itcEligibility = self.itc_eligibility
            if itcEligibility == 'Ineligible':
                itcEligibility = invoiceObj.itc_eligibility
        for invoiceLineObj in invoiceObj.invoice_line_ids.filtered(lambda l: l.product_id and l.tax_ids):
            if invoiceLineObj.product_id:
                if invoiceLineObj.product_id.type == 'service':
                    if invoiceType == 'impg':
                        continue
                else:
                    if invoiceType == 'imps':
                        continue
            else:
                if invoiceType == 'impg':
                    continue
            # if invoiceLineObj.product_id.categ_id.is_round_off:
            #     continue
            invoiceLineData = self.getInvoiceLineData(data, invoiceLineObj, invoiceObj, invoiceType)
            if invoiceLineData:
                rate = invoiceLineData[2]
                rateAmount = invoiceLineData[3]
                if invoiceLineData[1]:
                    invoiceLineData[1]['txval'] = rateAmount
                if gstType == 'gstr2':
                    igst = invoiceLineData[1].get('iamt') or 0.0
                    cgst = invoiceLineData[1].get('camt') or 0.0
                    sgst = invoiceLineData[1].get('samt') or 0.0
                    if rate not in rateDict.keys():
                        rateDataDict[rate] = {
                            'rt': rate,
                            'taxval': rateAmount,
                            'igst': igst,
                            'cgst': cgst,
                            'sgst': sgst,
                            'cess': 0.0
                        }
                    else:
                        rateDataDict[rate]['taxval'] = rateDataDict[rate]['taxval'] + rateAmount
                        rateDataDict[rate]['igst'] = rateDataDict[rate]['igst'] + igst
                        rateDataDict[rate]['cgst'] = rateDataDict[rate]['cgst'] + cgst
                        rateDataDict[rate]['sgst'] = rateDataDict[rate]['sgst'] + sgst
                        rateDataDict[rate]['cess'] = rateDataDict[rate]['cess'] + 0.0
                if gstType == 'gstr1':
                    if rate not in rateDict.keys():
                        rateDataDict[rate] = {
                            'rt': rate,
                            'taxval': rateAmount,
                            'cess': 0.0
                        }
                    else:
                        rateDataDict[rate]['taxval'] = rateDataDict[rate]['taxval'] + rateAmount
                        rateDataDict[rate]['cess'] = rateDataDict[rate]['cess'] + 0.0
                if rate not in rateJsonDict.keys():
                    rateJsonDict[rate] = invoiceLineData[1]
                else:
                    for key in invoiceLineData[1].keys():
                        if key in ['rt', 'sply_ty', 'typ', 'elg']:
                            continue
                        if rateJsonDict[rate].get(key):
                            rateJsonDict[rate][key] = rateJsonDict[rate][key] + invoiceLineData[1][key]
                            rateJsonDict[rate][key] = round(rateJsonDict[rate][key], 2)
                        else:
                            rateJsonDict[rate][key] = invoiceLineData[1][key]
                invData = []
                if gstType == 'gstr1':
                    invData = invoiceLineData[0] + [rateDataDict[rate]['taxval']]
                if gstType == 'gstr2':
                    if invoiceType in ['imps', 'impg']:
                        invData = invoiceLineData[0] + [
                            rateDataDict[rate]['taxval'],
                            rateDataDict[rate]['igst']
                        ]
                    else:
                        invData = invoiceLineData[0] + [
                            rateDataDict[rate]['taxval'],
                            rateDataDict[rate]['igst'],
                            rateDataDict[rate]['cgst'],
                            rateDataDict[rate]['sgst']
                        ]
                if invoiceType in ['b2b', 'cdnr']:
                    if gstType == 'gstr1':
                        invData = invData + [0.0]
                    if gstType == 'gstr2':
                        if itcEligibility != 'Ineligible':
                            invData = invData + [0.0] + [itcEligibility] + [
                                rateDataDict[rate]['igst']
                            ] + [rateDataDict[rate]['cgst']] + [
                                rateDataDict[rate]['sgst']
                            ] + [rateDataDict[rate]['cess']]
                        else:
                            invData = invData + [0.0] + [itcEligibility] + [0.0] * 4

                elif invoiceType == 'b2bur':
                    if itcEligibility != 'Ineligible':
                        invData = invData + [0.0] + [itcEligibility] + [
                            rateDataDict[rate]['igst']
                        ] + [rateDataDict[rate]['cgst']] + [
                            rateDataDict[rate]['sgst']
                        ] + [rateDataDict[rate]['cess']]
                    else:
                        invData = invData + [0.0] + [itcEligibility] + [0.0] * 4
                elif invoiceType in ['imps', 'impg']:
                    if itcEligibility != 'Ineligible':
                        invData = invData + [0.0] + [itcEligibility] + [
                            rateDataDict[rate]['igst']
                        ] + [rateDataDict[rate]['cess']]
                    else:
                        invData = invData + [0.0] + [itcEligibility] + [0.0] + [0.0]
                elif invoiceType in ['b2cs', 'b2cl']:
                    invData = invData + [0.0, '']
                    # if invoiceType == 'b2cl':
                    #     bonded_wh = 'Y' if invoiceObj.export_type == 'sale_from_bonded_wh' else 'N'
                    #     invData = invData + [bonded_wh]
                rateDict[rate] = invData
        mainData = rateDict.values()
        if rateJsonDict:
            for jsonData in rateJsonDict.values():
                count = count + 1
                if invoiceType in ['b2b', 'b2bur', 'cdnr'] and gstType == 'gstr2':
                    jsonItemData.append({
                        "num": count,
                        'itm_det': jsonData,
                        "itc": {
                            "elg": "no",
                            "tx_i": 0.0,
                            "tx_s": 0.0,
                            "tx_c": 0.0,
                            "tx_cs": 0.0
                        }
                    })
                elif invoiceType in ['imps', 'impg']:
                    jsonItemData.append({
                        "num": count,
                        'itm_det': jsonData,
                        "itc": {
                            "elg": "no",
                            "tx_i": 0.0,
                            "tx_cs": 0.0
                        }
                    })
                else:
                    jsonItemData.append({"num": count, 'itm_det': jsonData})
        return [mainData, jsonItemData, rateDataDict, rateJsonDict]

    def generateCsv(self):
        invoiceObjs = self.invoice_lines
        name = self.name
        gstinCompany = self.env.company.vat
        fp = (self.period_id.code or '').replace('/', '')
        jsonData = {
            "gstin": gstinCompany,
            "fp": fp,
            "version": "GST3.0.4",
            "hash": "hash",
            "gt": self.gross_turnover,
            "cur_gt": self.cgt,
        }
        gstType = self.gst_type
        if invoiceObjs:
            typeDict = {}
            invoiceIds = invoiceObjs.ids
            for invoiceObj in invoiceObjs:
                if typeDict.get(invoiceObj.invoice_type):
                    typeDict.get(invoiceObj.invoice_type).append(invoiceObj.id)
                else:
                    typeDict[invoiceObj.invoice_type] = [invoiceObj.id]
            typeList = self.getTypeList()
            for invoice_type, active_ids in typeDict.items():
                if invoice_type in typeList:
                    continue
                respData = self.exportCsv(active_ids, invoice_type, name, gstType)
                attachment = respData[0]
                jsonInvoiceData = respData[1]
                if invoice_type == 'b2b':
                    jsonData.update({invoice_type: jsonInvoiceData})
                    self.b2b_attachment = attachment.id if attachment else False
                if invoice_type == 'b2bur':
                    jsonData.update({invoice_type: jsonInvoiceData})
                    self.b2bur_attachment = attachment.id if attachment else False
                if invoice_type == 'b2cs':
                    self.b2cs_attachment = attachment.id if attachment else False
                    jsonData.update({invoice_type: jsonInvoiceData})
                if invoice_type == 'b2cl':
                    jsonData.update({invoice_type: jsonInvoiceData})
                    self.b2cl_attachment = attachment.id if attachment else False
                if invoice_type == 'import':
                    impsAttach = attachment[0]
                    impsJsonInvoiceData = attachment[1]
                    impgAttach = jsonInvoiceData[0]
                    impgJsonInvoiceData = jsonInvoiceData[1]
                    jsonData.update({
                        'imp_s': impsJsonInvoiceData,
                        'imp_g': impgJsonInvoiceData
                    })
                    if impsAttach:
                        self.imps_attachment = impsAttach.id
                    if impgAttach:
                        self.impg_attachment = impgAttach.id
                if invoice_type == 'export':
                    jsonData.update(
                        {'exp': {
                            "exp_typ": "WOPAY",
                            "inv": jsonInvoiceData
                        }})
                    self.export_attachment = attachment.id
                if invoice_type == 'cdnr':
                    jsonData.update({
                        invoice_type: jsonInvoiceData
                    })
                    self.cdnr_attachment = attachment.id
                if invoice_type == 'cdnur':
                    jsonData.update({
                        invoice_type: jsonInvoiceData
                    })
                    self.cdnur_attachment = attachment.id
            if not self.hsn_attachment:
                respHsnData = self.exportCsv(invoiceIds, 'hsn', name, gstType)
                if respHsnData:
                    hsnAttachment = respHsnData[0]
                    jsonInvoiceData = respHsnData[1]
                    jsonData.update({'hsn': {"data": jsonInvoiceData}})
                    if hsnAttachment:
                        self.hsn_attachment = hsnAttachment.id
                        self.status = 'ready_to_upload'
            if not self.json_attachment:
                if jsonData:
                    jsonData = json.dumps(jsonData, indent=4, sort_keys=False)
                    base64Data = base64.b64encode(jsonData.encode('utf-8'))
                    jsonAttachment = False
                    try:
                        jsonFileName = "{}.json".format(name)
                        jsonAttachment = self.env['ir.attachment'].create({
                            'datas': base64Data,
                            'type': 'binary',
                            'res_model': 'gstr1.tool',
                            'res_id': self.id,
                            'db_datas': jsonFileName,
                            'store_fname': jsonFileName,
                            'name': jsonFileName
                        })
                    except ValueError:
                        return jsonAttachment
                    if jsonAttachment:
                        self.json_attachment = jsonAttachment.id
        message = "Your gst & hsn csv are successfully generated"
        partial = self.env['message.wizard'].create({'text': message})
        self.combine_sheets()
        return {
            'name': ("Information"),
            'view_mode': 'form',
            'res_model': 'message.wizard',
            'view_id': self.env.ref('gst_invoice_v16.message_wizard_form1').id,
            'res_id': partial.id,
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
        }

    def action_view_invoice(self):
        invoices = self.mapped('invoice_lines')
        action = self.env.ref('gst_invoice_v16.customer_invoice_list_action').sudo().read()[0]
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = invoices.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action
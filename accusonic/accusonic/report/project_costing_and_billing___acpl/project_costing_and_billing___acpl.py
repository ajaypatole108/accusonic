# Copyright (c) 2024, Ajay Patole and contributors
# For license information, please see license.txt

import frappe
import logging
from frappe import _, qb, scrub

import babel.numbers
import decimal

logging.basicConfig(filename='project_costing_billing_acpl.log', level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

def execute(filters=None):
	return get_columns(), get_data(filters)

def get_data(filters):
	mysql =""" SELECT
				p.name AS name,
				p.project_name AS project_name,
				p.cost_center AS cost_center,
				ROUND((SELECT SUM(`tabSales Invoice`.grand_total) FROM `tabSales Invoice` WHERE `tabSales Invoice`.docstatus = 1 AND `tabSales Invoice`.project = p.name),2) AS inv_amt,
				
				ROUND((SELECT CASE WHEN
					(SELECT SUM(`tabPayment Entry`.paid_amount) FROM `tabPayment Entry` WHERE `tabPayment Entry`.docstatus = 1 AND `tabPayment Entry`.payment_type = "Receive" and `tabPayment Entry`.project = p.name and `tabPayment Entry`.docstatus = 1) IS NULL THEN 0
				ELSE
					(SELECT SUM(`tabPayment Entry`.paid_amount) FROM `tabPayment Entry` WHERE `tabPayment Entry`.docstatus = 1 AND `tabPayment Entry`.payment_type = "Receive" and `tabPayment Entry`.project = p.name and `tabPayment Entry`.docstatus = 1)END)
					+ 
				(SELECT CASE WHEN   
					(select sum(jea.credit) from `tabJournal Entry Account` jea JOIN `tabJournal Entry` je ON jea.parent = je.name where je.voucher_type = 'Bank Entry' and jea.account = 'Debtors - TIEPL' and jea.reference_type = 'Sales Invoice' and jea.project = p.name and je.docstatus = 1) IS NULL THEN 0 
				ELSE
					(select sum(jea.credit) from `tabJournal Entry Account` jea JOIN `tabJournal Entry` je ON jea.parent = je.name where je.voucher_type = 'Bank Entry' and jea.account = 'Debtors - TIEPL' and jea.reference_type = 'Sales Invoice' and jea.project = p.name and je.docstatus = 1)END))
				AS received_amt,
				
				ROUND((SELECT SUM(`tabPurchase Invoice`.grand_total) FROM `tabPurchase Invoice` WHERE `tabPurchase Invoice`.docstatus = 1 AND `tabPurchase Invoice`.project = p.name)) AS purchase_amt,
				
				(SELECT SUM(`tabPayment Entry`.paid_amount) FROM `tabPayment Entry` WHERE `tabPayment Entry`.docstatus = 1 AND `tabPayment Entry`.payment_type = "Pay" and `tabPayment Entry`.project = p.name) AS paid_amt,
				
				-- [formula --> Received_Amt - Paid_Amt - Expense_Claim]
				( 
				( (SELECT CASE WHEN
						(SELECT SUM(`tabPayment Entry`.paid_amount) FROM `tabPayment Entry` WHERE `tabPayment Entry`.docstatus = 1 AND `tabPayment Entry`.payment_type = "Receive" and `tabPayment Entry`.project = p.name and `tabPayment Entry`.docstatus = 1) IS NULL THEN 0
					ELSE
						(SELECT SUM(`tabPayment Entry`.paid_amount) FROM `tabPayment Entry` WHERE `tabPayment Entry`.docstatus = 1 AND `tabPayment Entry`.payment_type = "Receive" and `tabPayment Entry`.project = p.name and `tabPayment Entry`.docstatus = 1)END)
						+ 
					(SELECT CASE WHEN   
						(select sum(jea.credit) from `tabJournal Entry Account` jea JOIN `tabJournal Entry` je ON jea.parent = je.name where je.voucher_type = 'Bank Entry' and jea.account = 'Debtors - TIEPL' and jea.reference_type = 'Sales Invoice' and jea.project = p.name and je.docstatus = 1) IS NULL THEN 0 
					ELSE
						(select sum(jea.credit) from `tabJournal Entry Account` jea JOIN `tabJournal Entry` je ON jea.parent = je.name where je.voucher_type = 'Bank Entry' and jea.account = 'Debtors - TIEPL' and jea.reference_type = 'Sales Invoice' and jea.project = p.name and je.docstatus = 1)END) ) 
						
						-
						
					( (SELECT SUM(`tabPayment Entry`.paid_amount) FROM `tabPayment Entry` WHERE `tabPayment Entry`.docstatus = 1 AND `tabPayment Entry`.payment_type = "Pay" and `tabPayment Entry`.project = p.name) )
					
					-
					
					( p.total_expense_claim )
				) as cashflow_expense,
				
				(p.total_purchase_cost - p.total_consumed_material_cost) as purchase_consume,
				p.total_expense_claim AS total_expense_claim,
				
				-- %% Profitability Column [Formula --> ((Inv_Amt/(Purchase_amt + Expense_Claim))-1)*100]
				(
						ROUND(
							((
								(SELECT SUM(`tabSales Invoice`.grand_total) 
								FROM `tabSales Invoice` 
								WHERE `tabSales Invoice`.docstatus = 1 
								AND `tabSales Invoice`.project = p.name
								) 
								/ 
								(
									(SELECT SUM(`tabPurchase Invoice`.grand_total) 
									FROM `tabPurchase Invoice` 
									WHERE `tabPurchase Invoice`.docstatus = 1 
									AND `tabPurchase Invoice`.project = p.name
									) 
									+ p.total_expense_claim
								)
							)-1) * 100, 2
						)
				) AS profitability,
				
				p.estimated_costing AS estimated_costing,
				p.total_costing_amount AS total_costing_amount
			FROM
				`tabProject` p 
				JOIN `tabPayment Entry` pe ON pe.project = p.name
			WHERE
				p.status = 'Open'
			group by
				p.name
			order by
				p.name"""

	mydata = frappe.db.sql(mysql, as_dict=1)
	logging.info(mydata)
	new_data = []


	for row in mydata:
		if row['profitability'] == None or row['profitability'] == 0:
			pass
		else:
			if row['profitability'] > 0:
				row['prof3itability'] = '<span style="color: green;">' + str(row['profitability']) + str('%') + '</span>'
			else:
				row['profitability'] = '<span style="color: red;">' + str(row['profitability']) + str('%') + '</span>'

		if row['cashflow_expense'] > 0:
			if row['inv_amt'] == None:
				pass
			else:
				row['inv_amt'] = '<span style="color: ;">' + str(babel.numbers.format_currency(decimal.Decimal(row['inv_amt']), "INR" )) + '</span>'
			
			if row['received_amt'] == None:
				pass
			else:
				row['received_amt'] = '<span style="color: ;">' + str(babel.numbers.format_currency(decimal.Decimal(row['received_amt']), "INR" )) + '</span>'

			if row['purchase_amt'] == None:
				pass
			else:
				row['purchase_amt'] = '<span style="color: ;">' + str(babel.numbers.format_currency(decimal.Decimal(row['purchase_amt']), "INR" )) + '</span>'

			if row['paid_amt'] == None:
				pass
			else:
				row['paid_amt'] = '<span style="color: ;">' + str(babel.numbers.format_currency(decimal.Decimal(row['paid_amt']), "INR" )) + '</span>'

			if row['purchase_consume'] == None:
				pass
			else:
				row['purchase_consume'] = '<span style="color: ;">' + str(babel.numbers.format_currency(decimal.Decimal(row['purchase_consume']), "INR" )) + '</span>'

			if row['total_expense_claim'] == None:
				pass
			else:
				row['total_expense_claim'] = '<span style="color: ;">' + str(babel.numbers.format_currency(decimal.Decimal(row['total_expense_claim']), "INR" )) + '</span>'
			
			if row['cashflow_expense'] == None:
				pass
			else:
				row['cashflow_expense'] = '<span style="color: green;">' + str(babel.numbers.format_currency(decimal.Decimal(row['cashflow_expense']), "INR" )) + '</span>'

			if row['estimated_costing'] == None:
				pass
			else:
				row['estimated_costing'] = '<span style="color: ;">' + str(babel.numbers.format_currency(decimal.Decimal(row['estimated_costing']), "INR" )) + '</span>'
			
			if row['total_costing_amount'] == None:
				pass
			else:
				row['total_costing_amount'] = '<span style="color: ;">' + str(babel.numbers.format_currency(decimal.Decimal(row['total_costing_amount']), "INR" )) + '</span>'
		else:
			
			if row['inv_amt'] == None:
				pass
			else:
				row['inv_amt'] = '<span style="color: ;">' + str(babel.numbers.format_currency(decimal.Decimal(row['inv_amt']), "INR" )) + '</span>'
			
			if row['received_amt'] == None:
				pass
			else:
				row['received_amt'] = '<span style="color: ;">' + str(babel.numbers.format_currency(decimal.Decimal(row['received_amt']), "INR" )) + '</span>'
			
			if row['purchase_amt'] == None:
				pass
			else:
				row['purchase_amt'] = '<span style="color: ;">' + str(babel.numbers.format_currency(decimal.Decimal(row['purchase_amt']), "INR" )) + '</span>'

			if row['paid_amt'] == None:
				pass
			else:
				row['paid_amt'] = '<span style="color: ;">' + str(babel.numbers.format_currency(decimal.Decimal(row['paid_amt']), "INR" )) + '</span>'

			if row['purchase_consume'] == None:
				pass
			else:
				row['purchase_consume'] = '<span style="color: ;">' + str(babel.numbers.format_currency(decimal.Decimal(row['purchase_consume']), "INR" )) + '</span>'

			if row['total_expense_claim'] == None:
				pass
			else:
				row['total_expense_claim'] = '<span style="color: ;">' + str(babel.numbers.format_currency(decimal.Decimal(row['total_expense_claim']), "INR" )) + '</span>'
			
			if row['cashflow_expense'] == None:
				pass
			else:
				row['cashflow_expense'] = '<span style="color: red;">' + str(babel.numbers.format_currency(decimal.Decimal(row['cashflow_expense']), "INR" )) + '</span>'

			if row['estimated_costing'] == None:
				pass
			else:
				row['estimated_costing'] = '<span style="color: ;">' + str(babel.numbers.format_currency(decimal.Decimal(row['estimated_costing']), "INR" )) + '</span>'
			
			if row['total_costing_amount'] == None:
				pass
			else:
				row['total_costing_amount'] = '<span style="color: ;">' + str(babel.numbers.format_currency(decimal.Decimal(row['total_costing_amount']), "INR" )) + '</span>'

		new_data.append(row)
	logging.info(new_data)
	return new_data

def get_columns():
	return [
		 {
            'fieldname': 'name',
            'label': _('ProjectID'),
            'fieldtype': 'Data',
			'width' : '100'
        },
		{
            'fieldname': 'project_name',
            'label': _('ProjectName'),
            'fieldtype': 'Data',
			'width' : '200'
        },
		{
            'fieldname': 'cost_center',
            'label': _('CostCenter'),
            'fieldtype': 'Data',
			'width' : '200'	
        },
		{
            'fieldname': 'inv_amt',
            'label': _('Invoice Amt'),
            'fieldtype': 'Data',
			'width' : '150'	
        },
		{
            'fieldname': 'received_amt',
            'label': _('Recieved Amt'),
            'fieldtype': 'Data',
			'width' : '150'	
        },
		{
            'fieldname': 'purchase_amt',
            'label': _('Purchase Amt'),
            'fieldtype': 'Data',
			'width' : '150'	
        },
		{
            'fieldname': 'paid_amt',
            'label': _('Paid Amt'),
            'fieldtype': 'Data',
			'width' : '150'	
        },
		{
            'fieldname': 'cashflow_expense',
            'label': _('Current Cashflow Expense'),
            'fieldtype': 'Data',
			'width' : '150'	
        },
		{
            'fieldname': 'purchase_consume',
            'label': _('Purchase - Consume'),
            'fieldtype': 'Data',
			'width' : '180'	
        },
		{
            'fieldname': 'total_expense_claim',
            'label': _('T.ExpenseClaimAmt'),
            'fieldtype': 'Data',
			'width' : '150'	
        },
		{
            'fieldname': 'profitability',
            'label': _('% Profitability'),
            'fieldtype': 'Data',
			'width' : '150'	
        },
		{
            'fieldname': 'estimated_costing',
            'label': _('Est.Costing'),
            'fieldtype': 'Data',
			'width' : '150'	
        },
		{
            'fieldname': 'total_costing_amount',
            'label': _('T.CostingAmt'),
            'fieldtype': 'Data',
			'width' : '150'	
        }
	]

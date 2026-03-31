{
    "name": "CSS Project",
    "version": "16.0",
    "description": """Using This module to create BOQ and Tracking Materails""",
    'sequence': 1,
    "depends": [
        'base','project', 'purchase', 'purchase_stock', 'csspl_india', 'uom', 'approvals','hr_expense',
                'account', 'analytic','account_accountant', 'hr_timesheet','stock','crm'],
    'data': [
        'security/ir.model.access.csv',
        'security/sequence.xml',
        'data/uom.xml',
        'views/project.xml',
        'views/purchase.xml',
        'wizards/project.xml',
        'wizards/account.xml',
        'views/account.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
}


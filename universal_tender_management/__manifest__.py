{
    'name': 'CSS Universal Tender Management',
    'version': '16.0.1.0.0',
    'category': 'Operations',
    'summary': 'Universal Tender Management System',
    'author': 'Closyss Technologies',
    'depends': ['base', 'mail', 'project', 'account'],
    'data': [
        'security/tender_security.xml',
        'security/ir.model.access.csv',
        'data/tender_stage_data.xml',
        'views/tender_stage_views.xml',
        'views/tender_type_views.xml',
        'views/tender_master_views.xml',
        'views/tender_bg_views.xml',
        'views/tender_menu.xml',
    ],
    'application': True,
}

# __manifest__.py

{
    'name': 'Project Task Reports',
    'version': '17.0.1.3.0',
    'summary': 'Adds dynamic notebook sections with structured checklists and purchase order tracking to Project Tasks.',
    'author': 'anwer',
    'category': 'Project',
    'depends': ['project', 'purchase'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_task_views.xml',
        'views/project_project_views.xml',
        'views/purchase_order_views.xml',
        'reports/paperformat.xml',
        'reports/project_task_report.xml', 
    ],
    
    'installable': True,
    'application': False,
}
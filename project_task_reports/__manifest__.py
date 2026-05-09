# __manifest__.py

{
    'name': 'Project Task Reports',
    'version': '17.0.1.0.0',
    'summary': 'Adds dynamic notebook sections with structured checklists to Project Tasks.',
    'author': 'anwer',
    'category': 'Project',
    'depends': ['project'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_task_views.xml',
        'reports/paperformat.xml',
        'reports/project_task_report.xml', 
    ],
    
    'installable': True,
    'application': False,
}
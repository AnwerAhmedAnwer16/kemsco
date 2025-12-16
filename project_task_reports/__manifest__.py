# __manifest__.py

{
    'name': 'Project Task Reports',
    'version': '17.0.1.0.0',
    'summary': 'Adds dynamic notebook sections with structured checklists to Project Tasks.',
    'author': 'Anwer Abdelkader',
    'category': 'Project',
    'depends': ['project'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_task_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'project_task_reports/static/src/css/project_task_reports.css',
        ],
    },
    'installable': True,
    'application': False,
}
{
    'name': 'simplify_access_management',

    'summary': """Simplify Access Management""",
    'description': """Simplify Access Management""",

    'category': 'Tools',
    'author': "Abdallah",
    'license': "OPL-1",
    'depends': ['web'],
    'data': [
        # Security
        'security/ir.model.access.csv',
        'security/security.xml',
        # Data
        'data/ir_ui_view_type.xml',
        # Views
        'views/access_management.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # 'simplify_access_management/static/src/xml/*',
            'simplify_access_management/static/src/js/*',
        ]
    },
    'post_init_hook': 'post_install_ir_access_actions_hook',

    'application': True,
    'installable': True,
    'auto_install': False,
}

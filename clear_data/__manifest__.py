{
    'name': 'clear_data',
    'summary': """A powerful testing tool.Easily clear any odoo object data what you want.""",
    'description': """A powerful testing tool.Easily clear any odoo object data what you want.""",

    'author': "ResalaSoft",
    'category': 'Resala/base',
    "license": "OPL-1",
    'website': 'http://www.resalasoft.com',

    'depends': ['base'],
    'data': [
        # data
        'data/clear_data.xml',
        # security
        'security/ir.model.access.csv',
        # views
        'views/clear_data.xml',
    ],

    'installable': True,
    'application': True,
    'auto_install': False,
}

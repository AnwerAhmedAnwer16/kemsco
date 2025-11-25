# -*- coding: utf-8 -*-
{
    "name": "Odoo Arabic Right to Left",
    "summary": "Provide a right-to-left experience for Arabic users in the backend.",
    "version": "17.0.1.0.0",
    "category": "Technical Settings",
    "author": "Amira Essam El-Din",
    "support": "aessam86@gmail.com",
    "website": "https://www.linkedin.com/in/amira-essam-el-din-abd-el-fattah-43730361",
    "license": "OPL-1",
    "depends": ["web"],
    "data": ["views/templates.xml"],
    "assets": {
        "rtl_arabic.assets_rtl": [
            "rtl_arabic/static/src/css/bootstrap-rtl.min.css",
            "rtl_arabic/static/src/css/arabic.css",
        ],
    },
    "images": ["rtl_arabic/static/description/images/1.png"],
    "installable": True,
    "application": False,
    "auto_install": False,
}

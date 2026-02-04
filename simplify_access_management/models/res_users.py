import logging
from odoo.exceptions import UserError, AccessDenied
from odoo import fields, models, api, SUPERUSER_ID, _

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    access_management_ids = fields.Many2many(
        comodel_name='access.management', relation='access_management_users_rel',
        column1='user_id', column2='access_management_id', string='Access Management')

    @classmethod
    def _login(cls, db, login, password, user_agent_env):
        res = super(ResUsers, cls)._login(db, login, password, user_agent_env=user_agent_env)
        try:
            with cls.pool.cursor() as cr:
                self = api.Environment(cr, SUPERUSER_ID, {})[cls._name]
                user = self.sudo().browse(res)
                if any(user.access_management_ids.filtered(lambda a: a.is_active and a.disable_login)):
                    raise AccessDenied('Login Disabled')
        except AccessDenied:
            _logger.info("Login failed for db:%s login:%s from ", db, login)
            raise
        return res

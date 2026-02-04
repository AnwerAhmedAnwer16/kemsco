
from . import models
from . import controllers


def post_install_ir_access_actions_hook(env):
    for action in env['ir.actions.actions'].search([]):
        env['ir.access.actions'].create({'name': action.name, 'action_id': action.id})

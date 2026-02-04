from odoo.tools import config
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval
from odoo import api, fields, models, tools, _


class IrRule(models.Model):
    _inherit = 'ir.rule'

    @api.model
    @tools.conditional(
        'xml' not in config['dev_mode'],
        tools.ormcache('self.env.uid', 'self.env.su', 'model_name', 'mode',
                       'tuple(self._compute_domain_context_values())'),
    )
    def _compute_domain(self, model_name, mode="read"):
        self._cr.execute("""SELECT value from ir_config_parameter where key='uninstall_simplify_access_management'""")
        value = self._cr.fetchone() or False
        if not value:
            self._cr.execute("""select state from ir_module_module where name = 'simplify_access_management'""")
            value = self._cr.fetchone()
            value = value and value[0] or False
            if model_name and value == 'installed':
                access_domain_ids = self._get_access_management_domain(model_name)
                if access_domain_ids:
                    domain_list = []
                    for access_domain in access_domain_ids:
                        domain = safe_eval(access_domain.domain) if access_domain.domain else []
                        domain_list += expression.normalize_domain(domain)
                    return domain_list
        # standard
        global_domains = []  # list of domains
        rules = self._get_rules(model_name, mode=mode)
        if not rules:
            return expression.AND(global_domains) if global_domains else []
        # browse user and rules with sudo to avoid access errors!
        eval_context = self._eval_context()
        user_groups = self.env.user.groups_id
        group_domains = []  # list of domains
        for rule in rules.sudo():
            # evaluate the domain for the current user
            dom = safe_eval(rule.domain_force, eval_context) if rule.domain_force else []
            dom = expression.normalize_domain(dom)
            if not rule.groups:
                global_domains.append(dom)
            elif rule.groups & user_groups:
                group_domains.append(dom)
        # combine global domains and group domains
        if not group_domains:
            return expression.AND(global_domains)
        return expression.AND(global_domains + [expression.OR(group_domains)])

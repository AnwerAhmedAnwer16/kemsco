# models/maintenance_activity_line.py

from odoo import models, fields, api

class MaintenanceActivityLine(models.Model):
    _name = 'maintenance.activity.line'
    _description = 'Maintenance Activity Line'
    _order = 'sequence, id'

    task_id = fields.Many2one('project.task', string="Task", required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    
    activity_description = fields.Selection([
        ('oil_leakage', 'Check for any oil leakage'),
        ('coolant_level', 'Check coolant level'),
        ('oil_level', 'Check oil level'),
        ('fuel_level', 'Check fuel level'),
        ('fan_belt', 'Check fan belt tension'),
        ('water_pump', 'Check water pump for any leakage'),
        ('alternator_noise', 'Check alternator bearing noise'),
        ('battery_voltage', 'Check battery voltage'),
        ('battery_electrolyte', 'Check battery electrolyte level'),
        ('battery_terminal', 'Check battery terminal & clean'),
        ('electrical_connections', 'Check all electrical connections'),
        ('air_filter', 'Check air filter element'),
        ('engine_mounting', 'Check engine mounting bolts'),
        ('exhaust_system', 'Check exhaust system for leakage'),
        ('abnormal_noise', 'Run generator & check for abnormal noise'),
        ('voltage_frequency', 'Check voltage & frequency'),
        ('control_panel', 'Check control panel operation'),
        ('general_cleaning', 'General cleaning of generator'),
    ], string="Activity", required=True)

    # NEW: Computed field to show the user-friendly name
    display_activity = fields.Char(compute='_compute_display_activity', string='Activity')

    @api.depends('activity_description')
    def _compute_display_activity(self):
        for record in self:
            selection_map = dict(self._fields['activity_description'].selection)
            record.display_activity = selection_map.get(record.activity_description, '')

    remarks = fields.Text(string="Remarks")
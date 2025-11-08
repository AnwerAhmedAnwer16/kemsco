# models/checklist_line.py

from odoo import models, fields, api

class ChecklistLine(models.Model):
    _name = 'checklist.line'
    _description = 'Technical Report Checklist Line'
    _order = 'sequence, id'

    task_id = fields.Many2one('project.task', string="Task", required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    
    description = fields.Selection([
        ('fire_fighting_sys', 'Fire Fighting System'),
        ('sprinklers_sys', 'Sprinklers System'),
        ('fire_pump', 'Fire Pump'),
        ('fire_alarm_sys', 'Fire Alarm System'),
        ('smoke_detectors', 'Smoke Detectors'),
        ('heat_detectors', 'Heat Detectors'),
        ('fire_extinguishers', 'Fire Extinguishers'),
        ('hose_reel_cabinet', 'Fire Hose Reel Cabinet'),
        ('emergency_lights', 'Emergency Lights'),
        ('fire_mantel_cabinet', 'Fire Mantel / Cabinet'),
    ], string="Description", required=True)

    # NEW: Computed field to show the user-friendly name
    display_description = fields.Char(compute='_compute_display_description', string='Item')

    @api.depends('description')
    def _compute_display_description(self):
        for record in self:
            # Create a mapping from the selection options to get the nice name
            selection_map = dict(self._fields['description'].selection)
            record.display_description = selection_map.get(record.description, '')
    
    status = fields.Selection([
        ('ok', 'OK'),
        ('not_ok', 'Not OK'),
        ('na', 'N/A'),
    ], string="Status")
    
    remarks = fields.Text(string="Remarks")
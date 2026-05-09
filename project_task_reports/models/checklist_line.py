# models/checklist_line.py

from odoo import models, fields, api

class ChecklistLine(models.Model):
    _name = 'checklist.line'
    _description = 'Technical Report Checklist Line'
    _order = 'sequence, id'

    task_id = fields.Many2one('project.task', string="Task", required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    
    display_type = fields.Selection([
        ('line_section', 'Section'),
        ('line_note', 'Note'),
    ], default=False)
    
    name = fields.Char(string='Description')

    description = fields.Selection([
        # FIRE FIGHTING SYS.
        ('hose_reels', 'HOSE REELS SYS.'),
        ('sprinklers', 'SPRINKLERS SYS.'),
        ('dry_wet_riser', '(DRY & WET) RISER'),
        ('main_pumps', 'MAIN PUMPS'),
        ('jockey_pump', 'JOCKEY PUMP'),
        ('extinguishers', 'FIRE EXTINGUISHERS'),
        # FIRE ALARM SYS.
        ('alarm_panel', 'FIRE ALARM CONTROL PANEL'),
        ('call_points', 'CALL POINTS'),
        ('smoke_detectors', 'SMOKE DETECTORS'),
        ('heat_detectors', 'HEAT DETECTORS'),
        ('alarm_bells', 'ALARM BELLS'),
        # VENTILLATION SYS.
        ('smoke_van', 'SMOKE VAN'),
        ('fresh_air_van', 'FRESH AIR VAN'),
        # EMERG. LIGHTS SYS.
        ('exit_light', 'EXIT LIGHT'),
        ('emergency_light', 'EMERGENCY LIGHT'),
    ], string="Item")


    
    status = fields.Selection([
        ('ok', 'OK'),
        ('not_ok', 'Not OK'),
        ('na', 'N/A'),
    ], string="Status")
    
    remarks = fields.Text(string="Remarks")
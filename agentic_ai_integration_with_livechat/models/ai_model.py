from odoo import models, fields, api

class AgenticAIModel(models.Model):
    _name = 'agentic.ai.model'
    _description = 'AI Model Registry'
    _order = 'provider_type, name'

    name = fields.Char("Model Name", required=True, help="Technical model name (e.g., llama3, gpt-4)")
    display_name = fields.Char("Display Name", help="Human readable name (e.g., Llama 3, GPT-4)")
    provider_type = fields.Selection([
        ('ollama', 'Ollama'),
        ('openai', 'OpenAI'),
        ('claude', 'Anthropic Claude'),
        ('gemini', 'Google Gemini'),
        ('custom', 'Custom API')
    ], string="Provider Type", required=True)
    description = fields.Text("Description")
    is_active = fields.Boolean("Active", default=True)

    @api.depends('name', 'display_name')
    def _compute_display_name_field(self):
        for record in self:
            if record.display_name:
                record.complete_name = f"{record.display_name} ({record.name})"
            else:
                record.complete_name = record.name

    complete_name = fields.Char("Complete Name", compute='_compute_display_name_field', store=True)

    _sql_constraints = [
        ('unique_model_provider', 'unique(name, provider_type)', 'Model name must be unique per provider type!'),
    ]

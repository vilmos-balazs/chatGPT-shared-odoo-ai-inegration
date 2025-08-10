from odoo import models, fields, api
import json

class AgenticAIPromptRegistryView(models.TransientModel):
    _name = 'agentic.ai.prompt.registry.view'
    _description = 'View Registered AI Prompts (Readonly)'

    code = fields.Char("Prompt Code", readonly=True)
    name = fields.Char("Prompt Name", readonly=True)
    description = fields.Text("Description", readonly=True)
    category = fields.Char("Category", readonly=True)
    provider_type = fields.Char("Provider Type", readonly=True)
    channel = fields.Char("Channel", readonly=True)
    purpose = fields.Text("Purpose/When to Use", readonly=True)
    expected_input = fields.Text("Expected Input", readonly=True)
    expected_output = fields.Text("Expected Output", readonly=True)
    variables_json = fields.Text("Variables (JSON)", readonly=True)
    variables_display = fields.Html("Variables", readonly=True)
    prompt_template = fields.Text("Prompt Template", readonly=True)
    prompt_display = fields.Html("Prompt Template", readonly=True)
    python_class_exists = fields.Boolean("Python Class Exists", readonly=True)
    is_active = fields.Boolean("Active", readonly=True)
    is_custom = fields.Boolean("Custom", readonly=True)

    @api.model
    def get_registered_prompts(self):
        # Get prompts from persistent database
        prompt_metadata_records = self.env['agentic.ai.prompt.template'].search([])
        
        prompt_records = []
        for prompt_meta in prompt_metadata_records:
            # Format display fields
            variables = json.loads(prompt_meta.variables_json or '{}')
            variables_html = self._format_variables_html(variables)
            prompt_html = self._format_prompt_html(prompt_meta.prompt_template)

            record = {
                'code': prompt_meta.code,
                'name': prompt_meta.name,
                'description': prompt_meta.description,
                'category': prompt_meta.category,
                'provider_type': prompt_meta.provider_type,
                'channel': prompt_meta.channel,
                'purpose': prompt_meta.purpose,
                'expected_input': prompt_meta.expected_input,
                'expected_output': prompt_meta.expected_output,
                'variables_json': prompt_meta.variables_json,
                'variables_display': variables_html,
                'prompt_template': prompt_meta.prompt_template,
                'prompt_display': prompt_html,
                'python_class_exists': prompt_meta.python_class_exists,
                'is_active': prompt_meta.is_active,
                'is_custom': prompt_meta.is_custom,
            }
            prompt_records.append(record)
        return prompt_records

    @api.model
    def _format_variables_html(self, variables):
        if not variables:
            return "<p><em>No variables defined</em></p>"
        html = """
        <table class="table table-sm table-bordered">
            <thead class="table-light">
                <tr>
                    <th>Variable</th>
                    <th>Description</th>
                </tr>
            </thead>
            <tbody>
        """
        for var_name, var_desc in variables.items():
            html += f"""
                <tr>
                    <td><code>{{{var_name}}}</code></td>
                    <td>{var_desc}</td>
                </tr>
            """
        html += "</tbody></table>"
        return html

    @api.model
    def _format_prompt_html(self, prompt_template):
        if not prompt_template:
            return "<p><em>No prompt template defined</em></p>"
        
        # Format the prompt with syntax highlighting
        formatted_prompt = prompt_template.replace('\n', '<br/>')
        
        # Highlight variables
        import re
        formatted_prompt = re.sub(r'\{([^}]+)\}', r'<span class="badge badge-info">{<strong>\1</strong>}</span>', formatted_prompt)
        
        return f'<div class="bg-light p-3" style="border-left: 4px solid #007bff;"><pre style="white-space: pre-wrap; font-family: monospace;">{formatted_prompt}</pre></div>'

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        super(AgenticAIPromptRegistryView, self).search([]).unlink()
        prompts_data = self.get_registered_prompts()
        for prompt_data in prompts_data:
            self.create(prompt_data)
        return super(AgenticAIPromptRegistryView, self).search(args, offset=offset, limit=limit, order=order, count=count)

    def action_refresh_prompts(self):
        # First sync from Python
        self.env['agentic.ai.prompt.template'].load_new_prompts_only()
        
        # Then refresh the view
        super(AgenticAIPromptRegistryView, self).search([]).unlink()
        prompts_data = self.get_registered_prompts()
        for prompt_data in prompts_data:
            self.create(prompt_data)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Registered AI Prompts - Refreshed',
            'res_model': 'agentic.ai.prompt.registry.view',
            'view_mode': 'tree,form',
            'context': {},
            'target': 'current'
        }

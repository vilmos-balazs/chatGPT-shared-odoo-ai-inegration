from odoo import models, fields, api
import json

class AgenticAIPromptConfirmWizard(models.TransientModel):
    _name = 'agentic.ai.prompt.confirm.wizard'
    _description = 'Confirmation for Prompt Operations'

    message = fields.Text("Message", readonly=True)
    prompt_template_id = fields.Many2one('agentic.ai.prompt.template', string="Prompt Template")
    sync_all = fields.Boolean("Sync All Prompts", default=False)

    def action_confirm(self):
        """Execute the sync operation"""
        self.ensure_one()
        
        try:
            if self.sync_all:
                # Sync all prompts
                result = self.env['agentic.ai.prompt.template'].sync_from_python_registry()
                message = f"All prompts synced: {result['created']} created, {result['updated']} updated."
            elif self.prompt_template_id:
                # Sync single prompt
                template = self.prompt_template_id
                from ..models.agent_prompt_registry import get_prompt_registry
                
                registry = get_prompt_registry()
                prompt_class = None
                
                # Find the Python class
                for tc in registry.values():
                    prompt_instance = tc(self.env)
                    if prompt_instance.code == template.code:
                        prompt_class = tc
                        break
                
                if not prompt_class:
                    raise Exception(f"Python class for prompt '{template.code}' not found")
                
                # Sync the prompt
                prompt_instance = prompt_class(self.env)
                python_metadata = {
                    'name': prompt_instance.name,
                    'description': prompt_instance.description,
                    'category': prompt_instance.category,
                    'provider_type': prompt_instance.provider_type,
                    'channel': prompt_instance.channel,
                    'purpose': prompt_instance.purpose or '',
                    'expected_input': prompt_instance.expected_input or '',
                    'expected_output': prompt_instance.expected_output or '',
                    'variables_json': json.dumps(prompt_instance.variables, indent=2),
                    'prompt_template': prompt_instance.prompt_template,
                    'last_sync_date': fields.Datetime.now(),
                    'python_class_exists': True
                }
                
                template.write(python_metadata)
                message = f"Prompt '{template.name}' synced successfully!"
            else:
                message = "No operation specified"
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sync Complete!',
                    'message': message,
                    'type': 'success',
                    'sticky': True,
                }
            }
            
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sync Failed',
                    'message': f"Error: {str(e)}",
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_cancel(self):
        """Cancel the operation"""
        return {'type': 'ir.actions.act_window_close'}

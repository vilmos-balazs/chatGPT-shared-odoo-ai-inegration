from odoo import models, fields, api
import json
import logging

_logger = logging.getLogger(__name__)

class AgenticAIPromptLoaderWizard(models.TransientModel):
    _name = 'agentic.ai.prompt.loader.wizard'
    _description = 'Load New Prompts from Python Registry'

    message = fields.Html("Status", readonly=True, default="<p>Click the button below to load new prompts from Python registry.</p>")

    def action_load_new_prompts(self):
        """Load new prompts from Python registry"""
        try:
            from .agent_prompt_registry import get_prompt_registry
            
            registry = get_prompt_registry()
            existing_codes = set(self.env['agentic.ai.prompt.template'].search([]).mapped('code'))
            new_prompts_loaded = []
            
            for prompt_class in registry.values():
                prompt_instance = prompt_class(self.env)
                
                # Only create if it doesn't exist yet
                if prompt_instance.code not in existing_codes:
                    python_metadata = {
                        'code': prompt_instance.code,
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
                        'python_class_exists': True,
                        'is_custom': False
                    }
                    
                    self.env['agentic.ai.prompt.template'].create(python_metadata)
                    new_prompts_loaded.append(prompt_instance.name)
                    _logger.info(f"Loaded new prompt template: {prompt_instance.code}")
            
            if new_prompts_loaded:
                message = f"✅ Successfully loaded {len(new_prompts_loaded)} new prompts:<br/><ul>"
                for prompt_name in new_prompts_loaded:
                    message += f"<li>{prompt_name}</li>"
                message += "</ul>"
                notification_type = 'success'
                title = 'New Prompts Loaded'
            else:
                message = "ℹ️ No new prompts found. All prompts from Python registry are already loaded."
                notification_type = 'info'
                title = 'No New Prompts'
            
        except Exception as e:
            message = f"❌ Error loading prompts: {str(e)}"
            notification_type = 'danger'
            title = 'Load Failed'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': notification_type,
                'sticky': True,
            }
        }

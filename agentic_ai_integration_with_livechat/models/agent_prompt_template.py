from odoo import models, fields, api
import json
import logging

_logger = logging.getLogger(__name__)

class AgenticAIPromptTemplate(models.Model):
    _name = 'agentic.ai.prompt.template'
    _description = 'Persistent AI Prompt Templates (editable)'
    _order = 'category, sequence, code'

    # Core identification
    code = fields.Char("Template Code", required=True, index=True)
    name = fields.Char("Template Name", required=True)
    description = fields.Text("Description", required=True)
    category = fields.Selection([
        ('system', 'System Prompts'),
        ('function_calling', 'Function Calling'),
        ('rag', 'RAG Response Generation'),
        ('livechat', 'Livechat Specific'),
        ('internal', 'Internal Channel'),
        ('provider', 'Provider Specific'),
        ('orchestration', 'Tool Orchestration'),
        ('custom', 'Custom')
    ], string="Category", default='system', required=True)
    
    # Prompt content
    prompt_template = fields.Text("Prompt Template", required=True,
                                help="Use {variable_name} for placeholders")
    variables_json = fields.Text("Variables Schema (JSON)",
                               help="JSON schema defining available variables")
    
    # AI Context
    purpose = fields.Text("Purpose/When to Use",
                        help="When should this prompt template be used?")
    expected_input = fields.Text("Expected Input",
                               help="What kind of input does this prompt expect?")
    expected_output = fields.Text("Expected Output", 
                                help="What should the AI produce with this prompt?")
    
    # Configuration  
    provider_type = fields.Selection([
        ('all', 'All Providers'),
        ('ollama', 'Ollama'),
        ('openai', 'OpenAI'),
        ('claude', 'Anthropic Claude'),
        ('gemini', 'Google Gemini'),
        ('custom', 'Custom')
    ], string="Target Provider", default='all')
    
    channel = fields.Selection([
        ('all', 'All Channels'),
        ('livechat', 'Livechat Only'),
        ('internal', 'Internal Only')
    ], string="Target Channel", default='all')
    
    is_active = fields.Boolean("Active", default=True)
    sequence = fields.Integer("Sequence", default=10)
    
    # Tracking
    is_custom = fields.Boolean("Custom Template", default=False,
                             help="True if not defined in Python code")
    last_sync_date = fields.Datetime("Last Sync Date", readonly=True)
    python_class_exists = fields.Boolean("Python Definition Exists", readonly=True)
    
    _sql_constraints = [
        ('unique_template_code', 'unique(code)', 'Template code must be unique!')
    ]

    def render_template(self, **kwargs):
        """Render template with variables"""
        self.ensure_one()
        try:
            return self.prompt_template.format(**kwargs)
        except KeyError as e:
            _logger.error(f"Template {self.code} missing variable: {e}")
            return self.prompt_template

    @api.model
    def get_template(self, code, **kwargs):
        """Get and render a template by code"""
        template = self.search([('code', '=', code), ('is_active', '=', True)], limit=1)
        if not template:
            _logger.warning(f"Template '{code}' not found")
            return ""
        return template.render_template(**kwargs)

    def action_sync_single_from_python(self):
        """Show confirmation wizard before syncing single prompt"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Confirm Sync from Python',
            'res_model': 'agentic.ai.prompt.confirm.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_prompt_template_id': self.id,
                'default_message': f'Are you sure you want to sync "{self.name}" from Python? This will overwrite your customizations!'
            }
        }

    def action_sync_all_from_python(self):
        """Show confirmation wizard before syncing all prompts - FIXED for tree view"""
        # This method can be called from tree view (with recordset) or as model method
        return {
            'type': 'ir.actions.act_window',
            'name': 'Confirm Sync All from Python',
            'res_model': 'agentic.ai.prompt.confirm.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sync_all': True,
                'default_message': 'Are you sure you want to sync ALL prompts from Python? This will overwrite ALL your customizations!'
            }
        }

    @api.model
    def load_new_prompts_only(self):
        """🔍 SMART: Load only NEW prompts that don't exist in database yet"""
        from .agent_prompt_registry import get_prompt_registry
        
        registry = get_prompt_registry()
        existing_codes = set(self.search([]).mapped('code'))
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
                
                self.create(python_metadata)
                new_prompts_loaded.append(prompt_instance.name)
                _logger.info(f"Loaded new prompt template: {prompt_instance.code}")
        
        return {
            'new_loaded': len(new_prompts_loaded),
            'new_prompt_names': new_prompts_loaded
        }

    @api.model
    def sync_from_python_registry(self):
        """⚠️ DESTRUCTIVE: Sync ALL prompts, overwriting customizations"""
        from .agent_prompt_registry import get_prompt_registry
        
        registry = get_prompt_registry()
        synced_count = 0
        created_count = 0
        
        for prompt_class in registry.values():
            prompt_instance = prompt_class(self.env)
            existing = self.search([('code', '=', prompt_instance.code)], limit=1)
            
            # Prepare metadata from Python class
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
            
            if not existing:
                # Create new record
                self.create(python_metadata)
                created_count += 1
                _logger.info(f"Created prompt template: {prompt_instance.code}")
            else:
                # FORCE OVERWRITE existing customizations
                existing.write(python_metadata)
                synced_count += 1
        
        return {
            'created': created_count,
            'updated': synced_count
        }

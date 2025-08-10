from odoo import models, fields, api
import json
import logging

_logger = logging.getLogger(__name__)

class AgenticAIToolLoaderWizard(models.TransientModel):
    _name = 'agentic.ai.tool.loader.wizard'
    _description = 'Load New Tools from Python Registry'

    message = fields.Html("Status", readonly=True, default="<p>Click the button below to load new tools from Python registry.</p>")

    def action_load_new_tools(self):
        """Load new tools from Python registry"""
        try:
            from .agent_tool import get_registry
            
            registry = get_registry()
            existing_codes = set(self.env['agentic.ai.tool.metadata'].search([]).mapped('code'))
            new_tools_loaded = []
            
            for tool_class in registry.values():
                # Only create if it doesn't exist yet
                if tool_class.code not in existing_codes:
                    python_metadata = {
                        'code': tool_class.code,
                        'name': tool_class.name,
                        'description': tool_class.description,
                        'category': getattr(tool_class, 'category', 'general'),
                        'keywords': ', '.join(getattr(tool_class, 'keywords', [])),
                        'ai_usage_context': self.env['agentic.ai.tool.metadata']._generate_ai_context(tool_class),
                        'parameters_json': json.dumps(getattr(tool_class, 'parameters', {}), indent=2),
                        'examples_json': json.dumps(getattr(tool_class, 'examples', []), indent=2),
                        'output_format_json': json.dumps(getattr(tool_class, 'output_format', {}), indent=2),
                        'timeout': getattr(tool_class, 'timeout', 30),
                        'requires_auth': getattr(tool_class, 'requires_auth', False),
                        'last_sync_date': fields.Datetime.now(),
                        'python_class_exists': True,
                        'is_custom': False
                    }
                    
                    self.env['agentic.ai.tool.metadata'].create(python_metadata)
                    new_tools_loaded.append(tool_class.name)
                    _logger.info(f"Loaded new tool: {tool_class.code}")
            
            if new_tools_loaded:
                message = f"✅ Successfully loaded {len(new_tools_loaded)} new tools:<br/><ul>"
                for tool_name in new_tools_loaded:
                    message += f"<li>{tool_name}</li>"
                message += "</ul>"
                notification_type = 'success'
                title = 'New Tools Loaded'
            else:
                message = "ℹ️ No new tools found. All tools from Python registry are already loaded."
                notification_type = 'info'
                title = 'No New Tools'
            
        except Exception as e:
            message = f"❌ Error loading tools: {str(e)}"
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

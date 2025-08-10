from odoo import models, fields, api
import json
import logging

_logger = logging.getLogger(__name__)

class AgenticAIToolMetadata(models.Model):
    _name = 'agentic.ai.tool.metadata'
    _description = 'Persistent AI Tool Metadata (editable)'
    _order = 'category, sequence, code'

    # Core identification
    code = fields.Char("Tool Code", required=True, index=True)
    name = fields.Char("Tool Name", required=True)
    description = fields.Text("Description", required=True)
    category = fields.Selection([
        ('product', 'Product'),
        ('inventory', 'Inventory'),
        ('general', 'General'),
        ('crm', 'CRM'),
        ('sales', 'Sales'),
        ('purchase', 'Purchase'),
        ('accounting', 'Accounting'),
        ('meilisearch', 'MeiliSearch'),
        ('custom', 'Custom')
    ], string="Category", default='general', required=True)
    
    # AI Orchestration metadata (most important)
    keywords = fields.Text("Keywords (comma-separated)", 
                          help="Keywords that help AI decide when to use this tool")
    ai_usage_context = fields.Text("AI Usage Context", 
                                 help="When should the AI use this tool? Be specific.")
    ai_orchestration_priority = fields.Integer("AI Priority", default=50,
                                             help="Priority for AI selection (1-100, higher = more likely to be chosen)")
    
    # Technical metadata  
    parameters_json = fields.Text("Parameters Schema (JSON)", 
                                help="JSON schema for tool parameters")
    examples_json = fields.Text("Examples (JSON)",
                              help="Usage examples for the AI agent")
    output_format_json = fields.Text("Output Format (JSON)",
                                   help="Expected output structure")
    
    # Configuration
    timeout = fields.Integer("Timeout (seconds)", default=30)
    requires_auth = fields.Boolean("Requires Authentication", default=False)
    is_active = fields.Boolean("Active", default=True)
    sequence = fields.Integer("Sequence", default=10)
    
    # Tracking
    is_custom = fields.Boolean("Custom Tool", default=False,
                             help="True if this tool is not defined in Python code")
    last_sync_date = fields.Datetime("Last Sync Date", readonly=True)
    python_class_exists = fields.Boolean("Python Class Exists", readonly=True)
    
    _sql_constraints = [
        ('unique_tool_code', 'unique(code)', 'Tool code must be unique!')
    ]

    @api.model
    def load_new_tools_only(self):
        """🔍 SMART: Load only NEW tools that don't exist in database yet"""
        from .agent_tool import get_registry
        
        registry = get_registry()
        existing_codes = set(self.search([]).mapped('code'))
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
                    'ai_usage_context': self._generate_ai_context(tool_class),
                    'parameters_json': json.dumps(getattr(tool_class, 'parameters', {}), indent=2),
                    'examples_json': json.dumps(getattr(tool_class, 'examples', []), indent=2),
                    'output_format_json': json.dumps(getattr(tool_class, 'output_format', {}), indent=2),
                    'timeout': getattr(tool_class, 'timeout', 30),
                    'requires_auth': getattr(tool_class, 'requires_auth', False),
                    'last_sync_date': fields.Datetime.now(),
                    'python_class_exists': True,
                    'is_custom': False
                }
                
                self.create(python_metadata)
                new_tools_loaded.append(tool_class.name)
                _logger.info(f"Loaded new tool: {tool_class.code}")
        
        return {
            'new_loaded': len(new_tools_loaded),
            'new_tool_names': new_tools_loaded
        }

    @api.model
    def sync_from_python_registry(self):
        """
        ⚠️ DESTRUCTIVE: Sync ALL tools, overwriting customizations
        🌍 ENHANCED: Now syncs multilingual examples and parameters
        """
        from .agent_tool import get_registry
        
        registry = get_registry()
        synced_count = 0
        created_count = 0
        
        for tool_class in registry.values():
            existing = self.search([('code', '=', tool_class.code)], limit=1)
            
            # Prepare metadata from Python class
            python_metadata = {
                'code': tool_class.code,
                'name': tool_class.name,
                'description': tool_class.description,
                'category': getattr(tool_class, 'category', 'general'),
                'keywords': ', '.join(getattr(tool_class, 'keywords', [])),
                'ai_usage_context': self._generate_ai_context(tool_class),
                'parameters_json': json.dumps(getattr(tool_class, 'parameters', {}), indent=2),
                'examples_json': json.dumps(getattr(tool_class, 'examples', []), indent=2),
                'output_format_json': json.dumps(getattr(tool_class, 'output_format', {}), indent=2),
                'timeout': getattr(tool_class, 'timeout', 30),
                'requires_auth': getattr(tool_class, 'requires_auth', False),
                'last_sync_date': fields.Datetime.now(),
                'python_class_exists': True,
                'is_custom': False
            }
            
            if not existing:
                # Create new record
                self.create(python_metadata)
                created_count += 1
                _logger.info(f"Created tool metadata: {tool_class.code}")
            else:
                # FORCE OVERWRITE existing customizations
                existing.write(python_metadata)
                synced_count += 1
        
        # Mark tools that no longer exist in Python
        all_python_codes = [tool.code for tool in registry.values()]
        orphaned = self.search([
            ('python_class_exists', '=', True),
            ('code', 'not in', all_python_codes)
        ])
        orphaned.write({'python_class_exists': False})
        
        _logger.info(f"🌍 Multilingual tool sync complete: {created_count} created, {synced_count} updated")
        return {
            'created': created_count,
            'updated': synced_count,
            'orphaned': len(orphaned)
        }

    @api.model  
    def _generate_ai_context(self, tool_class):
        """🌍 ENHANCED: Generate multilingual AI usage context from tool metadata"""
        context_parts = []
        
        if hasattr(tool_class, 'description'):
            context_parts.append(f"Purpose: {tool_class.description}")
            
        if hasattr(tool_class, 'keywords') and tool_class.keywords:
            # 🌍 Include multilingual keywords
            keywords_str = ', '.join(tool_class.keywords)
            context_parts.append(f"Use when user mentions: {keywords_str}")
            context_parts.append("Supports multilingual input (English, Romanian, Hungarian)")
            
        if hasattr(tool_class, 'category'):
            context_parts.append(f"Category: {tool_class.category} operations")
        
        # 🌍 Add language support note
        context_parts.append("Language: Automatically detects and responds in user's language (en_US, ro_RO, hu_HU)")
            
        return " | ".join(context_parts) if context_parts else "General purpose multilingual tool"

    def get_tool_for_ai(self):
        """
        🌍 ENHANCED: Get tool metadata formatted for AI agent consumption with language support
        """
        self.ensure_one()
        
        return {
            'code': self.code,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'keywords': [kw.strip() for kw in (self.keywords or '').split(',') if kw.strip()],
            'ai_usage_context': self.ai_usage_context,
            'priority': self.ai_orchestration_priority,
            'parameters': json.loads(self.parameters_json or '{}'),
            'timeout': self.timeout,
            'requires_auth': self.requires_auth,
            'multilingual': True,  # 🌍 LANGUAGE CAPABILITY FLAG
            'supported_languages': ['en_US', 'ro_RO', 'hu_HU']  # 🌍 SUPPORTED LANGUAGES
        }

    @api.model
    def get_active_tools_for_ai(self, category=None):
        """
        🌍 ENHANCED: Get all active tools formatted for AI consumption with language metadata
        """
        domain = [('is_active', '=', True)]
        if category:
            domain.append(('category', '=', category))
            
        tools = self.search(domain, order='ai_orchestration_priority desc, sequence')
        return [tool.get_tool_for_ai() for tool in tools]

    @api.model
    def create_custom_tool(self, code, name, description, **kwargs):
        """
        🌍 ENHANCED: Create a custom tool (not backed by Python class) with language support
        """
        data = {
            'code': code,
            'name': name,
            'description': description,
            'is_custom': True,
            'python_class_exists': False,
            **kwargs
        }
        return self.create(data)

    def action_sync_from_python(self):
        """Show confirmation wizard before syncing single tool"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Confirm Sync from Python',
            'res_model': 'agentic.ai.tool.sync.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sync_type': 'single',
                'default_tool_metadata_id': self.id
            }
        }

    def action_sync_all_from_python(self):
        """Show confirmation wizard before syncing all tools - FIXED for tree view"""
        # This method can be called from tree view (with recordset) or as model method
        return {
            'type': 'ir.actions.act_window',
            'name': 'Confirm Sync All from Python',
            'res_model': 'agentic.ai.tool.sync.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sync_type': 'all'
            }
        }

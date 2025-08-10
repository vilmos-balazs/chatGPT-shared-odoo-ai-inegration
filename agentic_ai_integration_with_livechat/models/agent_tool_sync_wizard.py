from odoo import models, fields, api
import json

class AgenticAIToolSyncWizard(models.TransientModel):
    _name = 'agentic.ai.tool.sync.wizard'
    _description = 'Confirmation Wizard for Tool Sync from Python'

    message = fields.Html("Warning Message", readonly=True)
    sync_type = fields.Selection([
        ('all', 'Sync All Tools'),
        ('single', 'Sync Single Tool')
    ], required=True, readonly=True)
    tool_metadata_id = fields.Many2one('agentic.ai.tool.metadata', string="Tool to Sync", readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        # Build warning message
        warning_html = """
        <div class="alert alert-warning">
            <h4><i class="fa fa-warning"></i> Warning: Sync from Python Registry</h4>
            <p><strong>This action will overwrite your customizations!</strong></p>
            
            <p>The following user-modified fields will be <strong>reset to Python development defaults</strong>:</p>
            <ul>
                <li><strong>Keywords</strong> - Your custom keywords will be replaced</li>
                <li><strong>AI Usage Context</strong> - Your custom AI instructions will be lost</li>
                <li><strong>Description</strong> - Will revert to original Python description</li>
                <li><strong>Parameters Schema</strong> - Technical parameters from Python class</li>
                <li><strong>Examples</strong> - Usage examples from Python class</li>
                <li><strong>Output Format</strong> - Expected output structure from Python class</li>
            </ul>
            
            <p><strong>Fields that will be preserved:</strong></p>
            <ul>
                <li>AI Orchestration Priority</li>
                <li>Active/Inactive status</li>
                <li>Sequence order</li>
            </ul>
            
            <hr/>
            <p class="text-danger"><strong>⚠️ This action cannot be undone!</strong></p>
            <p>Make sure you have backed up any important customizations before proceeding.</p>
        </div>
        """
        
        res['message'] = warning_html
        return res

    def action_confirm_sync(self):
        """Perform the actual sync after user confirmation"""
        self.ensure_one()
        
        try:
            if self.sync_type == 'single' and self.tool_metadata_id:
                # Sync single tool
                result = self._sync_single_tool(self.tool_metadata_id)
                message = f"Tool '{self.tool_metadata_id.name}' synced successfully from Python registry."
                notification_type = 'success'
                title = 'Sync Complete'
            else:
                # Sync all tools
                result = self.env['agentic.ai.tool.metadata'].sync_from_python_registry()
                message = f"Sync complete: {result['created']} created, {result['updated']} updated, {result['orphaned']} orphaned."
                notification_type = 'success'
                title = 'Sync Complete'
                
        except Exception as e:
            message = f"Sync failed: {str(e)}"
            notification_type = 'danger'
            title = 'Sync Failed'
        
        # Return notification and close wizard
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': notification_type,
                'sticky': False,
            },
            'effect': {
                'fadeout': 'slow',
                'type': 'rainbow_man' if notification_type == 'success' else None
            }
        }

    def _sync_single_tool(self, tool_metadata):
        """Sync a single tool from Python registry"""
        from .agent_tool import get_registry
        
        registry = get_registry()
        tool_class = None
        
        # Find the Python class
        for tc in registry.values():
            if tc.code == tool_metadata.code:
                tool_class = tc
                break
        
        if not tool_class:
            raise Exception(f"Python class for tool '{tool_metadata.code}' not found in registry")
        
        # Prepare metadata from Python class
        python_metadata = {
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
            'python_class_exists': True
        }
        
        tool_metadata.write(python_metadata)
        return {'updated': 1}

    def action_cancel_sync(self):
        """Cancel sync operation"""
        return {'type': 'ir.actions.act_window_close'}

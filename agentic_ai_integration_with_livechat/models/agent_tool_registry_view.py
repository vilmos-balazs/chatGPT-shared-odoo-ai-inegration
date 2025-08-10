from odoo import models, fields, api
import json

class AgenticAIToolRegistryView(models.TransientModel):
    _name = 'agentic.ai.tool.registry.view'
    _description = 'View Registered AI Tools'

    code = fields.Char("Tool Code", readonly=True)
    name = fields.Char("Tool Name", readonly=True)
    description = fields.Text("Description", readonly=True)
    category = fields.Char("Category", readonly=True)
    keywords = fields.Char("Keywords", readonly=True)
    ai_usage_context = fields.Text("AI Usage Context", readonly=True)
    ai_orchestration_priority = fields.Integer("AI Priority", readonly=True)
    parameters_json = fields.Text("Parameters (JSON)", readonly=True)
    parameters_display = fields.Html("Parameters", readonly=True)
    examples_json = fields.Text("Examples (JSON)", readonly=True)
    examples_display = fields.Html("Examples", readonly=True)
    output_format_json = fields.Text("Output Format (JSON)", readonly=True)
    output_format_display = fields.Html("Output Format", readonly=True)
    function_schema_json = fields.Text("Function Schema (JSON)", readonly=True)
    function_schema_display = fields.Html("Function Schema", readonly=True)
    timeout = fields.Integer("Timeout (seconds)", readonly=True)
    requires_auth = fields.Boolean("Requires Authentication", readonly=True)
    python_class_exists = fields.Boolean("Python Class Exists", readonly=True)
    is_active = fields.Boolean("Active", readonly=True)

    @api.model
    def get_registered_tools(self):
        # Get tools from persistent database instead of Python registry
        tool_metadata_records = self.env['agentic.ai.tool.metadata'].search([])
        
        from .agent_tool import get_registry
        registry = get_registry()
        
        tool_records = []
        for tool_meta in tool_metadata_records:
            # Try to get function schema from Python class if it exists
            function_schema = {}
            if tool_meta.python_class_exists and tool_meta.code in [t.code for t in registry.values()]:
                try:
                    tool_instance = registry.get_tool(tool_meta.code, self.env)
                    function_schema = tool_instance.get_function_schema()
                except:
                    pass
            
            # Format display fields
            parameters = json.loads(tool_meta.parameters_json or '{}')
            examples = json.loads(tool_meta.examples_json or '[]')
            output_format = json.loads(tool_meta.output_format_json or '{}')
            
            parameters_html = self._format_parameters_html(parameters)
            examples_html = self._format_examples_html(examples)
            output_format_html = self._format_json_html(output_format)
            function_schema_html = self._format_json_html(function_schema)

            record = {
                'code': tool_meta.code,
                'name': tool_meta.name,
                'description': tool_meta.description,
                'category': tool_meta.category,
                'keywords': tool_meta.keywords,
                'ai_usage_context': tool_meta.ai_usage_context,
                'ai_orchestration_priority': tool_meta.ai_orchestration_priority,
                'parameters_json': tool_meta.parameters_json,
                'parameters_display': parameters_html,
                'examples_json': tool_meta.examples_json,
                'examples_display': examples_html,
                'output_format_json': tool_meta.output_format_json,
                'output_format_display': output_format_html,
                'function_schema_json': json.dumps(function_schema, indent=2),
                'function_schema_display': function_schema_html,
                'timeout': tool_meta.timeout,
                'requires_auth': tool_meta.requires_auth,
                'python_class_exists': tool_meta.python_class_exists,
                'is_active': tool_meta.is_active,
            }
            tool_records.append(record)
        return tool_records

    @api.model
    def _format_parameters_html(self, parameters):
        if not parameters:
            return "<p><em>No parameters defined</em></p>"
        html = """
        <table class="table table-sm table-bordered">
            <thead class="table-light">
                <tr>
                    <th>Parameter</th>
                    <th>Type</th>
                    <th>Required</th>
                    <th>Description</th>
                    <th>Options</th>
                </tr>
            </thead>
            <tbody>
        """
        for param_name, param_def in parameters.items():
            required = "✓" if param_def.get('required', False) else ""
            param_type = param_def.get('type', 'string')
            description = param_def.get('description', '')
            options = ""
            if 'enum' in param_def:
                options = f"Options: {', '.join(param_def['enum'])}"
            html += f"""
                <tr>
                    <td><code>{param_name}</code></td>
                    <td><span class="badge badge-info">{param_type}</span></td>
                    <td class="text-center">{'<span class="text-success">✓</span>' if required else ''}</td>
                    <td>{description}</td>
                    <td><small>{options}</small></td>
                </tr>
            """
        html += "</tbody></table>"
        return html

    @api.model
    def _format_examples_html(self, examples):
        if not examples:
            return "<p><em>No examples provided</em></p>"
        html = ""
        for i, example in enumerate(examples, 1):
            html += f"""
            <div class="card mb-2">
                <div class="card-header">
                    <strong>Example {i}: {example.get('description', 'Usage example')}</strong>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <h6>Input:</h6>
                            <pre class="bg-light p-2"><code>{json.dumps(example.get('input', {}), indent=2)}</code></pre>
                        </div>
                        <div class="col-md-6">
                            <h6>Output:</h6>
                            <pre class="bg-light p-2"><code>{json.dumps(example.get('output', {}), indent=2)}</code></pre>
                        </div>
                    </div>
                </div>
            </div>
            """
        return html

    @api.model
    def _format_json_html(self, json_data):
        if not json_data:
            return "<p><em>Not defined</em></p>"
        return f'<pre class="bg-light p-3"><code>{json.dumps(json_data, indent=2)}</code></pre>'

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        super(AgenticAIToolRegistryView, self).search([]).unlink()
        tools_data = self.get_registered_tools()
        for tool_data in tools_data:
            self.create(tool_data)
        return super(AgenticAIToolRegistryView, self).search(args, offset=offset, limit=limit, order=order, count=count)

    def action_refresh_tools(self):
        # First sync from Python
        self.env['agentic.ai.tool.metadata'].sync_from_python_registry()
        
        # Then refresh the view
        super(AgenticAIToolRegistryView, self).search([]).unlink()
        tools_data = self.get_registered_tools()
        for tool_data in tools_data:
            self.create(tool_data)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Registered AI Tools - Refreshed',
            'res_model': 'agentic.ai.tool.registry.view',
            'view_mode': 'tree,form',
            'context': {},
            'target': 'current'
        }

class AgenticAIToolTest(models.TransientModel):
    _name = 'agentic.ai.tool.test'
    _description = 'Test Individual AI Tools'

    tool_code = fields.Selection(selection='_get_tool_codes', string="Tool to Test", required=True)
    parameters_input = fields.Text("Parameters (JSON)", help="Enter parameters as JSON, e.g., {\"query\": \"laptop\", \"limit\": 5}")
    test_result = fields.Text("Test Result", readonly=True)
    test_status = fields.Selection([
        ('pending', 'Ready to Test'),
        ('success', 'Success'), 
        ('error', 'Error')
    ], default='pending', readonly=True)

    @api.model
    def _get_tool_codes(self):
        try:
            # Get from persistent metadata
            tools = self.env['agentic.ai.tool.metadata'].search([('is_active', '=', True)])
            return [(tool.code, f"{tool.name} ({tool.code})") for tool in tools]
        except:
            return [('no_tools', 'No tools available')]

    def action_test_tool(self):
        self.ensure_one()
        try:
            from .agent_tool import get_registry
            if self.parameters_input:
                try:
                    params = json.loads(self.parameters_input)
                except json.JSONDecodeError as e:
                    self.test_result = f"Invalid JSON parameters: {str(e)}"
                    self.test_status = 'error'
                    return self._return_form_view()
            else:
                params = {}
            registry = get_registry()
            tool = registry.get_tool(self.tool_code, self.env)
            result = tool.call(**params)
            self.test_result = json.dumps(result, indent=2, ensure_ascii=False)
            self.test_status = 'success'
        except Exception as e:
            self.test_result = f"Error: {str(e)}"
            self.test_status = 'error'
        return self._return_form_view()

    def _return_form_view(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'agentic.ai.tool.test',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

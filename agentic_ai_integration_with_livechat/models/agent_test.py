from odoo import models, fields, api

class AgenticAITestWizard(models.TransientModel):
    _name = "agentic.ai.test.wizard"
    _description = "Test Agentic AI Agent from Backend"

    user_message = fields.Text("User Message", required=True)
    agent_answer = fields.Text("Agent Answer", readonly=True)
    prompt_used = fields.Char("Prompt Template Used", readonly=True)
    function_calls_made = fields.Integer("Function Calls Made", readonly=True)
    function_calling_used = fields.Boolean("Function Calling Used", readonly=True)
    language_detected = fields.Char("Language Detected", readonly=True)
    execution_details = fields.Text("Execution Details", readonly=True)
    channel = fields.Selection([
        ('livechat', 'Livechat (Business Only)'),
        ('internal', 'Internal (Unrestricted)')
    ], string="Test Channel", default='livechat')

    def action_test_agent(self):
        self.ensure_one()
        agent = self.env['agentic.ai.agent']
        result = agent.ask(self.user_message, channel=self.channel)
        
        # 🎯 ENHANCED: Display comprehensive function calling results
        self.agent_answer = result.get('answer')
        self.prompt_used = result.get('prompt_used', 'Unknown')
        self.function_calls_made = result.get('function_calls_made', 0)
        self.function_calling_used = result.get('function_calling_used', False)
        self.language_detected = result.get('language', 'en_US')
        
        # 📊 BUILD DETAILED EXECUTION REPORT
        execution_details = []
        execution_details.append(f"🌍 Language: {result.get('language')} ({result.get('language_detection_method', 'unknown')})")
        execution_details.append(f"🤖 Provider: {result.get('provider', 'Unknown')}")
        execution_details.append(f"📍 Channel: {result.get('channel', 'unknown')}")
        execution_details.append(f"🛠️ Tools Available: {result.get('tools_available', 0)}")
        execution_details.append(f"⚡ Function Calling: {'Yes' if result.get('function_calling_used') else 'No'}")
        
        if result.get('function_calling_used'):
            execution_details.append(f"🔧 Function Calls Made: {result.get('function_calls_made', 0)}")
            
            # Show function call details
            if result.get('function_calls'):
                execution_details.append("\n🛠️ Function Calls Details:")
                for i, call in enumerate(result.get('function_calls', []), 1):
                    execution_details.append(f"  {i}. {call.get('tool')}({', '.join(f'{k}={v}' for k, v in call.get('parameters', {}).items())})")
            
            # Show function results summary
            if result.get('function_results'):
                execution_details.append("\n📊 Function Results:")
                for i, res in enumerate(result.get('function_results', []), 1):
                    status = "✅ Success" if res.get('success') else "❌ Error"
                    execution_details.append(f"  {i}. {res.get('tool')}: {status}")
                    if not res.get('success') and res.get('error'):
                        execution_details.append(f"     Error: {res.get('error')}")
        
        # 🤖 AI RAW RESPONSE (if available)
        if result.get('ai_raw_response'):
            ai_raw = result.get('ai_raw_response')
            if len(ai_raw) > 200:
                ai_raw = ai_raw[:200] + "..."
            execution_details.append(f"\n🤖 AI Raw Response: {ai_raw}")
        
        self.execution_details = "\n".join(execution_details)
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'agentic.ai.test.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

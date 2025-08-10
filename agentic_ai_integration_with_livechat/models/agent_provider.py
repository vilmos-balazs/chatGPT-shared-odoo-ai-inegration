from odoo import models, fields, api
from abc import ABC, abstractmethod
import requests
import json
import logging

_logger = logging.getLogger(__name__)

# Abstract Base Class
class AbstractAIProvider(ABC):
    def __init__(self, provider_record):
        self.provider_record = provider_record
        self.env = provider_record.env

    @abstractmethod
    def complete(self, prompt, history=None, tools=None, lang="en"):
        """Generate completion based on provider implementation"""
        pass

    @abstractmethod
    def complete_language_detection(self, prompt):
        """🎯 NEW: Isolated language detection without system prompts"""
        pass

# Concrete Provider Classes
class OllamaProvider(AbstractAIProvider):
    def complete(self, prompt, history=None, tools=None, lang="en"):
        """
        🛠️ FIXED: Ollama completion that respects function calling prompts
        """
        try:
            # 🛠️ DETECT FUNCTION CALLING PROMPTS
            is_function_calling = "FUNCTION_CALL" in prompt and "🎯 FUNCTION CALLING INSTRUCTIONS" in prompt
            
            if is_function_calling:
                # 🎯 FUNCTION CALLING MODE: Use the prompt as-is (it's already complete)
                messages = [
                    {"role": "user", "content": prompt}
                ]
                _logger.info("🛠️ Function calling mode: Using prompt as-is")
            else:
                # 🗣️ NORMAL MODE: Extract user message and add system message
                user_message = "Hello"
                if "User message:" in prompt:
                    user_message = prompt.split("User message:")[1].split("Channel:")[0].strip()
                elif "Customer message:" in prompt:
                    user_message = prompt.split("Customer message:")[1].strip()
                elif "Team member request:" in prompt:
                    user_message = prompt.split("Team member request:")[1].strip()
                
                # Use database prompt template for normal system message
                tools_list = [t['code'] for t in tools] if tools else ['none']
                
                system_msg = self.env['agentic.ai.prompt.template'].get_template(
                    'ollama_provider_system',
                    tools_list=tools_list,
                    lang=lang
                )
                
                # Fallback if template not found
                if not system_msg:
                    system_msg = f"You are a helpful AI assistant for Odoo ERP system. Available tools: {tools_list}. Language: {lang}. Be concise and helpful."
                
                messages = [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_message}
                ]
                _logger.info("🗣️ Normal mode: Using system + user messages")
            
            if history:
                messages.extend(history)
            
            # 🎯 DATABASE DRIVEN: Use provider's max_tokens and temperature settings
            max_tokens = self.provider_record.max_tokens
            temperature = self.provider_record.temperature
            
            _logger.info(f"🎯 Using database settings: max_tokens={max_tokens}, temperature={temperature}")
            
            # API request
            payload = {
                "model": self.provider_record.model_name.name,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            
            response = requests.post(
                self.provider_record.endpoint_url,
                json=payload,
                timeout=self.provider_record.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result.get("message", {}).get("content", "Sorry, I couldn't generate a response.")
                
                if is_function_calling:
                    _logger.info(f"🛠️ Function calling response: '{ai_response}'")
                
                return ai_response
            else:
                _logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                return f"Error connecting to AI model (HTTP {response.status_code})"
                
        except requests.RequestException as e:
            _logger.error(f"Ollama connection error: {str(e)}")
            return f"Error: Cannot connect to Ollama server at {self.provider_record.endpoint_url}"
        except Exception as e:
            _logger.error(f"Ollama provider error: {str(e)}")
            return f"AI Error: {str(e)}"

    def complete_language_detection(self, prompt):
        """🎯 ISOLATED LANGUAGE DETECTION: No system prompts, minimal context"""
        try:
            _logger.info("🎯 ISOLATED LANGUAGE DETECTION CALL")
            
            # 🎯 MINIMAL CONTEXT: Only user message, no system prompts
            messages = [
                {"role": "user", "content": prompt}
            ]
            
            # �� MINIMAL SETTINGS: Lower temperature for consistency
            payload = {
                "model": self.provider_record.model_name.name,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Very low temperature for consistent detection
                    "num_predict": 10     # Very short response expected
                }
            }
            
            response = requests.post(
                self.provider_record.endpoint_url,
                json=payload,
                timeout=15  # Shorter timeout for language detection
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result.get("message", {}).get("content", "en_US")
                _logger.info(f"🎯 Isolated detection response: '{ai_response}'")
                return ai_response
            else:
                _logger.error(f"Language detection API error: {response.status_code}")
                return "en_US"
                
        except Exception as e:
            _logger.error(f"Language detection error: {str(e)}")
            return "en_US"

class OpenAIProvider(AbstractAIProvider):
    def complete(self, prompt, history=None, tools=None, lang="en"):
        return f"[OpenAI {self.provider_record.model_name.name}] Provider not implemented yet."

    def complete_language_detection(self, prompt):
        return "en_US"  # Fallback for unimplemented providers

class ClaudeProvider(AbstractAIProvider):
    def complete(self, prompt, history=None, tools=None, lang="en"):
        return f"[Claude {self.provider_record.model_name.name}] Provider not implemented yet."

    def complete_language_detection(self, prompt):
        return "en_US"  # Fallback for unimplemented providers

class GeminiProvider(AbstractAIProvider):
    def complete(self, prompt, history=None, tools=None, lang="en"):
        return f"[Gemini {self.provider_record.model_name.name}] Provider not implemented yet."

    def complete_language_detection(self, prompt):
        return "en_US"  # Fallback for unimplemented providers

# Provider Factory
class ProviderFactory:
    _providers = {
        'ollama': OllamaProvider,
        'openai': OpenAIProvider,
        'claude': ClaudeProvider,
        'gemini': GeminiProvider,
    }
    
    @classmethod
    def create_provider(cls, provider_record):
        provider_class = cls._providers.get(provider_record.provider_type)
        if not provider_class:
            raise ValueError(f"Unknown provider type: {provider_record.provider_type}")
        return provider_class(provider_record)

# Database Model (Configuration Only)
class AgenticAIProvider(models.Model):
    _name = 'agentic.ai.provider'
    _description = 'Agentic AI Provider Configuration'
    _order = 'sequence, name'

    name = fields.Char("Provider Name", required=True)
    code = fields.Char("Provider Code", required=True)
    description = fields.Text("Description")
    provider_type = fields.Selection([
        ('ollama', 'Ollama'),
        ('openai', 'OpenAI'),
        ('claude', 'Anthropic Claude'),
        ('gemini', 'Google Gemini'),
        ('custom', 'Custom API')
    ], string="Provider Type", required=True)
    
    # Connection settings
    endpoint_url = fields.Char("API Endpoint URL", required=True)
    api_key = fields.Char("API Key")
    
    # Model selection
    model_name = fields.Many2one('agentic.ai.model', string="AI Model", required=True, domain="[('provider_type', '=', provider_type), ('is_active', '=', True)]")
    
    # Configuration
    is_default = fields.Boolean("Default Provider")
    is_active = fields.Boolean("Active", default=True)
    sequence = fields.Integer("Sequence", default=10)
    timeout = fields.Integer("Timeout (seconds)", default=30)
    
    # Advanced settings
    temperature = fields.Float("Temperature", default=0.7)
    max_tokens = fields.Integer("Max Tokens", default=1000)

    @api.onchange('provider_type')
    def _onchange_provider_type(self):
        if self.provider_type:
            self.model_name = False

    @api.constrains('is_default')
    def _check_single_default(self):
        if self.is_default:
            other_defaults = self.search([('is_default', '=', True), ('id', '!=', self.id)])
            if other_defaults:
                other_defaults.write({'is_default': False})

    @api.model
    def get_default_provider(self):
        provider = self.search([('is_default', '=', True), ('is_active', '=', True)], limit=1)
        if not provider:
            provider = self.search([('is_active', '=', True)], limit=1)
        return provider

    def complete(self, prompt, history=None, tools=None, lang="en"):
        self.ensure_one()
        provider_instance = ProviderFactory.create_provider(self)
        return provider_instance.complete(prompt, history, tools, lang)

    def complete_language_detection(self, prompt):
        """🎯 NEW: Isolated language detection method"""
        self.ensure_one()
        provider_instance = ProviderFactory.create_provider(self)
        return provider_instance.complete_language_detection(prompt)

    def test_connection(self):
        """🔧 FIXED: Test connection with proper UI notification"""
        self.ensure_one()
        try:
            test_prompt = self.env['agentic.ai.prompt.template'].get_template('connection_test')
            
            if not test_prompt:
                test_prompt = "Test connection. Please respond with: Connection successful - AI provider is working correctly."
            
            result = self.complete(test_prompt)
            
            if "Error:" not in result and result:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': '✅ Connection Successful!',
                        'message': f'AI Provider "{self.name}" is working correctly!\n\nResponse: {result[:100]}...\n\nSettings: {self.max_tokens} tokens, temp={self.temperature}',
                        'type': 'success',
                        'sticky': True,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': '❌ Connection Failed',
                        'message': f'AI Provider "{self.name}" test failed:\n\n{result}',
                        'type': 'danger',
                        'sticky': True,
                    }
                }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': '❌ Connection Error',
                    'message': f'Failed to test "{self.name}":\n\n{str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }

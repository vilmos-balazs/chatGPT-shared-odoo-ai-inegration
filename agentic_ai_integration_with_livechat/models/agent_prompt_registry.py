from abc import ABC, abstractmethod
import logging

_logger = logging.getLogger(__name__)

class AgenticAIPromptBase(ABC):
    code = None
    name = None
    description = None
    category = "system"
    provider_type = "all"
    channel = "all"
    purpose = None
    expected_input = None
    expected_output = None
    variables = {}
    prompt_template = ""

    def __init__(self, env):
        self.env = env

    def get_metadata(self):
        return {
            'code': self.code,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'provider_type': self.provider_type,
            'channel': self.channel,
            'purpose': self.purpose,
            'expected_input': self.expected_input,
            'expected_output': self.expected_output,
            'variables_json': str(self.variables),
            'prompt_template': self.prompt_template
        }

class AgenticAIPromptRegistry:
    def __init__(self):
        self._prompts = {}
        self._categories = {}

    def register(self, prompt_class):
        if not prompt_class.code:
            raise ValueError(f"Prompt {prompt_class.__name__} must have a code")
        self._prompts[prompt_class.code] = prompt_class
        category = getattr(prompt_class, 'category', 'system')
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(prompt_class.code)
        _logger.info(f"Registered prompt: {prompt_class.code} ({prompt_class.name})")

    def get_prompt(self, code, env):
        if code not in self._prompts:
            raise ValueError(f"Prompt '{code}' not found")
        return self._prompts[code](env)

    def get_all_prompts_metadata(self, env):
        return [
            prompt_class(env).get_metadata()
            for prompt_class in self._prompts.values()
        ]

    def values(self):
        return self._prompts.values()

AGENTIC_AI_PROMPT_REGISTRY = AgenticAIPromptRegistry()

def register_prompt(prompt_class):
    AGENTIC_AI_PROMPT_REGISTRY.register(prompt_class)
    return prompt_class

# =============================================================================
# 🎯 ENHANCED LANGUAGE DETECTION PROMPT (UPDATED EXISTING)
# =============================================================================

@register_prompt
class LanguageDetectionPrompt(AgenticAIPromptBase):
    code = "language_detection"
    name = "AI Language Detection Prompt"
    description = "Ultra-precise AI language detection with zero contamination"
    category = "system"
    provider_type = "all"
    channel = "all"
    purpose = "Detect language with zero contamination from AI system responses or greetings"
    expected_input = "User message in any of the supported languages"
    expected_output = "Exactly one language code: en_US, ro_RO, or hu_HU"
    variables = {
        "user_message": "The message to analyze for language detection"
    }
    prompt_template = """LANGUAGE_DETECTION_TASK

Analyze this text and return ONLY the language code - nothing else:

TEXT: "{user_message}"

RESPONSE_FORMAT: Return exactly one of these codes:
- ro_RO (if Romanian)
- hu_HU (if Hungarian) 
- en_US (if English or any other language)

CRITICAL: Return ONLY the language code, no greetings, no explanations, no additional text.

LANGUAGE_CODE:"""

# =============================================================================
# 🛠️ FUNCTION CALLING PROMPTS
# =============================================================================

@register_prompt
class FunctionCallingMainPrompt(AgenticAIPromptBase):
    code = "function_calling_main"
    name = "Function Calling Main System Prompt"
    description = "Main system prompt for AI function calling and tool orchestration"
    category = "function_calling"
    provider_type = "all"
    channel = "all"
    purpose = "Teach AI how to analyze user requests and call appropriate tools to fulfill them"
    expected_input = "User message, available tools, language context"
    expected_output = "Either direct response or function calls followed by integrated response"
    variables = {
        "user_message": "The user's request or question",
        "available_tools": "List of available tools with descriptions",
        "lang": "Language code (en_US, ro_RO, hu_HU)",
        "language_name": "Human-readable language name",
        "channel": "livechat or internal"
    }
    prompt_template = """You are an intelligent AI assistant for Odoo ERP system with function calling capabilities.

🌍 LANGUAGE: Respond in {language_name} ({lang})
📍 CHANNEL: {channel}

🛠️ AVAILABLE TOOLS:
{available_tools}

🎯 FUNCTION CALLING INSTRUCTIONS:

1. **ANALYZE USER REQUEST:**
   - What is the user asking for?
   - Which tools can help answer their question?
   - Do I need to call tools or can I answer directly?

2. **WHEN TO CALL FUNCTIONS:**
   - User asks about products → use product_search_enhanced or meili_product_search_simple
   - User asks about categories → use meili_product_category
   - User asks about stock/inventory → use stock_check
   - User asks about company info → use company_info
   - Multiple tools may be needed for complex requests

3. **HOW TO CALL FUNCTIONS:**
   Format: FUNCTION_CALL[tool_name](parameter1="value1", parameter2="value2")
   
   Examples:
   - FUNCTION_CALL[product_search_enhanced](query="zowohome", lang="{lang}")
   - FUNCTION_CALL[meili_product_search_simple](query="laptop", lang="{lang}")
   - FUNCTION_CALL[stock_check](product_name="Dell XPS", lang="{lang}")
   - FUNCTION_CALL[company_info](info_type="contact", lang="{lang}")

4. **AFTER CALLING FUNCTIONS:**
   - Wait for tool results
   - Integrate results into natural response in {language_name}
   - Be helpful and conversational

🗣️ USER REQUEST: {user_message}

Analyze the request and either respond directly or make appropriate function calls to gather information first."""

@register_prompt
class OllamaProviderSystemPrompt(AgenticAIPromptBase):
    code = "ollama_provider_system"
    name = "Ollama Provider System Message"
    description = "System message specifically for Ollama provider interactions with language support"
    category = "provider"
    provider_type = "ollama"
    channel = "all"
    purpose = "Concise system message for Ollama model to establish role and multilingual capabilities"
    expected_input = "Available tools list, language preference"
    expected_output = "Brief system message for Ollama API with language context"
    variables = {
        "tools_list": "list of tool codes",
        "lang": "language code (en_US, ro_RO, hu_HU)"
    }
    prompt_template = """You are a helpful AI assistant for Odoo ERP system. Available tools: {tools_list}. Language: {lang}. Be concise and helpful. Respond in the user's language."""

@register_prompt
class ConnectionTestPrompt(AgenticAIPromptBase):
    code = "connection_test"
    name = "Connection Test Prompt"
    description = "Simple prompt used to test AI provider connections"
    category = "system"
    provider_type = "all"
    channel = "all"
    purpose = "Verify that AI provider is responding correctly"
    expected_input = "No variables needed"
    expected_output = "Simple response confirming connection"
    variables = {}
    prompt_template = """Test connection. Please respond with: "Connection successful - AI provider is working correctly."""

@register_prompt
class MainAgentSystemPrompt(AgenticAIPromptBase):
    code = "main_agent_system"
    name = "Main Agent System Prompt"
    description = "Primary system prompt for the agentic AI agent with multilingual support"
    category = "system"
    provider_type = "all"
    channel = "all"
    purpose = "Establishes the AI's role, provides context about available tools, and sets expectations for multilingual responses"
    expected_input = "User message, available tools list, channel, language, language name"
    expected_output = "System prompt ready for AI provider with language context"
    variables = {
        "channel": "livechat or internal", 
        "lang": "language code (en_US, ro_RO, hu_HU)",
        "language_name": "human-readable language name",
        "tool_descriptions": "formatted list of available tools with language support",
        "message": "user's input message"
    }
    prompt_template = """You are an AI assistant for Odoo ERP system.
Channel: {channel}
Language: {lang} ({language_name})

🌍 MULTILINGUAL INSTRUCTIONS:
- Detect and respond in the user's language: {language_name}
- All tools support multilingual input and output
- If user switches languages mid-conversation, adapt accordingly

Available tools:
{tool_descriptions}

User message: {message}

Based on the user's message and available tools, provide a helpful response in {language_name}. Use tool context and keywords to decide which tools are most relevant."""

@register_prompt
class LivechatBusinessPrompt(AgenticAIPromptBase):
    code = "livechat_business_system"
    name = "Livechat Business-Focused System Prompt"  
    description = "System prompt for public livechat with business restrictions and multilingual support"
    category = "livechat"
    provider_type = "all"
    channel = "livechat"
    purpose = "Restrict AI responses to business-relevant topics only in public livechat, with language detection"
    expected_input = "User message, business tools only, language, language name"
    expected_output = "Business-focused response or polite redirect in user's language"
    variables = {
        "business_tools": "product and general tools only",
        "user_message": "customer inquiry",
        "lang": "language code (en_US, ro_RO, hu_HU)",
        "language_name": "human-readable language name"
    }
    prompt_template = """You are a business assistant for our company's website livechat.

🌍 LANGUAGE: Respond in {language_name} ({lang})

IMPORTANT RESTRICTIONS:
- Only help with business-related questions (products, services, company info)
- Available business tools: {business_tools}
- If asked about non-business topics, politely redirect to business matters
- Be professional, helpful, and concise
- Maintain conversation in {language_name}

Customer message: {user_message}

Provide helpful business-focused assistance in {language_name} or politely redirect off-topic questions."""

@register_prompt
class InternalUnrestrictedPrompt(AgenticAIPromptBase):
    code = "internal_unrestricted_system"
    name = "Internal Unrestricted System Prompt"
    description = "Full access system prompt for internal team members with multilingual support"
    category = "internal"
    provider_type = "all" 
    channel = "internal"
    purpose = "Provide unrestricted access to all tools and capabilities for staff with language support"
    expected_input = "User message, all available tools, language, language name"
    expected_output = "Comprehensive assistance using any available tools in user's language"
    variables = {
        "all_tools": "complete list of available tools",
        "user_message": "staff member inquiry", 
        "lang": "language code (en_US, ro_RO, hu_HU)",
        "language_name": "human-readable language name"
    }
    prompt_template = """You are an advanced AI assistant for internal team members.

🌍 LANGUAGE: Communicate in {language_name} ({lang})

FULL ACCESS MODE:
- Use any available tools: {all_tools}
- Help with any task (business, technical, administrative)
- Provide detailed, comprehensive responses
- All tools support multilingual operation
- Maintain conversation in {language_name}

Team member request: {user_message}

Provide thorough assistance in {language_name} using all available capabilities."""

def get_prompt_registry():
    return AGENTIC_AI_PROMPT_REGISTRY

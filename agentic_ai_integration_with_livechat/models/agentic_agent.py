from odoo import models, api
import logging
import re

_logger = logging.getLogger(__name__)

class AgenticAIAgent(models.AbstractModel):
    _name = "agentic.ai.agent"
    _description = "Agentic AI Agent (abstract, vendor-agnostic)"

    @api.model
    def _detect_language_with_ai(self, message):
        """
        🎯 PURE AI LANGUAGE DETECTION - DATABASE-DRIVEN ONLY
        """
        try:
            # 🎯 CLEAN: Use ONLY database template system
            detection_prompt = self.env['agentic.ai.prompt.template'].get_template(
                'language_detection',
                user_message=message
            )
            
            # 🔍 DEBUG: Show exactly what we're sending
            _logger.info("=" * 80)
            _logger.info("🎯 LANGUAGE DETECTION - ISOLATED CALL")
            _logger.info("=" * 80)
            _logger.info(f"📥 USER MESSAGE: '{message}'")
            _logger.info("-" * 40)
            _logger.info("📤 DETECTION PROMPT:")
            _logger.info(f"'''{detection_prompt}'''")
            _logger.info("-" * 40)

            # Get provider and call AI with isolated context
            provider = self._get_provider()
            
            # 🎯 ISOLATED CALL: Use special language detection method
            ai_response = provider.complete_language_detection(detection_prompt)
            
            # 🔍 DEBUG: Show AI response
            _logger.info("🤖 AI RAW RESPONSE:")
            _logger.info(f"'''{ai_response}'''")
            _logger.info("-" * 40)
            
            # Parse AI response to extract language code
            detected_lang = self._parse_language_response_strict(ai_response)
            
            # 🎯 VALIDATION: Ensure supported language or fallback to English
            validated_lang = self._validate_and_fallback_language(detected_lang)
            
            # 🔍 DEBUG: Show final result
            _logger.info(f"🎯 PARSED LANGUAGE: {detected_lang}")
            _logger.info(f"✅ FINAL LANGUAGE: {validated_lang}")
            _logger.info("=" * 80)
            
            return validated_lang
            
        except Exception as e:
            _logger.error("=" * 80)
            _logger.error(f"💥 LANGUAGE DETECTION ERROR: {str(e)} → FALLBACK TO ENGLISH")
            _logger.error("=" * 80)
            return "en_US"  # Always fallback to English on errors

    @api.model
    def _parse_language_response_strict(self, ai_response):
        """�� STRICT PARSING: Extract only valid language codes"""
        if not ai_response:
            _logger.warning("❌ Empty AI response → fallback to en_US")
            return "en_US"
        
        # Clean the response
        response_clean = ai_response.strip().upper()
        
        _logger.info(f"🔍 STRICT PARSING: Original='{ai_response}' | Clean='{response_clean}'")
        
        # 🎯 EXACT PATTERN MATCHING: Look for exact language codes
        if "RO_RO" in response_clean or "RO-RO" in response_clean:
            _logger.info("✅ FOUND: ro_RO pattern")
            return "ro_RO"
        elif "HU_HU" in response_clean or "HU-HU" in response_clean:
            _logger.info("✅ FOUND: hu_HU pattern")
            return "hu_HU"
        elif "EN_US" in response_clean or "EN-US" in response_clean:
            _logger.info("✅ FOUND: en_US pattern")
            return "en_US"
        
        # 🎯 LANGUAGE NAME MATCHING: Look for language names
        elif any(word in response_clean for word in ["ROMANIAN", "ROMÂNĂ", "ROMANIA"]):
            _logger.info("✅ FOUND: Romanian language name")
            return "ro_RO"
        elif any(word in response_clean for word in ["HUNGARIAN", "MAGYAR", "HUNGARY"]):
            _logger.info("✅ FOUND: Hungarian language name")
            return "hu_HU"
        elif any(word in response_clean for word in ["ENGLISH", "ENGLAND"]):
            _logger.info("✅ FOUND: English language name")
            return "en_US"
        
        # 🎯 SINGLE CODE MATCHING: Look for standalone codes
        elif re.search(r'\bRO\b', response_clean):
            _logger.info("✅ FOUND: RO code")
            return "ro_RO"
        elif re.search(r'\bHU\b', response_clean):
            _logger.info("✅ FOUND: HU code")
            return "hu_HU"
        elif re.search(r'\bEN\b', response_clean):
            _logger.info("✅ FOUND: EN code")
            return "en_US"
        
        # 🎯 DEFAULT FALLBACK: If nothing matches, default to English
        _logger.warning(f"❌ COULD NOT PARSE: '{ai_response}' → defaulting to en_US")
        return "en_US"

    @api.model
    def _validate_and_fallback_language(self, detected_lang):
        """🎯 VALIDATE AND FALLBACK: Ensure language is supported"""
        SUPPORTED_LANGUAGES = ['en_US', 'ro_RO', 'hu_HU']
        
        if detected_lang in SUPPORTED_LANGUAGES:
            _logger.info(f"✅ VALID LANGUAGE: {detected_lang}")
            return detected_lang
        else:
            _logger.warning(f"❌ UNSUPPORTED LANGUAGE: {detected_lang} → fallback to en_US")
            return "en_US"

    @api.model
    def _detect_language(self, message):
        """🎯 MAIN LANGUAGE DETECTION: Pure AI only"""
        return self._detect_language_with_ai(message)

    @api.model
    def _get_provider(self, provider_code=None):
        """Get provider from database"""
        if provider_code:
            provider = self.env['agentic.ai.provider'].search([
                ('code', '=', provider_code), 
                ('is_active', '=', True)
            ], limit=1)
        else:
            provider = self.env['agentic.ai.provider'].get_default_provider()
        
        if not provider:
            raise Exception(f"AI provider '{provider_code or 'default'}' not found or inactive")
        return provider

    @api.model
    def _list_tools(self, category=None):
        return self.env['agentic.ai.tool.metadata'].get_active_tools_for_ai(category=category)

    @api.model
    def ask(self, message, channel="livechat", history=None, provider_code=None, lang=None):
        """Main entry point with enhanced language detection"""
        
        _logger.info("🚀" * 20)
        _logger.info("🚀 STARTING AGENTIC AI REQUEST")
        _logger.info("🚀" * 20)
        _logger.info(f"📥 USER MESSAGE: '{message}'")
        _logger.info(f"📍 CHANNEL: {channel}")
        
        # 🎯 PURE AI LANGUAGE DETECTION
        if not lang:
            detected_lang = self._detect_language(message)
            lang = detected_lang  # Already validated in detection method
            language_detection_method = "pure_ai_isolated"
        else:
            lang = self._validate_and_fallback_language(lang)
            language_detection_method = "provided"
        
        _logger.info(f"🌍 FINAL LANGUAGE: {lang} (method: {language_detection_method})")
        
        provider = self._get_provider(provider_code)
        _logger.info(f"🤖 PROVIDER: {provider.name}")
        
        # Get tools based on channel restrictions
        if channel == "livechat":
            tools = self._list_tools(category='product') + self._list_tools(category='general')
            prompt_code = "livechat_business_system"
        else:
            tools = self._list_tools()
            prompt_code = "internal_unrestricted_system"
        
        _logger.info(f"🛠️ TOOLS AVAILABLE: {len(tools)}")
        
        # Check if function calling is needed
        function_engine = self.env['agentic.ai.function.calling.engine']
        needs_function_calling = function_engine.should_use_function_calling(message, tools)
        
        _logger.info(f"⚡ FUNCTION CALLING NEEDED: {needs_function_calling}")
        
        if needs_function_calling:
            return self._handle_with_function_calling(message, channel, tools, provider, lang, prompt_code, history)
        else:
            return self._handle_direct_response(message, channel, tools, provider, lang, prompt_code, history)

    @api.model
    def _handle_with_function_calling(self, message, channel, tools, provider, lang, prompt_code, history):
        """Function calling workflow with debug"""
        _logger.info(f"🛠️ USING FUNCTION CALLING WORKFLOW")
        
        # Build tool descriptions for AI
        tool_descriptions = []
        for tool in tools:
            tool_desc = f"- {tool['code']}: {tool['name']} - {tool['description']}"
            if tool.get('ai_usage_context'):
                tool_desc += f" | Context: {tool['ai_usage_context']}"
            if tool.get('keywords'):
                tool_desc += f" | Keywords: {', '.join(tool['keywords'])}"
            tool_descriptions.append(tool_desc)
        
        # Get function calling prompt
        function_prompt = self.env['agentic.ai.prompt.template'].get_template(
            'function_calling_main',
            user_message=message,
            available_tools="\n".join(tool_descriptions),
            lang=lang,
            language_name=self._get_language_name(lang),
            channel=channel
        )
        
        _logger.info("📤 FUNCTION CALLING PROMPT SENT TO AI:")
        _logger.info("=" * 60)
        _logger.info(function_prompt)
        _logger.info("=" * 60)
        
        # Get AI response (may contain function calls)
        ai_response = provider.complete(
            function_prompt, 
            history=history, 
            tools=tools, 
            lang=lang
        )
        
        _logger.info("🤖 AI FUNCTION CALLING RESPONSE:")
        _logger.info("=" * 60)
        _logger.info(ai_response)
        _logger.info("=" * 60)
        
        # Parse function calls
        function_engine = self.env['agentic.ai.function.calling.engine']
        function_calls = function_engine.parse_function_calls(ai_response)
        
        _logger.info(f"🔧 PARSED FUNCTION CALLS: {len(function_calls)}")
        for i, call in enumerate(function_calls, 1):
            _logger.info(f"  {i}. {call['tool']}({call['parameters']})")
        
        if function_calls:
            # Execute function calls
            function_results = function_engine.execute_function_calls(function_calls, lang)
            
            _logger.info("📊 FUNCTION RESULTS:")
            for i, result in enumerate(function_results, 1):
                status = "✅ Success" if result['success'] else "❌ Error"
                _logger.info(f"  {i}. {result['tool']}: {status}")
                if not result['success']:
                    _logger.info(f"     Error: {result['error']}")
            
            # Integrate results into natural response
            final_response = function_engine.integrate_function_results(message, function_results, lang)
            
            _logger.info("🎯 FINAL INTEGRATED RESPONSE:")
            _logger.info("=" * 60)
            _logger.info(final_response)
            _logger.info("=" * 60)
            
            return {
                "answer": final_response,
                "language": lang,
                "language_detected": True,
                "language_detection_method": "pure_ai_isolated",
                "provider": provider.name,
                "provider_code": provider.code,
                "tools_available": len(tools),
                "channel": channel,
                "prompt_used": prompt_code,
                "function_calling_used": True,
                "function_calls_made": len(function_calls),
                "function_calls": function_calls,
                "function_results": function_results,
                "ai_raw_response": ai_response,
                "multilingual_ready": True,
                "ai_powered_detection": True
            }
        else:
            return {
                "answer": ai_response,
                "language": lang,
                "language_detected": True,
                "language_detection_method": "pure_ai_isolated",
                "provider": provider.name,
                "provider_code": provider.code,
                "tools_available": len(tools),
                "channel": channel,
                "prompt_used": prompt_code,
                "function_calling_used": False,
                "function_calls_made": 0,
                "multilingual_ready": True,
                "ai_powered_detection": True
            }

    @api.model
    def _handle_direct_response(self, message, channel, tools, provider, lang, prompt_code, history):
        """Direct response workflow with debug"""
        _logger.info(f"🗣️ USING DIRECT RESPONSE WORKFLOW")
        
        # Build tool descriptions
        tool_descriptions = []
        for tool in tools:
            tool_desc = f"- {tool['code']}: {tool['name']} - {tool['description']}"
            if tool.get('ai_usage_context'):
                tool_desc += f" | Context: {tool['ai_usage_context']}"
            if tool.get('keywords'):
                tool_desc += f" | Keywords: {', '.join(tool['keywords'])}"
            tool_descriptions.append(tool_desc)
        
        # Get system prompt
        if channel == "livechat":
            system_prompt = self.env['agentic.ai.prompt.template'].get_template(
                'livechat_business_system',
                business_tools="\n".join(tool_descriptions),
                user_message=message,
                lang=lang,
                language_name=self._get_language_name(lang)
            )
        else:
            system_prompt = self.env['agentic.ai.prompt.template'].get_template(
                'internal_unrestricted_system',
                all_tools="\n".join(tool_descriptions),
                user_message=message,
                lang=lang,
                language_name=self._get_language_name(lang)
            )
        
        _logger.info("📤 DIRECT RESPONSE PROMPT SENT TO AI:")
        _logger.info("=" * 60)
        _logger.info(system_prompt)
        _logger.info("=" * 60)
        
        # Call AI
        answer = provider.complete(
            system_prompt, 
            history=history, 
            tools=tools, 
            lang=lang
        )
        
        _logger.info("🤖 AI DIRECT RESPONSE:")
        _logger.info("=" * 60)
        _logger.info(answer)
        _logger.info("=" * 60)
        
        return {
            "answer": answer,
            "language": lang,
            "language_detected": True,
            "language_detection_method": "pure_ai_isolated",
            "provider": provider.name,
            "provider_code": provider.code,
            "tools_available": len(tools),
            "channel": channel,
            "prompt_used": prompt_code,
            "function_calling_used": False,
            "function_calls_made": 0,
            "multilingual_ready": True,
            "ai_powered_detection": True
        }
    
    @api.model
    def _get_language_name(self, lang_code):
        """Get human-readable language name"""
        lang_names = {
            'en_US': 'English',
            'ro_RO': 'Romanian',
            'hu_HU': 'Hungarian'
        }
        return lang_names.get(lang_code, 'English')

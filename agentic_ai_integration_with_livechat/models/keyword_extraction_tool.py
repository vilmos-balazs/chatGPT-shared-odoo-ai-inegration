from ..models.agent_tool import register_tool, AgenticAIToolBase
import json
import logging

_logger = logging.getLogger(__name__)

@register_tool
class KeywordExtractionTool(AgenticAIToolBase):
    code = "keyword_extraction"
    name = "AI Keyword Extraction (Structured)"
    description = "Extract structured keywords from user messages using AI intelligence"
    category = "general"
    parameters = {
        "user_message": {
            "type": "string",
            "required": True,
            "description": "The user's message to analyze for keyword extraction"
        },
        "lang": {
            "type": "string",
            "required": False,
            "description": "Language code (en_US, ro_RO, hu_HU)"
        }
    }
    keywords = [
        "extract", "analyze", "keywords", "intent", "understand",
        "extrage", "analizeaza", "cuvinte", "intentie", "intelege",
        "elemez", "kulcsszavak", "szándék", "megért"
    ]
    ai_orchestration_priority = 100  # Highest priority - should run first
    ai_usage_context = "Always use this tool FIRST when user asks about products, recommendations, or any search-related queries. This tool extracts structured keywords to improve search precision. Use for any message that might need product/category search."
    
    examples = [
        {
            "input": {
                "user_message": "Am un proiect de pardoseala acasa la mine. Ce lac recomanzi in bucatarie ca sa reziste la apa?",
                "lang": "ro_RO"
            },
            "output": {
                "objects": ["pardoseala", "lac"],
                "properties": ["reziste", "apa"],
                "rooms": ["bucatarie"],
                "actions": ["recomanzi"],
                "context": ["proiect", "acasa"],
                "intent": "recommendation"
            },
            "description": "Extract structured keywords from Romanian renovation query"
        }
    ]
    
    output_format = {
        "objects": ["list of physical items/products"],
        "properties": ["list of characteristics/features"], 
        "rooms": ["list of spaces/locations"],
        "actions": ["list of user intentions/actions"],
        "context": ["list of project/usage context"],
        "intent": "primary intent category",
        "extraction_success": "boolean",
        "language_detected": "detected language",
        "total_keywords": "number of extracted keywords"
    }
    
    def call(self, **kwargs):
        validated = self.validate_parameters(**kwargs)
        user_message = validated["user_message"]
        lang = self._validate_language(validated.get("lang", "en_US"))
        
        _logger.info(f"🧠 AI KEYWORD EXTRACTION: '{user_message}' in {lang}")
        
        try:
            # 🎯 USE DATABASE-DRIVEN PROMPT TEMPLATE
            extraction_prompt = self.env['agentic.ai.prompt.template'].get_template(
                'keyword_extraction_structured',
                user_message=user_message,
                lang=lang
            )
            
            if not extraction_prompt:
                # Fallback if template not found
                extraction_prompt = f'''Extract keywords from: "{user_message}" 
Return JSON: {{"objects": [], "properties": [], "rooms": [], "actions": [], "context": [], "intent": "product_search"}}'''
            
            _logger.info(f"📤 EXTRACTION PROMPT: {extraction_prompt[:200]}...")
            
            # 🎯 CALL AI FOR EXTRACTION
            provider = self._get_provider()
            ai_response = provider.complete_language_detection(extraction_prompt)  # Use isolated call
            
            _logger.info(f"🤖 AI EXTRACTION RESPONSE: {ai_response}")
            
            # 🎯 PARSE JSON RESPONSE
            extracted_data = self._parse_extraction_response(ai_response)
            
            # 🎯 ENHANCE WITH METADATA
            result = {
                **extracted_data,
                "extraction_success": True,
                "language_detected": lang,
                "total_keywords": sum(len(v) if isinstance(v, list) else 0 for v in extracted_data.values()),
                "original_message": user_message
            }
            
            _logger.info(f"✅ EXTRACTION COMPLETE: {result['total_keywords']} keywords extracted")
            return result
            
        except Exception as e:
            error_msg = f"Keyword extraction failed: {str(e)}"
            _logger.error(f"❌ {error_msg}")
            
            # 🛡️ GRACEFUL FALLBACK
            return {
                "objects": [user_message.lower()],  # Fallback to simple search
                "properties": [],
                "rooms": [],
                "actions": ["search"],
                "context": [],
                "intent": "product_search",
                "extraction_success": False,
                "language_detected": lang,
                "total_keywords": 1,
                "error": error_msg,
                "original_message": user_message
            }
    
    def _parse_extraction_response(self, ai_response):
        """Parse AI JSON response with robust error handling"""
        try:
            # Clean the response - remove extra text before/after JSON
            response_clean = ai_response.strip()
            
            # Find JSON block
            start_idx = response_clean.find('{')
            end_idx = response_clean.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = response_clean[start_idx:end_idx+1]
                extracted = json.loads(json_str)
                
                # 🎯 VALIDATE STRUCTURE
                required_fields = ["objects", "properties", "rooms", "actions", "context", "intent"]
                for field in required_fields:
                    if field not in extracted:
                        extracted[field] = [] if field != "intent" else "product_search"
                    elif field != "intent" and not isinstance(extracted[field], list):
                        extracted[field] = [str(extracted[field])] if extracted[field] else []
                
                return extracted
            
            else:
                _logger.warning("No valid JSON found in AI response")
                return self._get_fallback_structure()
                
        except json.JSONDecodeError as e:
            _logger.error(f"JSON parsing failed: {str(e)}")
            return self._get_fallback_structure()
        except Exception as e:
            _logger.error(f"Extraction parsing error: {str(e)}")
            return self._get_fallback_structure()
    
    def _get_fallback_structure(self):
        """Fallback structure when parsing fails"""
        return {
            "objects": [],
            "properties": [],
            "rooms": [],
            "actions": ["search"],
            "context": [],
            "intent": "product_search"
        }
    
    def _get_provider(self):
        """Get AI provider for extraction"""
        return self.env['agentic.ai.provider'].get_default_provider()

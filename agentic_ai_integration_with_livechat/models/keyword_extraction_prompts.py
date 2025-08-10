from ..models.agent_prompt_registry import register_prompt, AgenticAIPromptBase

@register_prompt
class KeywordExtractionPrompt(AgenticAIPromptBase):
    code = "keyword_extraction_structured"
    name = "AI Structured Keyword Extraction"
    description = "Extract structured keywords from user messages for enhanced product search"
    category = "function_calling"
    provider_type = "all"
    channel = "all"
    purpose = "Intelligently extract and categorize keywords from user messages to improve search precision"
    expected_input = "Natural language user message in any supported language"
    expected_output = "Structured JSON with categorized keywords"
    variables = {
        "user_message": "The user's message to analyze",
        "lang": "Language code for context"
    }
    prompt_template = """KEYWORD_EXTRACTION_TASK

Analyze this user message and extract structured keywords for product search:

USER_MESSAGE: "{user_message}"
LANGUAGE: {lang}

Extract keywords into these categories:

1. OBJECTS: Physical items, products, materials (pardoseala, lac, vopsea, parchet, etc.)
2. PROPERTIES: Characteristics, features, qualities (reziste, mat, lucios, transparent, etc.)  
3. ROOMS: Spaces, locations, areas (bucatarie, baie, living, dormitor, etc.)
4. ACTIONS: What user wants to do (recomanzi, cumpara, gaseste, compara, etc.)
5. CONTEXT: Project type, usage context (proiect, renovare, constructie, etc.)
6. INTENT: Primary goal (product_search, recommendation, comparison, information)

RESPONSE FORMAT - Return ONLY valid JSON:
{{
  "objects": ["keyword1", "keyword2"],
  "properties": ["keyword3", "keyword4"], 
  "rooms": ["keyword5"],
  "actions": ["keyword6"],
  "context": ["keyword7"],
  "intent": "primary_intent"
}}

RULES:
- Extract meaningful keywords only (ignore stop words)
- Keep original language of keywords
- Include synonyms/related terms when relevant
- Focus on commerce/construction/paint domain
- Return empty arrays for missing categories
- Intent should be one of: product_search, recommendation, comparison, information, stock_check

JSON_RESPONSE:"""

from odoo import models, api
import logging
import re
import json

_logger = logging.getLogger(__name__)

class AgenticAIFunctionCallingEngine(models.AbstractModel):
    _name = "agentic.ai.function.calling.engine"
    _description = "Function Calling and Tool Orchestration Engine"

    @api.model
    def should_use_function_calling(self, user_message, available_tools):
        """
        🎯 ENHANCED: Smart orchestration with AI keyword extraction priority
        """
        message_lower = user_message.lower()
        
        # 🎯 CHECK IF WE HAVE KEYWORD EXTRACTION TOOL
        available_tool_codes = [tool['code'] for tool in available_tools]
        has_keyword_extraction = 'keyword_extraction' in available_tool_codes
        has_multisearch_tools = any(tool in available_tool_codes for tool in ['product_multisearch', 'category_multisearch'])
        
        _logger.info(f"🛠️ Tools check: keyword_extraction={has_keyword_extraction}, multisearch={has_multisearch_tools}")
        
        # 🎯 ENHANCED INTENT DETECTION
        intent_indicators = {
            'product_search': [
                # Romanian
                'produs', 'produse', 'lac', 'vopsea', 'parchet', 'pardoseala', 'recomanzi', 'aveti', 'gasesc', 'cauta',
                # Hungarian  
                'termék', 'termékek', 'festék', 'parketta', 'ajánl', 'van', 'keres',
                # English
                'product', 'products', 'paint', 'parquet', 'flooring', 'recommend', 'have', 'find', 'search'
            ],
            'category_search': [
                'categorie', 'categorii', 'kategória', 'category', 'categories', 'browse', 'section', 'tip', 'tipuri'
            ],
            'renovation_project': [
                'proiect', 'projekt', 'project', 'renovare', 'renovation', 'constructie', 'construction', 'acasa', 'home'
            ]
        }
        
        # 🎯 SCORE INTENTS
        intent_scores = {}
        for intent, indicators in intent_indicators.items():
            score = sum(1 for indicator in indicators if indicator in message_lower)
            intent_scores[intent] = score
        
        max_score = max(intent_scores.values()) if intent_scores else 0
        
        _logger.info(f"🎯 Intent scores: {intent_scores}, max: {max_score}")
        
        # 🎯 DECISION LOGIC
        if max_score > 0:
            if has_keyword_extraction and has_multisearch_tools:
                _logger.info("✅ Using AI-powered extraction + multisearch workflow")
                return True
            elif any(tool in available_tool_codes for tool in ['product_search', 'meili_product_search', 'stock_check', 'company_info']):
                _logger.info("✅ Using traditional tool workflow")
                return True
        
        _logger.info("❌ No relevant tools or intent detected")
        return False

    @api.model
    def parse_function_calls(self, ai_response):
        """Parse function calls from AI response - ENHANCED FOR CHAINING"""
        function_calls = []
        
        pattern = r'FUNCTION_CALL\[([^\]]+)\]\(([^)]*)\)'
        matches = re.findall(pattern, ai_response, re.IGNORECASE)
        
        for match in matches:
            tool_name = match[0].strip()
            params_str = match[1].strip()
            
            try:
                parameters = self._parse_parameters(params_str)
                
                function_calls.append({
                    'tool': tool_name,
                    'parameters': parameters,
                    'raw_match': f"FUNCTION_CALL[{tool_name}]({params_str})"
                })
                
                _logger.info(f"🛠️ Parsed function call: {tool_name} with params {parameters}")
                
            except Exception as e:
                _logger.error(f"Error parsing function call parameters: {str(e)}")
                continue
        
        return function_calls

    @api.model
    def _parse_parameters(self, params_str):
        """Parse parameter string into dictionary - ENHANCED FOR JSON"""
        if not params_str.strip():
            return {}
        
        parameters = {}
        
        if '=' in params_str:
            param_pattern = r'(\w+)\s*=\s*["\']?([^,"\']*)["\']*'
            param_matches = re.findall(param_pattern, params_str)
            
            for param_name, param_value in param_matches:
                if param_value.lower() == 'true':
                    parameters[param_name] = True
                elif param_value.lower() == 'false':
                    parameters[param_name] = False
                elif param_value.isdigit():
                    parameters[param_name] = int(param_value)
                else:
                    # 🎯 ENHANCED: Handle JSON strings for extracted_keywords
                    param_value_clean = param_value.strip('"\'')
                    if param_name == 'extracted_keywords' and (param_value_clean.startswith('{') or param_value_clean.startswith('[')):
                        # It's JSON, keep as string for tool to parse
                        parameters[param_name] = param_value_clean
                    else:
                        parameters[param_name] = param_value_clean
        
        return parameters

    @api.model
    def execute_function_calls(self, function_calls, lang="en_US"):
        """🎯 ENHANCED: Execute with intelligent chaining for extraction → search flow"""
        results = []
        extraction_result = None
        
        # 🎯 STEP 1: Execute keyword extraction first if present
        for call in function_calls:
            if call['tool'] == 'keyword_extraction':
                try:
                    result = self._execute_single_function(call, lang)
                    extraction_result = result
                    results.append({
                        'tool': call['tool'],
                        'parameters': call['parameters'],
                        'success': True,
                        'result': result,
                        'error': None
                    })
                    _logger.info("✅ Keyword extraction completed, ready for chaining")
                    break
                except Exception as e:
                    _logger.error(f"Keyword extraction failed: {str(e)}")
                    results.append({
                        'tool': call['tool'],
                        'parameters': call['parameters'],
                        'success': False,
                        'result': None,
                        'error': str(e)
                    })
        
        # 🎯 STEP 2: Execute other tools, inject extraction results if needed
        for call in function_calls:
            if call['tool'] == 'keyword_extraction':
                continue  # Already processed
            
            try:
                # 🎯 SMART CHAINING: Inject extraction results into multisearch tools
                if extraction_result and call['tool'] in ['product_multisearch', 'category_multisearch']:
                    if 'extracted_keywords' not in call['parameters']:
                        call['parameters']['extracted_keywords'] = json.dumps(extraction_result)
                        _logger.info(f"🔗 Chained extraction result to {call['tool']}")
                
                result = self._execute_single_function(call, lang)
                results.append({
                    'tool': call['tool'],
                    'parameters': call['parameters'],
                    'success': True,
                    'result': result,
                    'error': None
                })
                
            except Exception as e:
                _logger.error(f"Error executing function {call['tool']}: {str(e)}")
                results.append({
                    'tool': call['tool'],
                    'parameters': call['parameters'],
                    'success': False,
                    'result': None,
                    'error': str(e)
                })
        
        return results

    @api.model
    def _execute_single_function(self, call, lang):
        """Execute a single function call - UNCHANGED"""
        tool_name = call['tool']
        parameters = call['parameters'].copy()
        
        if 'lang' not in parameters:
            parameters['lang'] = lang
        
        from .agent_tool import get_registry
        registry = get_registry()
        tool = registry.get_tool(tool_name, self.env)
        
        result = tool.call(**parameters)
        
        _logger.info(f"🛠️ Executed {tool_name}: {len(str(result))} chars result")
        return result

    @api.model
    def integrate_function_results(self, user_message, function_results, lang="en_US"):
        """🎯 ENHANCED: Integrate results with keyword extraction awareness"""
        if not function_results:
            return self._get_fallback_response(user_message, lang)
        
        successful_results = [r for r in function_results if r['success']]
        
        if not successful_results:
            return self._get_error_response(function_results, lang)
        
        response_parts = []
        extraction_summary = None
        
        # 🎯 FIND EXTRACTION SUMMARY
        for result in successful_results:
            if result['tool'] == 'keyword_extraction' and result['success']:
                extraction_summary = result['result']
                break
        
        # 🎯 INTEGRATE RESULTS WITH EXTRACTION CONTEXT
        for result in successful_results:
            tool_name = result['tool']
            tool_result = result['result']
            
            if tool_name == 'keyword_extraction':
                continue  # Don't include raw extraction in response
            elif 'product_multisearch' in tool_name or 'product_search' in tool_name or 'meili_product_search' in tool_name:
                response_parts.append(self._format_product_search_response(tool_result, lang))
            elif 'category_multisearch' in tool_name or 'category' in tool_name:
                response_parts.append(self._format_category_response(tool_result, lang))
            elif tool_name == 'stock_check':
                response_parts.append(self._format_stock_response(tool_result, lang))
            elif tool_name == 'company_info':
                response_parts.append(self._format_company_response(tool_result, lang))
        
        if response_parts:
            final_response = " ".join(response_parts)
            
            # 🎯 ADD EXTRACTION CONTEXT IF AVAILABLE
            if extraction_summary and extraction_summary.get('extraction_success'):
                intent = extraction_summary.get('intent', 'search')
                total_keywords = extraction_summary.get('total_keywords', 0)
                
                if lang == 'ro_RO':
                    final_response += f"\n\n💡 Am analizat {total_keywords} cuvinte cheie din cererea dumneavoastră pentru a găsi cele mai relevante rezultate."
                elif lang == 'hu_HU':
                    final_response += f"\n\n💡 {total_keywords} kulcsszót elemeztem a kéréséből a legmegfelelőbb eredmények megtalálásához."
                else:
                    final_response += f"\n\n💡 I analyzed {total_keywords} keywords from your request to find the most relevant results."
            
            return final_response
        else:
            return self._get_fallback_response(user_message, lang)

    @api.model
    def _format_product_search_response(self, result, lang):
        """Format product search results - ENHANCED FOR EXTRACTION"""
        products = result.get('products', [])
        total_found = result.get('total_found', 0)
        keywords_used = result.get('keywords_used', [])
        extraction_summary = result.get('extraction_summary', {})
        
        if not products:
            return self._get_localized_text("no_products_found", lang)
        
        if len(products) == 1:
            product = products[0]
            if lang == 'ro_RO':
                base_response = f"Am găsit acest produs: {product['name']} la {product['price']} {product.get('currency', 'RON')}. {'Este disponibil în stoc.' if product.get('available') else 'Nu este în stoc momentan.'}"
                if keywords_used:
                    base_response += f" (căutare inteligentă pentru: {', '.join(keywords_used[:3])})"
                return base_response
            elif lang == 'hu_HU':
                base_response = f"Megtaláltam ezt a terméket: {product['name']} {product['price']} {product.get('currency', 'RON')} áron. {'Raktáron van.' if product.get('available') else 'Jelenleg nincs raktáron.'}"
                if keywords_used:
                    base_response += f" (intelligens keresés: {', '.join(keywords_used[:3])})"
                return base_response
            else:
                base_response = f"I found this product: {product['name']} at {product['price']} {product.get('currency', 'RON')}. {'It is available in stock.' if product.get('available') else 'Currently out of stock.'}"
                if keywords_used:
                    base_response += f" (intelligent search for: {', '.join(keywords_used[:3])})"
                return base_response
        else:
            if lang == 'ro_RO':
                response = f"Am găsit {total_found} produse relevante"
                if extraction_summary.get('intent'):
                    response += f" pentru {extraction_summary['intent']}"
                response += ":\n"
                for i, product in enumerate(products[:3], 1):
                    response += f"{i}. {product['name']} - {product['price']} {product.get('currency', 'RON')}\n"
            elif lang == 'hu_HU':
                response = f"{total_found} releváns terméket találtam"
                if extraction_summary.get('intent'):
                    response += f" erre: {extraction_summary['intent']}"
                response += ":\n"
                for i, product in enumerate(products[:3], 1):
                    response += f"{i}. {product['name']} - {product['price']} {product.get('currency', 'RON')}\n"
            else:
                response = f"I found {total_found} relevant products"
                if extraction_summary.get('intent'):
                    response += f" for {extraction_summary['intent']}"
                response += ":\n"
                for i, product in enumerate(products[:3], 1):
                    response += f"{i}. {product['name']} - {product['price']} {product.get('currency', 'RON')}\n"
            
            return response

    @api.model
    def _format_category_response(self, result, lang):
        """Format category results - ENHANCED"""
        categories = result.get('categories', [])
        keywords_used = result.get('keywords_used', [])
        
        if not categories:
            return self._get_localized_text("no_categories_found", lang)
        
        if lang == 'ro_RO':
            response = f"Am găsit {len(categories)} categorii relevante:\n"
            for cat in categories[:5]:
                response += f"• {cat['name']} ({cat.get('product_count', 0)} produse)\n"
        elif lang == 'hu_HU':
            response = f"{len(categories)} releváns kategóriát találtam:\n"
            for cat in categories[:5]:
                response += f"• {cat['name']} ({cat.get('product_count', 0)} termék)\n"
        else:
            response = f"I found {len(categories)} relevant categories:\n"
            for cat in categories[:5]:
                response += f"• {cat['name']} ({cat.get('product_count', 0)} products)\n"
        
        return response

    @api.model
    def _format_stock_response(self, result, lang):
        """Format stock check results - UNCHANGED"""
        if result.get('error'):
            return result['error']
        
        product_name = result.get('product_name', 'Product')
        quantity = result.get('quantity', 0)
        status = result.get('status', 'Unknown')
        
        if lang == 'ro_RO':
            return f"Stoc pentru {product_name}: {quantity} bucăți. Status: {status}."
        elif lang == 'hu_HU':
            return f"Készlet a {product_name} termékből: {quantity} darab. Állapot: {status}."
        else:
            return f"Stock for {product_name}: {quantity} units. Status: {status}."

    @api.model
    def _format_company_response(self, result, lang):
        """Format company info results - UNCHANGED"""
        company_name = result.get('company_name', 'Our Company')
        
        response = f"{company_name}"
        
        if result.get('email'):
            response += f"\n📧 {result['email']}"
        if result.get('phone'):
            response += f"\n📞 {result['phone']}"
        if result.get('website'):
            response += f"\n🌐 {result['website']}"
        
        return response

    @api.model
    def _get_localized_text(self, key, lang):
        """Get localized text for common responses"""
        texts = {
            'no_products_found': {
                'en_US': 'No products found matching your criteria.',
                'ro_RO': 'Nu am găsit produse care să corespundă criteriilor dumneavoastră.',
                'hu_HU': 'Nem találtam a kritériumoknak megfelelő termékeket.'
            },
            'no_categories_found': {
                'en_US': 'No relevant categories found.',
                'ro_RO': 'Nu am găsit categorii relevante.',
                'hu_HU': 'Nem találtam releváns kategóriákat.'
            },
            'function_error': {
                'en_US': 'I encountered an error while analyzing your request. Please try again.',
                'ro_RO': 'Am întâmpinat o eroare în timpul analizării cererii. Vă rog să încercați din nou.',
                'hu_HU': 'Hiba történt a kérés elemzése során. Kérem, próbálja újra.'
            }
        }
        
        return texts.get(key, {}).get(lang, texts.get(key, {}).get('en_US', 'Error'))

    @api.model
    def _get_fallback_response(self, user_message, lang):
        """Generate fallback response when no function calls are made"""
        if lang == 'ro_RO':
            return "Îmi pare rău, nu am înțeles complet cererea dumneavoastră. Puteți să o reformulați?"
        elif lang == 'hu_HU':
            return "Sajnálom, nem értettem teljesen a kérését. Tudná másképp megfogalmazni?"
        else:
            return "I'm sorry, I didn't fully understand your request. Could you rephrase it?"

    @api.model
    def _get_error_response(self, function_results, lang):
        """Generate error response when all function calls failed"""
        return self._get_localized_text('function_error', lang)

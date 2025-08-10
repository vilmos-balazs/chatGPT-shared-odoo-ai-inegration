from ..models.agent_tool import register_tool, AgenticAIToolBase
import requests
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

@register_tool
class ProductMultiSearchTool(AgenticAIToolBase):
    code = "product_multisearch"
    name = "Multi-Keyword Product Search (JSON-Powered)"
    description = "Advanced product search using AI-extracted structured keywords for maximum precision"
    category = "product"
    parameters = {
        "extracted_keywords": {
            "type": "string",
            "required": True,
            "description": "JSON string with extracted keywords from keyword_extraction tool"
        },
        "lang": {
            "type": "string",
            "required": False,
            "description": "Language code (en_US, ro_RO, hu_HU)"
        },
        "limit": {
            "type": "integer",
            "required": False,
            "description": "Maximum results (default: 10)"
        }
    }
    keywords = [
        "produs", "produse", "product", "products", "termék", "termékek",
        "cauta", "search", "gaseste", "find", "keres", "recommendation", "recomanzi"
    ]
    ai_orchestration_priority = 90  # High priority, runs after keyword extraction
    ai_usage_context = "Use this tool AFTER keyword_extraction when user needs product search. Pass the JSON output from keyword_extraction directly to this tool. Perfect for complex product searches with multiple criteria."
    
    def call(self, **kwargs):
        validated = self.validate_parameters(**kwargs)
        extracted_keywords_str = validated["extracted_keywords"]
        lang = self._validate_language(validated.get("lang", "en_US"))
        limit = validated.get("limit", 10)
        
        try:
            # 🎯 PARSE EXTRACTED KEYWORDS JSON
            if isinstance(extracted_keywords_str, str):
                extracted_keywords = json.loads(extracted_keywords_str)
            else:
                extracted_keywords = extracted_keywords_str
            
            _logger.info(f"🔍 MULTI-SEARCH with AI keywords: {extracted_keywords}")
            
            # 🎯 BUILD INTELLIGENT SEARCH STRATEGY
            search_strategy = self._build_search_strategy(extracted_keywords, lang)
            
            config = self.env['meilisearch.config'].get_active_config()
            client_info = config.get_meilisearch_client()
            
            # 🎯 EXECUTE SMART SEARCH
            search_results = self._execute_strategic_search(
                client_info, config, search_strategy, limit, lang
            )
            
            # 🎯 ENHANCE RESULTS WITH KEYWORD CONTEXT
            enhanced_results = self._enhance_with_keyword_context(
                search_results, extracted_keywords, lang
            )
            
            return enhanced_results
            
        except Exception as e:
            error_msg = f"Multi-search failed: {str(e)}"
            _logger.error(f"❌ {error_msg}")
            return {
                "products": [],
                "error": error_msg,
                "search_method": "ai_multisearch_failed",
                "keywords_used": []
            }
    
    def _build_search_strategy(self, extracted_keywords, lang):
        """🧠 BUILD INTELLIGENT SEARCH STRATEGY FROM AI KEYWORDS"""
        strategy = {
            "primary_query": "",
            "secondary_queries": [],
            "filters": [],
            "boosters": []
        }
        
        # 🎯 PRIMARY QUERY: Combine most important keywords
        primary_terms = []
        
        # Objects are most important for product search
        if extracted_keywords.get("objects"):
            primary_terms.extend(extracted_keywords["objects"][:3])  # Top 3 objects
        
        # Add properties if available
        if extracted_keywords.get("properties"):
            primary_terms.extend(extracted_keywords["properties"][:2])  # Top 2 properties
        
        strategy["primary_query"] = " ".join(primary_terms) if primary_terms else "products"
        
        # 🎯 SECONDARY QUERIES: For fallback searches
        if extracted_keywords.get("rooms"):
            for room in extracted_keywords["rooms"][:2]:
                strategy["secondary_queries"].append(f"{' '.join(primary_terms)} {room}")
        
        # 🎯 CATEGORY FILTERS: Use context and rooms
        category_hints = []
        if extracted_keywords.get("rooms"):
            category_hints.extend(extracted_keywords["rooms"])
        if extracted_keywords.get("context"):
            category_hints.extend(extracted_keywords["context"])
        
        strategy["category_hints"] = category_hints
        
        # 🎯 PROPERTY BOOSTERS: Enhance ranking for properties
        if extracted_keywords.get("properties"):
            strategy["boosters"].extend(extracted_keywords["properties"])
        
        _logger.info(f"🧠 SEARCH STRATEGY: {strategy}")
        return strategy
    
    def _execute_strategic_search(self, client_info, config, strategy, limit, lang):
        """🎯 EXECUTE MULTI-STAGE STRATEGIC SEARCH"""
        lang_suffix = self._get_language_suffix(lang)
        results = []
        
        # 🎯 STAGE 1: Primary search with all keywords
        primary_params = {
            "q": strategy["primary_query"],
            "limit": limit,
            "attributesToRetrieve": ["*"],
            "showRankingScore": True,
            "attributesToSearchOn": [
                f"name_{lang_suffix}^5",
                f"description_{lang_suffix}^4",
                "default_code^6",
                "brand^5",
                f"categories_combined_{lang_suffix}^3"
            ]
        }
        
        try:
            response = requests.post(
                f"{client_info['endpoint']}/indexes/{config.products_index_name}/search",
                headers=client_info['headers_post'],
                json=primary_params,
                timeout=15
            )
            
            if response.status_code == 200:
                primary_results = response.json().get('hits', [])
                results.extend(primary_results)
                _logger.info(f"🎯 Primary search: {len(primary_results)} results")
        
        except Exception as e:
            _logger.error(f"Primary search failed: {str(e)}")
        
        # 🎯 STAGE 2: Secondary searches if not enough results
        if len(results) < limit and strategy["secondary_queries"]:
            for secondary_query in strategy["secondary_queries"][:2]:  # Max 2 secondary
                try:
                    secondary_params = primary_params.copy()
                    secondary_params["q"] = secondary_query
                    secondary_params["limit"] = limit - len(results)
                    
                    response = requests.post(
                        f"{client_info['endpoint']}/indexes/{config.products_index_name}/search",
                        headers=client_info['headers_post'],
                        json=secondary_params,
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        secondary_results = response.json().get('hits', [])
                        # Avoid duplicates
                        existing_ids = {r.get('id') for r in results}
                        new_results = [r for r in secondary_results if r.get('id') not in existing_ids]
                        results.extend(new_results)
                        _logger.info(f"🎯 Secondary search '{secondary_query}': {len(new_results)} new results")
                
                except Exception as e:
                    _logger.error(f"Secondary search failed: {str(e)}")
        
        return results[:limit]  # Limit final results
    
    def _enhance_with_keyword_context(self, search_results, extracted_keywords, lang):
        """🎯 ENHANCE RESULTS WITH KEYWORD CONTEXT"""
        if not search_results:
            return {
                "products": [],
                "total_found": 0,
                "search_method": "ai_multisearch",
                "keywords_used": self._flatten_keywords(extracted_keywords),
                "extraction_summary": extracted_keywords,
                "language_used": lang
            }
        
        # Transform results with enhanced metadata
        lang_suffix = self._get_language_suffix(lang)
        products = []
        
        for hit in search_results:
            name = hit.get(f'name_{lang_suffix}', '') or hit.get('name_en', '') or 'Unknown'
            
            products.append({
                "id": hit.get('id', 0),
                "name": name,
                "price": float(hit.get('price', 0.0)),
                "currency": "RON",
                "brand": hit.get('brand', ''),
                "available": hit.get('available', False),
                "ranking_score": hit.get('_rankingScore', 0.0),
                "language": lang,
                "keyword_matches": self._calculate_keyword_matches(hit, extracted_keywords, lang_suffix)
            })
        
        return {
            "products": products,
            "total_found": len(products),
            "search_method": "ai_multisearch",
            "keywords_used": self._flatten_keywords(extracted_keywords),
            "extraction_summary": {
                "intent": extracted_keywords.get("intent", "product_search"),
                "total_keywords": sum(len(v) if isinstance(v, list) else 0 for v in extracted_keywords.values()),
                "categories": list(extracted_keywords.keys())
            },
            "language_used": lang,
            "search_intelligence": "ai_powered_extraction"
        }
    
    def _flatten_keywords(self, extracted_keywords):
        """Flatten all keywords into a single list"""
        flattened = []
        for key, value in extracted_keywords.items():
            if isinstance(value, list):
                flattened.extend(value)
            elif key != "intent" and value:
                flattened.append(str(value))
        return flattened[:10]  # Limit for display
    
    def _calculate_keyword_matches(self, hit, extracted_keywords, lang_suffix):
        """Calculate how many keywords match this product"""
        product_text = " ".join([
            hit.get(f'name_{lang_suffix}', ''),
            hit.get(f'description_{lang_suffix}', ''),
            hit.get('brand', ''),
            hit.get(f'categories_combined_{lang_suffix}', '')
        ]).lower()
        
        matches = []
        for key, keywords in extracted_keywords.items():
            if isinstance(keywords, list):
                for keyword in keywords:
                    if keyword.lower() in product_text:
                        matches.append(keyword)
        
        return matches
    
    def _get_language_suffix(self, lang_code):
        return {'en_US': 'en', 'ro_RO': 'ro', 'hu_HU': 'hu'}.get(lang_code, 'en')

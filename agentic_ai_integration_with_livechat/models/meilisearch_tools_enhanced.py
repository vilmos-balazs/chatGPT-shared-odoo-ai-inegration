from ..models.agent_tool import register_tool, AgenticAIToolBase
import requests
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

@register_tool
class MeiliProductSearchEnhanced(AgenticAIToolBase):
    code = "product_search_enhanced"
    name = "Enhanced Multi-Keyword Product Search"
    description = "Advanced product search using ALL extracted keywords with MeiliSearch intelligence"
    category = "product"
    parameters = {
        "query": {
            "type": "string", 
            "required": True,
            "description": "ALL search keywords combined (e.g., 'lac zowohome mat parchet')"
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
        "lac", "vopsea", "paint", "festék", "parchet", "parquet", "parketta", 
        "adeziv", "adhesive", "ragasztó", "lemn", "wood", "fa",
        "zowohome", "kleiberit", "dulux", "caparol"
    ]
    ai_orchestration_priority = 90
    
    def call(self, **kwargs):
        validated = self.validate_parameters(**kwargs)
        query = validated["query"]
        lang = self._validate_language(validated.get("lang", "en_US"))
        limit = validated.get("limit", 10)
        
        _logger.info(f"🔍 ENHANCED Multi-keyword search: '{query}' in {lang}")
        
        try:
            config = self.env['meilisearch.config'].get_active_config()
            client_info = config.get_meilisearch_client()
            
            # 🎯 MULTI-KEYWORD SEARCH: Use all terms from query
            search_params = {
                "q": query,  # Use full query with all keywords
                "limit": limit,
                "attributesToRetrieve": ["*"],
                "showRankingScore": True,
            }
            
            # 🌍 LANGUAGE-SPECIFIC SEARCH STRATEGY
            lang_suffix = self._get_language_suffix(lang)
            
            # Enhanced search attributes with keyword boosting
            search_attributes = [
                f"name_{lang_suffix}^4",           # Highest boost for name in target language
                f"description_{lang_suffix}^3",   # High boost for description in target language  
                "default_code^5",                 # Very high boost for SKU/code
                "brand^4",                        # High boost for brand
                f"categories_combined_{lang_suffix}^3", # High boost for categories in target language
            ]
            
            # Add other languages with lower priority
            other_languages = ['en', 'ro', 'hu']
            if lang_suffix in other_languages:
                other_languages.remove(lang_suffix)
            
            for other_lang in other_languages:
                search_attributes.extend([
                    f"name_{other_lang}^2",
                    f"description_{other_lang}^1.5", 
                    f"categories_combined_{other_lang}^2"
                ])
            
            search_params["attributesToSearchOn"] = search_attributes
            
            # Execute search
            response = requests.post(
                f"{client_info['endpoint']}/indexes/{config.products_index_name}/search",
                headers=client_info['headers_post'],
                json=search_params,
                timeout=15
            )
            
            if response.status_code != 200:
                return {
                    "products": [],
                    "error": f"Search failed: HTTP {response.status_code}",
                    "search_method": "enhanced_multi_keyword"
                }
            
            result = response.json()
            hits = result.get('hits', [])
            
            _logger.info(f"🎯 Enhanced search found {len(hits)} results for '{query}'")
            
            # Transform results
            products = []
            for hit in hits:
                name = hit.get(f'name_{lang_suffix}', '') or hit.get('name_en', '') or 'Unknown'
                
                products.append({
                    "id": hit.get('id', 0),
                    "name": name,
                    "price": float(hit.get('price', 0.0)),
                    "currency": "RON",
                    "brand": hit.get('brand', ''),
                    "available": hit.get('available', False),
                    "ranking_score": hit.get('_rankingScore', 0.0),
                    "language": lang
                })
            
            return {
                "products": products,
                "total_found": len(products),
                "search_method": "enhanced_multi_keyword",
                "language_used": lang,
                "query": query,
                "keywords_used": query.split()  # Show all keywords used
            }
            
        except Exception as e:
            error_msg = f"Enhanced multi-keyword search error: {str(e)}"
            _logger.error(error_msg)
            return {
                "products": [],
                "error": error_msg,
                "search_method": "enhanced_multi_keyword"
            }
    
    def _get_language_suffix(self, lang_code):
        return {'en_US': 'en', 'ro_RO': 'ro', 'hu_HU': 'hu'}.get(lang_code, 'en')

from ..models.agent_tool import register_tool, AgenticAIToolBase
import requests
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

@register_tool
class MeiliProductSearchTool(AgenticAIToolBase):
    code = "product_search_enhanced"
    name = "Enhanced Product Search (MeiliSearch)"
    description = "Enhanced product search using MeiliSearch with multilingual support and typo tolerance"
    category = "product"
    parameters = {
        "query": {
            "type": "string",
            "required": True,
            "description": "Search term for products"
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
        "product", "produs", "termék", "search", "find", "cauta", "gaseste", "keres", 
        "aveti", "have", "van", "show", "arata", "lac", "vopsea", "paint", "festék",
        "zowohome", "kleiberit", "dulux", "caparol"
    ]
    ai_orchestration_priority = 100  # Higher priority than old tool
    
    def call(self, **kwargs):
        validated = self.validate_parameters(**kwargs)
        query = validated["query"]
        lang = self._validate_language(validated.get("lang", "en_US"))
        limit = validated.get("limit", 10)
        
        _logger.info(f"🔍 Enhanced search: '{query}' in {lang}")
        
        try:
            config = self.env['meilisearch.config'].get_active_config()
            client_info = config.get_meilisearch_client()
            
            search_params = {
                "q": query,
                "limit": limit
            }
            
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
                    "search_method": "enhanced_meilisearch"
                }
            
            result = response.json()
            hits = result.get('hits', [])
            
            products = []
            for hit in hits:
                lang_suffix = self._get_language_suffix(lang)
                name = hit.get(f'name_{lang_suffix}', '') or hit.get('name_en', '') or 'Unknown'
                
                products.append({
                    "id": hit.get('id', 0),
                    "name": name,
                    "price": float(hit.get('price', 0.0)),
                    "currency": "RON",
                    "brand": hit.get('brand', ''),
                    "available": hit.get('available', False),
                    "language": lang
                })
            
            return {
                "products": products,
                "total_found": len(products),
                "search_method": "enhanced_meilisearch",
                "language_used": lang,
                "query": query
            }
            
        except Exception as e:
            error_msg = f"Enhanced search error: {str(e)}"
            _logger.error(error_msg)
            return {
                "products": [],
                "error": error_msg,
                "search_method": "enhanced_meilisearch"
            }
    
    def _get_language_suffix(self, lang_code):
        return {'en_US': 'en', 'ro_RO': 'ro', 'hu_HU': 'hu'}.get(lang_code, 'en')

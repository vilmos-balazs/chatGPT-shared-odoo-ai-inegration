from ..models.agent_tool import register_tool, AgenticAIToolBase
import requests
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

@register_tool
class MeiliProductSearchSimple(AgenticAIToolBase):
    code = "meili_product_search_simple"
    name = "Simple MeiliSearch Product Search"
    description = "Basic MeiliSearch product search without advanced features for testing"
    category = "meilisearch"
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
    keywords = ["product", "search", "find", "meili", "simple"]
    
    def call(self, **kwargs):
        validated = self.validate_parameters(**kwargs)
        query = validated["query"]
        lang = self._validate_language(validated.get("lang", "en_US"))
        limit = validated.get("limit", 10)
        
        try:
            config = self.env['meilisearch.config'].get_active_config()
            client_info = config.get_meilisearch_client()
            
            # SIMPLE search parameters - no advanced features
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
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "search_type": "simple_meilisearch"
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
                    "price": hit.get('price', 0.0),
                    "brand": hit.get('brand', ''),
                    "available": hit.get('available', False)
                })
            
            return {
                "products": products,
                "total_found": len(products),
                "search_type": "simple_meilisearch",
                "language_used": lang
            }
            
        except Exception as e:
            return {
                "products": [],
                "error": str(e),
                "search_type": "simple_meilisearch"
            }
    
    def _get_language_suffix(self, lang_code):
        return {'en_US': 'en', 'ro_RO': 'ro', 'hu_HU': 'hu'}.get(lang_code, 'en')

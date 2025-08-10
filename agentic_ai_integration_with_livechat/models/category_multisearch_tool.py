from ..models.agent_tool import register_tool, AgenticAIToolBase
import requests
import json
import logging

_logger = logging.getLogger(__name__)

@register_tool
class CategoryMultiSearchTool(AgenticAIToolBase):
    code = "category_multisearch"
    name = "Multi-Keyword Category Search (JSON-Powered)"
    description = "Advanced category search using AI-extracted structured keywords"
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
            "description": "Maximum results (default: 15)"
        }
    }
    keywords = [
        "category", "categories", "categorie", "categorii", "kategória", "kategóriák",
        "section", "sectiune", "browse", "tip", "tipuri", "type", "types"
    ]
    ai_orchestration_priority = 88  # High priority, runs after keyword extraction
    ai_usage_context = "Use this tool AFTER keyword_extraction when user asks about categories or browsing. Pass the JSON output from keyword_extraction to find relevant product categories."
    
    def call(self, **kwargs):
        validated = self.validate_parameters(**kwargs)
        extracted_keywords_str = validated["extracted_keywords"]
        lang = self._validate_language(validated.get("lang", "en_US"))
        limit = validated.get("limit", 15)
        
        try:
            # �� PARSE EXTRACTED KEYWORDS JSON
            if isinstance(extracted_keywords_str, str):
                extracted_keywords = json.loads(extracted_keywords_str)
            else:
                extracted_keywords = extracted_keywords_str
            
            _logger.info(f"🏷️ CATEGORY MULTI-SEARCH with AI keywords: {extracted_keywords}")
            
            config = self.env['meilisearch.config'].get_active_config()
            client_info = config.get_meilisearch_client()
            
            # 🎯 BUILD CATEGORY SEARCH STRATEGY
            category_terms = self._build_category_search_terms(extracted_keywords)
            
            # 🎯 EXECUTE CATEGORY SEARCH
            categories = self._search_categories_with_keywords(
                client_info, config, category_terms, lang, limit
            )
            
            return {
                "categories": categories,
                "total_found": len(categories),
                "search_method": "ai_category_multisearch",
                "keywords_used": self._flatten_keywords(extracted_keywords),
                "extraction_summary": extracted_keywords,
                "language_used": lang
            }
            
        except Exception as e:
            error_msg = f"Category multi-search failed: {str(e)}"
            _logger.error(f"❌ {error_msg}")
            return {
                "categories": [],
                "error": error_msg,
                "search_method": "ai_category_multisearch_failed"
            }
    
    def _build_category_search_terms(self, extracted_keywords):
        """🧠 BUILD SMART CATEGORY SEARCH TERMS"""
        search_terms = []
        
        # 🎯 PRIMARY: Objects often correspond to categories
        if extracted_keywords.get("objects"):
            search_terms.extend(extracted_keywords["objects"])
        
        # 🎯 SECONDARY: Rooms indicate category contexts
        if extracted_keywords.get("rooms"):
            search_terms.extend(extracted_keywords["rooms"])
        
        # 🎯 TERTIARY: Context provides category hints
        if extracted_keywords.get("context"):
            search_terms.extend(extracted_keywords["context"])
        
        # 🎯 QUATERNARY: Properties might indicate category types
        if extracted_keywords.get("properties"):
            search_terms.extend(extracted_keywords["properties"][:2])  # Limit properties
        
        _logger.info(f"🏷️ Category search terms: {search_terms}")
        return search_terms[:8]  # Limit total terms
    
    def _search_categories_with_keywords(self, client_info, config, search_terms, lang, limit):
        """�� EXECUTE MULTI-TERM CATEGORY SEARCH"""
        lang_suffix = self._get_language_suffix(lang)
        found_categories = {}
        
        # 🎯 SEARCH STRATEGY: Try individual terms and combinations
        search_queries = []
        
        # Individual terms
        search_queries.extend(search_terms[:5])  # Top 5 individual terms
        
        # Combinations of 2 terms
        for i, term1 in enumerate(search_terms[:3]):
            for term2 in search_terms[i+1:4]:
                search_queries.append(f"{term1} {term2}")
        
        _logger.info(f"🏷️ Executing {len(search_queries)} category searches")
        
        for query in search_queries:
            try:
                search_params = {
                    "q": query,
                    "limit": limit * 2,  # Get more for deduplication
                    "attributesToSearchOn": [
                        f"categories_combined_{lang_suffix}^3",
                        f"categories_combined_en^2",
                        f"categories_combined_ro^1",
                        f"categories_combined_hu^1"
                    ],
                    "attributesToRetrieve": [
                        f"categories_combined_{lang_suffix}",
                        f"categories_{lang_suffix}",
                        "id", "template_id"
                    ]
                }
                
                response = requests.post(
                    f"{client_info['endpoint']}/indexes/{config.products_index_name}/search",
                    headers=client_info['headers_post'],
                    json=search_params,
                    timeout=10
                )
                
                if response.status_code == 200:
                    hits = response.json().get('hits', [])
                    
                    # Extract unique categories
                    for hit in hits:
                        categories_list = hit.get(f'categories_{lang_suffix}', [])
                        if not categories_list:
                            categories_list = hit.get('categories_en', [])
                        
                        for category_path in categories_list[:3]:  # Limit per product
                            if category_path and category_path not in found_categories:
                                found_categories[category_path] = {
                                    "name": category_path,
                                    "hierarchy_path": category_path,
                                    "product_count": 0,
                                    "language": lang,
                                    "matched_keywords": [query]
                                }
                            elif category_path in found_categories:
                                # Add matched keyword
                                if query not in found_categories[category_path]["matched_keywords"]:
                                    found_categories[category_path]["matched_keywords"].append(query)
            
            except Exception as e:
                _logger.error(f"Category search failed for '{query}': {str(e)}")
                continue
        
        # �� ENHANCE WITH PRODUCT COUNTS
        categories_list = list(found_categories.values())[:limit]
        
        for category in categories_list:
            try:
                category["product_count"] = self._count_products_in_category(
                    client_info, config, category["name"], lang_suffix
                )
            except:
                category["product_count"] = 0
        
        # 🎯 SORT BY RELEVANCE (product count + keyword matches)
        categories_list.sort(
            key=lambda x: (len(x["matched_keywords"]), x["product_count"]), 
            reverse=True
        )
        
        return categories_list
    
    def _count_products_in_category(self, client_info, config, category_path, lang_suffix):
        """Count products in category"""
        try:
            search_params = {
                "q": "",
                "limit": 1,
                "filter": f"categories_combined_{lang_suffix} CONTAINS '{category_path}' OR categories_combined_en CONTAINS '{category_path}'",
            }
            
            response = requests.post(
                f"{client_info['endpoint']}/indexes/{config.products_index_name}/search",
                headers=client_info['headers_post'],
                json=search_params,
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json().get('estimatedTotalHits', 0)
        except:
            pass
        return 0
    
    def _flatten_keywords(self, extracted_keywords):
        """Flatten all keywords into a single list"""
        flattened = []
        for key, value in extracted_keywords.items():
            if isinstance(value, list):
                flattened.extend(value)
            elif key != "intent" and value:
                flattened.append(str(value))
        return flattened
    
    def _get_language_suffix(self, lang_code):
        return {'en_US': 'en', 'ro_RO': 'ro', 'hu_HU': 'hu'}.get(lang_code, 'en')

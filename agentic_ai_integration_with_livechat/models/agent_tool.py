from abc import ABC, abstractmethod
from odoo import models, fields, api
import logging
import json

_logger = logging.getLogger(__name__)

class AgenticAIToolBase(ABC):
    code = None
    name = None
    description = None
    parameters = {}
    keywords = []
    examples = []
    output_format = {}
    timeout = 30
    requires_auth = False
    category = "general"

    def __init__(self, env):
        self.env = env

    @abstractmethod
    def call(self, **kwargs):
        pass

    def _validate_language(self, lang):
        """Validate language is supported in Odoo, fallback to en_US"""
        SUPPORTED_LANGUAGES = ['en_US', 'ro_RO', 'hu_HU']
        validated_lang = lang if lang in SUPPORTED_LANGUAGES else 'en_US'
        if validated_lang != lang:
            _logger.info(f"Language {lang} not supported, falling back to {validated_lang}")
        return validated_lang

    def _get_language_name(self, lang_code):
        """Get human-readable language name"""
        lang_names = {
            'en_US': 'English',
            'ro_RO': 'Romanian', 
            'hu_HU': 'Hungarian'
        }
        return lang_names.get(lang_code, 'English')

    def validate_parameters(self, **kwargs):
        errors = []
        validated_params = {}
        for param_name, param_def in self.parameters.items():
            if param_def.get("required", False) and param_name not in kwargs:
                errors.append(f"Missing required parameter: {param_name}")
                continue
            if param_name in kwargs:
                value = kwargs[param_name]
                param_type = param_def.get("type", "string")
                if param_type == "string" and not isinstance(value, str):
                    errors.append(f"Parameter {param_name} must be string")
                elif param_type == "integer" and not isinstance(value, int):
                    errors.append(f"Parameter {param_name} must be integer")
                elif param_type == "boolean" and not isinstance(value, bool):
                    errors.append(f"Parameter {param_name} must be boolean")
                validated_params[param_name] = value
        if errors:
            raise ValueError(f"Parameter validation failed: {', '.join(errors)}")
        return validated_params

    def get_function_schema(self):
        return {
            "name": self.code,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    param_name: {
                        "type": param_def.get("type", "string"),
                        "description": param_def.get("description", ""),
                        **({"enum": param_def["enum"]} if "enum" in param_def else {})
                    }
                    for param_name, param_def in self.parameters.items()
                },
                "required": [
                    param_name for param_name, param_def in self.parameters.items()
                    if param_def.get("required", False)
                ]
            }
        }

    def matches_intent(self, user_message):
        message_lower = user_message.lower()
        return any(keyword in message_lower for keyword in self.keywords)

    def get_usage_example(self):
        if self.examples:
            return self.examples[0]
        return None

class AgenticAIToolRegistry:
    def __init__(self):
        self._tools = {}
        self._categories = {}

    def register(self, tool_class):
        if not tool_class.code:
            raise ValueError(f"Tool {tool_class.__name__} must have a code")
        self._tools[tool_class.code] = tool_class
        category = getattr(tool_class, 'category', 'general')
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(tool_class.code)
        _logger.info(f"Registered tool: {tool_class.code} ({tool_class.name})")

    def get_tool(self, code, env):
        if code not in self._tools:
            raise ValueError(f"Tool '{code}' not found")
        return self._tools[code](env)

    def find_matching_tools(self, user_message, category=None):
        matching_tools = []
        tools_to_check = self._tools.values()
        if category:
            tools_to_check = [
                self._tools[code] for code in self._categories.get(category, [])
            ]
        for tool_class in tools_to_check:
            if tool_class(None).matches_intent(user_message):
                matching_tools.append(tool_class.code)
        return matching_tools

    def get_all_tools_metadata(self, env):
        return [
            {
                "code": tool_class.code,
                "name": tool_class.name,
                "description": tool_class.description,
                "category": getattr(tool_class, 'category', 'general'),
                "keywords": getattr(tool_class, 'keywords', []),
                "parameters": getattr(tool_class, 'parameters', {}),
                "schema": tool_class(env).get_function_schema()
            }
            for tool_class in self._tools.values()
        ]

    def get_function_schemas(self, env):
        return [tool_class(env).get_function_schema() for tool_class in self._tools.values()]

    def values(self):
        return self._tools.values()

AGENTIC_AI_TOOL_REGISTRY = AgenticAIToolRegistry()

def register_tool(tool_class):
    AGENTIC_AI_TOOL_REGISTRY.register(tool_class)
    return tool_class

@register_tool
class ProductSearchTool(AgenticAIToolBase):
    code = "product_search"
    name = "Product Search"
    description = "Search for products in the company catalog by name, category, or description with multilingual support"
    category = "product"
    parameters = {
        "query": {
            "type": "string",
            "required": True,
            "description": "Search term for product name or description"
        },
        "lang": {
            "type": "string",
            "required": False,
            "description": "Language code (en_US, ro_RO, hu_HU). Auto-detected if not provided."
        },
        "category_id": {
            "type": "integer",
            "required": False,
            "description": "Product category ID to filter results"
        },
        "limit": {
            "type": "integer",
            "required": False,
            "description": "Maximum number of results (default: 10)"
        }
    }
    keywords = ["product", "item", "search", "find", "catalog", "buy", "purchase", "what", "show me", "produs", "articol", "cauta", "gaseste", "termék", "keresés", "talál", "aveti", "lac", "vopsea"]
    examples = [
        {
            "input": {"query": "zowohome", "lang": "en_US", "limit": 2},
            "output": {
                "products": [
                    {
                        "name": "ZowoHome 8400 - mat Coating",
                        "language": "en_US"
                    }
                ]
            },
            "description": "Search ZowoHome products in English"
        },
        {
            "input": {"query": "zowohome", "lang": "ro_RO", "limit": 2},
            "output": {
                "products": [
                    {
                        "name": "ZowoHome 8400- lac interior si parchet -mat",
                        "language": "ro_RO"
                    }
                ]
            },
            "description": "Căutare produse ZowoHome în română"
        },
        {
            "input": {"query": "zowohome", "lang": "hu_HU"},
            "output": {
                "products": [
                    {
                        "name": "ZowoHome 8400- mat Parketta lakk",
                        "language": "hu_HU"
                    }
                ]
            },
            "description": "ZowoHome termékek keresése magyar nyelven"
        }
    ]
    output_format = {
        "products": [
            {
                "id": "int",
                "name": "string (translated via native Odoo)",
                "qty": "float",
                "uom_name": "string",
                "price": "float",
                "price_uom": "string",
                "total_price": "float",
                "currency": "string",
                "available": "boolean",
                "category": "string (translated)",
                "description": "string (translated)",
                "language": "string"
            }
        ],
        "total_found": "int",
        "language_used": "string",
        "translation_method": "native_odoo_context"
    }
    
    def call(self, **kwargs):
        validated = self.validate_parameters(**kwargs)
        query = validated["query"]
        lang = self._validate_language(validated.get("lang", "en_US"))
        category_id = validated.get("category_id")
        limit = validated.get("limit", 10)
        
        # 🔍 DEBUG: Log language context
        _logger.info(f"🌍 ProductSearch: query='{query}', lang='{lang}'")
        
        # 🌍 NATIVE ODOO TRANSLATION: Apply language context to the entire environment
        domain = [
            "|", "|",
            ("name", "ilike", query),
            ("description", "ilike", query),
            ("default_code", "ilike", query)
        ]
        if category_id:
            domain.append(("categ_id", "=", category_id))
        
        # 🎯 CORRECT: Use native Odoo translation with language context
        products = self.env['product.template'].with_context(lang=lang).search(domain, limit=limit)
        
        result_products = []
        
        for product in products:
            # 🌍 NATIVE TRANSLATION: Fields are automatically translated by Odoo
            # No manual JSONB parsing needed - Odoo handles this transparently!
            
            # 🔍 DEBUG: Log what we get from Odoo
            _logger.info(f"🌍 Product {product.id} in {lang}: '{product.name}'")
            
            qty = getattr(product, "package_qty", 1) or 1
            uom_name = product.uom_id.name if product.uom_id else ""
            price = product.list_price or 0.0
            price_currency = product.currency_id.name if product.currency_id else "RON"
            total_price = price * qty
            
            result_products.append({
                "id": product.id,
                "name": product.name,  # 🌍 AUTOMATICALLY TRANSLATED BY ODOO
                "qty": qty,
                "uom_name": uom_name,
                "price": price,
                "price_uom": f"{price_currency}/{uom_name}" if uom_name else price_currency,
                "total_price": total_price,
                "currency": price_currency,
                "available": product.qty_available > 0 if hasattr(product, 'qty_available') else True,
                "category": product.categ_id.name if product.categ_id else "Uncategorized",  # 🌍 TRANSLATED
                "description": product.description or "",  # 🌍 TRANSLATED
                "language": lang
            })
        
        return {
            "products": result_products,
            "total_found": len(result_products),
            "query": query,
            "language_used": lang,
            "translation_method": "native_odoo_context",
            "search_language_note": f"Results in {self._get_language_name(lang)} using Odoo native translation"
        }

@register_tool
class ProductCategoryTool(AgenticAIToolBase):
    code = "product_category"
    name = "Product Category Browser"
    description = "Get product categories, browse category hierarchy, and find category information with multilingual support"
    category = "product"
    parameters = {
        "action": {
            "type": "string",
            "required": False,
            "enum": ["list_all", "get_children", "search", "get_hierarchy", "get_by_id"],
            "description": "Action to perform (default: list_all)"
        },
        "lang": {
            "type": "string",
            "required": False,
            "description": "Language code (en_US, ro_RO, hu_HU). Auto-detected if not provided."
        },
        "parent_id": {
            "type": "integer",
            "required": False,
            "description": "Parent category ID for getting children"
        },
        "category_id": {
            "type": "integer",
            "required": False,
            "description": "Specific category ID to get details"
        },
        "search_term": {
            "type": "string",
            "required": False,
            "description": "Search term for category names"
        },
        "limit": {
            "type": "integer",
            "required": False,
            "description": "Maximum number of results (default: 20)"
        },
        "include_product_count": {
            "type": "boolean",
            "required": False,
            "description": "Include product count for each category (default: true)"
        }
    }
    keywords = ["category", "categories", "browse", "section", "department", "type", "classification", "categorie", "sectiune", "tip", "kategória", "osztály", "típus"]
    
    def call(self, **kwargs):
        validated = self.validate_parameters(**kwargs)
        action = validated.get("action", "list_all")
        lang = self._validate_language(validated.get("lang", "en_US"))
        limit = validated.get("limit", 20)
        include_product_count = validated.get("include_product_count", True)
        
        # 🌍 NATIVE ODOO TRANSLATION: Apply language context
        Category = self.env['product.category'].with_context(lang=lang)
        
        if action == "list_all":
            domain = []
            if not validated.get("parent_id"):
                domain = [("parent_id", "=", False)]
            categories_data = Category.search(domain, limit=limit)
        elif action == "get_children":
            parent_id = validated.get("parent_id")
            if not parent_id:
                raise ValueError("parent_id is required for get_children action")
            categories_data = Category.search([("parent_id", "=", parent_id)], limit=limit)
        elif action == "search":
            search_term = validated.get("search_term")
            if not search_term:
                raise ValueError("search_term is required for search action")
            categories_data = Category.search([("name", "ilike", search_term)], limit=limit)
        elif action == "get_by_id":
            category_id = validated.get("category_id")
            if not category_id:
                raise ValueError("category_id is required for get_by_id action")
            categories_data = Category.browse(category_id)
        elif action == "get_hierarchy":
            categories_data = Category.search([], limit=limit)
        else:
            raise ValueError(f"Unknown action: {action}")
        
        result_categories = []
        for category in categories_data:
            product_count = 0
            if include_product_count:
                product_count = self.env['product.template'].search_count([('categ_id', '=', category.id)])
            
            has_children = bool(self.env['product.category'].search_count([('parent_id', '=', category.id)]))
            
            # 🌍 NATIVE TRANSLATION: Build translated path
            path_parts = []
            current = category
            while current:
                path_parts.insert(0, current.name)  # Already translated via context
                current = current.parent_id
            category_path = " > ".join(path_parts)
            
            category_data = {
                "id": category.id,
                "name": category.name,  # 🌍 TRANSLATED BY ODOO
                "parent_id": category.parent_id.id if category.parent_id else None,
                "parent_name": category.parent_id.name if category.parent_id else None,  # 🌍 TRANSLATED
                "product_count": product_count,
                "has_children": has_children,
                "path": category_path,  # 🌍 TRANSLATED PATH
                "description": getattr(category, 'description', '') or "",  # 🌍 TRANSLATED
                "language": lang
            }
            result_categories.append(category_data)
        
        return {
            "categories": result_categories,
            "total_found": len(result_categories),
            "action_performed": action,
            "language_used": lang,
            "translation_method": "native_odoo_context"
        }

@register_tool
class StockCheckTool(AgenticAIToolBase):
    code = "stock_check"
    name = "Stock Level Check"
    description = "Check inventory/stock levels for products with multilingual support"
    category = "inventory"
    parameters = {
        "product_id": {
            "type": "integer",
            "required": False,
            "description": "Specific product ID to check"
        },
        "product_name": {
            "type": "string",
            "required": False,
            "description": "Product name to search and check stock"
        },
        "lang": {
            "type": "string",
            "required": False,
            "description": "Language code (en_US, ro_RO, hu_HU). Auto-detected if not provided."
        }
    }
    keywords = ["stock", "inventory", "available", "quantity", "how many", "in stock", "stoc", "inventar", "disponibil", "cantitate", "raktár", "készlet", "elérhető", "mennyiség"]
    
    def call(self, **kwargs):
        validated = self.validate_parameters(**kwargs)
        lang = self._validate_language(validated.get("lang", "en_US"))
        
        if not validated.get("product_id") and not validated.get("product_name"):
            raise ValueError("Either product_id or product_name is required")
        
        # 🌍 NATIVE ODOO TRANSLATION: Apply language context
        Product = self.env['product.template'].with_context(lang=lang)
        
        if validated.get("product_id"):
            product = Product.browse(validated["product_id"])
        else:
            product = Product.search([
                ("name", "ilike", validated["product_name"])
            ], limit=1)
        
        if not product:
            return {
                "error": self._get_localized_message("Product not found", lang),
                "query": validated,
                "language": lang
            }
        
        qty_available = getattr(product, 'qty_available', 0)
        status = self._get_stock_status(qty_available, lang)
        
        return {
            "product_id": product.id,
            "product_name": product.name,  # 🌍 AUTOMATICALLY TRANSLATED
            "quantity": qty_available,
            "status": status,  # 🌍 TRANSLATED
            "unit": product.uom_id.name if product.uom_id else "Units",
            "language": lang,
            "translation_method": "native_odoo_context"
        }
    
    def _get_stock_status(self, qty, lang):
        """Get localized stock status message"""
        if qty > 0:
            status_translations = {
                'en_US': 'In Stock',
                'ro_RO': 'În Stoc', 
                'hu_HU': 'Raktáron'
            }
        else:
            status_translations = {
                'en_US': 'Out of Stock',
                'ro_RO': 'Lipsă Stoc',
                'hu_HU': 'Nincs Raktáron'
            }
        return status_translations.get(lang, status_translations['en_US'])
    
    def _get_localized_message(self, message, lang):
        """Get localized error messages"""
        translations = {
            'Product not found': {
                'en_US': 'Product not found',
                'ro_RO': 'Produs negăsit',
                'hu_HU': 'Termék nem található'
            }
        }
        return translations.get(message, {}).get(lang, message)

@register_tool
class CompanyInfoTool(AgenticAIToolBase):
    code = "company_info"
    name = "Company Information"
    description = "Get basic company information like name, address, contact details with multilingual support"
    category = "general"
    parameters = {
        "info_type": {
            "type": "string",
            "required": False,
            "enum": ["basic", "contact", "address", "all"],
            "description": "Type of company info to retrieve (default: basic)"
        },
        "lang": {
            "type": "string",
            "required": False,
            "description": "Language code (en_US, ro_RO, hu_HU). Auto-detected if not provided."
        }
    }
    keywords = ["company", "about", "contact", "address", "phone", "email", "who", "business", "companie", "despre", "contact", "adresa", "telefon", "cég", "kapcsolat", "cím", "telefon"]
    
    def call(self, **kwargs):
        validated = self.validate_parameters(**kwargs)
        info_type = validated.get("info_type", "basic")
        lang = self._validate_language(validated.get("lang", "en_US"))
        
        # 🌍 NATIVE ODOO TRANSLATION: Apply language context
        company = self.env.user.company_id.with_context(lang=lang)
        
        result = {
            "company_name": company.name,
            "language": lang,
            "translation_method": "native_odoo_context"
        }
        
        if info_type in ["basic", "all"]:
            result.update({
                "currency": company.currency_id.name,
                "country": company.country_id.name if company.country_id else None,  # 🌍 TRANSLATED
            })
        
        if info_type in ["contact", "all"]:
            result.update({
                "email": company.email,
                "phone": company.phone,
                "website": company.website,
            })
        
        if info_type in ["address", "all"]:
            result.update({
                "street": company.street,
                "city": company.city,
                "zip": company.zip,
                "country": company.country_id.name if company.country_id else None,  # �� TRANSLATED
            })
        
        return result

def get_registry():
    return AGENTIC_AI_TOOL_REGISTRY

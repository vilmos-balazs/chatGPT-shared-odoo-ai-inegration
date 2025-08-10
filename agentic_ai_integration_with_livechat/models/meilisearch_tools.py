from ..models.agent_tool import register_tool, AgenticAIToolBase
import requests
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

@register_tool
class MeiliSyncTool(AgenticAIToolBase):
    code = "meili_sync"
    name = "MeiliSearch Sync Tool"
    description = "Synchronize Odoo product variants to MeiliSearch index with multilingual JSONB flattening"
    category = "meilisearch"
    parameters = {
        "sync_type": {
            "type": "string",
            "required": False,
            "enum": ["full", "incremental", "single", "clear_and_full"],
            "description": "Type of sync: full (all variants), incremental (recent changes), single (specific variant), clear_and_full (clear index first)"
        },
        "product_id": {
            "type": "integer", 
            "required": False,
            "description": "Specific product variant ID for single sync"
        },
        "batch_size": {
            "type": "integer",
            "required": False,
            "description": "Number of product variants to upload per batch to MeiliSearch (default: 50)"
        },
        "max_products": {
            "type": "integer",
            "required": False,
            "description": "Maximum total products to sync (default: no limit for full sync)"
        },
        "force_reindex": {
            "type": "boolean",
            "required": False,
            "description": "Force complete reindex even for incremental sync"
        }
    }
    keywords = ["sync", "index", "meilisearch", "update", "reindex", "search engine", "variants"]
    examples = [
        {
            "input": {"sync_type": "clear_and_full", "batch_size": 50},
            "output": {"synced": 1500, "errors": 0, "duration": "12.3s"},
            "description": "Clear index and do full sync of ALL product variants"
        }
    ]
    output_format = {
        "synced": "int - Number of product variants successfully synced",
        "errors": "int - Number of sync errors",
        "duration": "string - Time taken for sync operation",
        "error_details": "list - Details of any errors that occurred",
        "last_sync_date": "string - Timestamp of sync completion"
    }
    
    def call(self, **kwargs):
        validated = self.validate_parameters(**kwargs)
        sync_type = validated.get("sync_type", "incremental")
        product_id = validated.get("product_id")
        batch_size = validated.get("batch_size", 50)
        max_products = validated.get("max_products")
        force_reindex = validated.get("force_reindex", False)
        
        start_time = datetime.now()
        _logger.info(f"🔄 Starting MeiliSearch variant sync: type={sync_type}, batch_size={batch_size}, max_products={max_products}")
        
        try:
            # Get MeiliSearch configuration
            config = self.env['meilisearch.config'].get_active_config()
            client_info = config.get_meilisearch_client()
            
            # ✅ FIX 1: Clear index for clear_and_full sync type
            if sync_type == "clear_and_full":
                _logger.info("🗑️ Clearing MeiliSearch index before full sync...")
                try:
                    clear_response = requests.delete(
                        f"{client_info['endpoint']}/indexes/{config.products_index_name}/documents",
                        headers=client_info['headers_post'],
                        timeout=30
                    )
                    _logger.info(f"🗑️ Clear index response: {clear_response.status_code}")
                    if clear_response.status_code not in [200, 201, 202, 204]:
                        _logger.warning(f"Clear index failed: {clear_response.status_code}")
                except Exception as e:
                    _logger.warning(f"Failed to clear index: {str(e)}")
                
                # Treat as full sync after clearing
                sync_type = "full"
            
            # Determine product VARIANTS to sync
            if sync_type == "single" and product_id:
                products = self.env['product.product'].browse(product_id)
                if not products.exists():
                    return {
                        "synced": 0,
                        "errors": 1,
                        "duration": "0s",
                        "error_details": [f"Product variant ID {product_id} not found"]
                    }
            elif sync_type == "full" or force_reindex:
                domain = [('active', '=', True)]
                if max_products:
                    products = self.env['product.product'].search(domain, limit=max_products)
                    _logger.info(f"📦 Limited to {max_products} variants for testing")
                else:
                    products = self.env['product.product'].search(domain)
                    _logger.info(f"📦 Full sync - found {len(products)} total variants")
            else:  # incremental
                last_sync = config.last_sync_date
                domain = [('active', '=', True)]
                if last_sync:
                    domain.append(('write_date', '>', last_sync))
                products = self.env['product.product'].search(domain)
            
            _logger.info(f"📦 Found {len(products)} product variants to sync")
            
            if not products:
                return {
                    "synced": 0,
                    "errors": 0,
                    "duration": "0s",
                    "message": "No product variants to sync",
                    "products_found": 0
                }
            
            # DEBUG: Check for specific product template
            eva_hotmelt_products = products.filtered(lambda p: 'EVA Hotmelt' in (p.product_tmpl_id.name or ''))
            if eva_hotmelt_products:
                _logger.info(f"🔍 DEBUG: Found {len(eva_hotmelt_products)} EVA Hotmelt variants:")
                for p in eva_hotmelt_products[:3]:
                    _logger.info(f"  - Variant {p.id}, Template {p.product_tmpl_id.id}: {p.product_tmpl_id.name}")
                    _logger.info(f"    Write date: {p.write_date}")
                    _logger.info(f"    Template write date: {p.product_tmpl_id.write_date}")
            
            # Process in batches
            total_synced = 0
            total_errors = 0
            all_error_details = []
            
            for i in range(0, len(products), batch_size):
                batch = products[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = ((len(products) - 1) // batch_size) + 1
                
                _logger.info(f"🔄 Processing batch {batch_num}/{total_batches}: {len(batch)} variants")
                
                # Transform batch
                documents = []
                batch_errors = 0
                batch_error_details = []
                
                for product in batch:
                    try:
                        doc = self._transform_product_variant_to_meili_doc(product)
                        documents.append(doc)
                    except Exception as e:
                        batch_errors += 1
                        error_msg = f"Variant {product.id}: {str(e)}"
                        batch_error_details.append(error_msg)
                        _logger.error(f"❌ Transform failed: {error_msg}")
                
                # Upload batch to MeiliSearch
                if documents:
                    try:
                        upload_url = f"{client_info['endpoint']}/indexes/{config.products_index_name}/documents"
                        
                        # ✅ FIX 1: Use PUT for primary key upsert (avoid duplicates)
                        response = requests.put(
                            upload_url,
                            headers=client_info['headers_post'],
                            json=documents,
                            timeout=60
                        )
                        
                        if response.status_code in [200, 201, 202]:
                            batch_synced = len(documents)
                            total_synced += batch_synced
                            _logger.info(f"✅ Batch {batch_num}: uploaded {batch_synced} variants")
                        else:
                            error_msg = f"Batch {batch_num} upload failed: HTTP {response.status_code}"
                            try:
                                error_detail = response.json()
                                error_msg += f" - {error_detail}"
                            except:
                                error_msg += f" - {response.text}"
                            
                            batch_error_details.append(error_msg)
                            batch_errors += len(documents)
                            _logger.error(f"❌ {error_msg}")
                            
                    except Exception as e:
                        error_msg = f"Batch {batch_num} upload error: {str(e)}"
                        batch_error_details.append(error_msg)
                        batch_errors += len(documents)
                        _logger.error(f"❌ {error_msg}")
                
                total_errors += batch_errors
                all_error_details.extend(batch_error_details)
            
            # Update sync statistics
            if total_synced > 0:
                config.write({
                    'last_sync_date': datetime.now(),
                    'total_products_indexed': total_synced,
                    'connection_status': 'connected'
                })
            
            duration = (datetime.now() - start_time).total_seconds()
            
            result = {
                "synced": total_synced,
                "errors": total_errors,
                "duration": f"{duration:.1f}s",
                "error_details": all_error_details[:10],
                "last_sync_date": datetime.now().isoformat(),
                "total_products_found": len(products),
                "batch_size_used": batch_size,
                "batches_processed": ((len(products) - 1) // batch_size) + 1 if products else 0
            }
            
            _logger.info(f"🏁 Variant sync complete: {result}")
            return result
            
        except Exception as e:
            error_msg = f"Variant sync failed: {str(e)}"
            _logger.error(f"💥 {error_msg}")
            return {
                "synced": 0,
                "errors": 1,
                "duration": "0s",
                "error_details": [error_msg]
            }
    
    def _transform_product_variant_to_meili_doc(self, product_variant):
        """Transform Odoo product variant with JSONB to flat MeiliSearch document"""
        template = product_variant.product_tmpl_id
        
        # DEBUG: Log EVA Hotmelt products specifically
        if 'EVA Hotmelt' in (template.name or ''):
            _logger.info(f"🔍 DEBUG: Processing EVA Hotmelt variant {product_variant.id}, template {template.id}")
        
        # ✅ FIX 3: Extract descriptions from multiple sources
        desc_translations = self._extract_all_descriptions_from_template(template)
        
        # Build full variant names manually
        variant_full_names = self._build_full_variant_names(product_variant)
        
        # Get ALL PUBLIC CATEGORIES with full hierarchies
        all_categories_info = self._get_all_public_categories_with_hierarchies(template)
        
        # Extract brand from English variant name
        brand = self._extract_brand(variant_full_names.get('en_US', ''))
        
        # ✅ FIX 2: Use current datetime for sync tracking
        current_time = datetime.now()
        
        # Build MeiliSearch document for VARIANT
        doc = {
            "id": product_variant.id,  # VARIANT ID - PRIMARY KEY
            "template_id": template.id,
            "default_code": product_variant.default_code or template.default_code or "",
            "brand": brand,
            "price": float(product_variant.list_price) if product_variant.list_price else 0.0,
            "available": getattr(product_variant, 'qty_available', 0) > 0,
            
            # ✅ FIX 2: Use current sync time instead of product write_date
            "updated_date": current_time.isoformat(),
            "product_write_date": product_variant.write_date.isoformat() if product_variant.write_date else "",
            "template_write_date": template.write_date.isoformat() if template.write_date else "",
            
            "popularity_score": 50,
            
            # MANUALLY BUILT VARIANT NAMES (template + attributes)
            "name_en": variant_full_names.get('en_US', ''),
            "name_ro": variant_full_names.get('ro_RO', ''),
            "name_hu": variant_full_names.get('hu_HU', ''),
            
            # ✅ FIX 3: Enhanced descriptions
            "description_en": desc_translations.get('en_US', ''),
            "description_ro": desc_translations.get('ro_RO', ''),
            "description_hu": desc_translations.get('hu_HU', ''),
            
            # ALL PUBLIC CATEGORIES WITH FULL HIERARCHIES
            "categories_en": all_categories_info['categories_en'],
            "categories_ro": all_categories_info['categories_ro'],
            "categories_hu": all_categories_info['categories_hu'],
            "categories_combined_en": all_categories_info['combined_en'],
            "categories_combined_ro": all_categories_info['combined_ro'],
            "categories_combined_hu": all_categories_info['combined_hu'],
            "category_ids": all_categories_info['category_ids'],
            
            # Legacy single category fields
            "category_id": all_categories_info['category_ids'][0] if all_categories_info['category_ids'] else 0,
            "category_name_en": all_categories_info['categories_en'][0] if all_categories_info['categories_en'] else 'Uncategorized',
            "category_name_ro": all_categories_info['categories_ro'][0] if all_categories_info['categories_ro'] else 'Fără categorie',
            "category_name_hu": all_categories_info['categories_hu'][0] if all_categories_info['categories_hu'] else 'Kategória nélkül',
            
            # Variant specific info
            "is_variant": len(template.product_variant_ids) > 1,
            "variant_count": len(template.product_variant_ids),
        }
        
        _logger.info(f"✅ Transformed variant: {doc['id']} - {doc['name_en']} - Desc EN: {len(doc['description_en'])} chars")
        return doc
    
    def _extract_all_descriptions_from_template(self, template):
        """✅ FIX 3: Extract descriptions from multiple sources"""
        descriptions = {}
        
        try:
            # Try multiple description fields
            description_fields = [
                'description_sale',  # Sales description
                'description',       # Standard description
                'description_purchase', # Purchase description
                'website_description', # Website description
            ]
            
            for lang_code in ['en_US', 'ro_RO', 'hu_HU']:
                found_desc = ""
                
                # Try each field until we find content
                for field_name in description_fields:
                    if hasattr(template, field_name):
                        try:
                            template_translated = template.with_context(lang=lang_code)
                            field_value = getattr(template_translated, field_name, '')
                            
                            if isinstance(field_value, dict):
                                # JSONB field
                                desc = field_value.get(lang_code, '') or ''
                            else:
                                # Regular field
                                desc = str(field_value) if field_value else ''
                            
                            if desc and desc.strip():
                                found_desc = desc.strip()
                                _logger.info(f"📝 Found description in {field_name} for {lang_code}: {len(found_desc)} chars")
                                break
                                
                        except Exception as e:
                            _logger.warning(f"Failed to get {field_name} for {lang_code}: {str(e)}")
                            continue
                
                descriptions[lang_code] = found_desc
                
        except Exception as e:
            _logger.error(f"Description extraction failed: {str(e)}")
            for lang_code in ['en_US', 'ro_RO', 'hu_HU']:
                descriptions[lang_code] = ''
        
        return descriptions
    
    def _get_all_public_categories_with_hierarchies(self, template):
        """Get ALL public categories with their full recursive hierarchies"""
        categories_info = {
            'categories_en': [],
            'categories_ro': [],
            'categories_hu': [],
            'combined_en': '',
            'combined_ro': '',
            'combined_hu': '',
            'category_ids': []
        }
        
        try:
            # Get ALL public categories (many2many relation)
            if hasattr(template, 'public_categ_ids') and template.public_categ_ids:
                public_categories = template.public_categ_ids
                _logger.info(f"🏷️ Found {len(public_categories)} public categories for template {template.id}")
                
                # Process each category
                for category in public_categories:
                    categories_info['category_ids'].append(category.id)
                    
                    # Build full hierarchy for each language
                    for lang_code, lang_suffix in [('en_US', 'en'), ('ro_RO', 'ro'), ('hu_HU', 'hu')]:
                        try:
                            hierarchy_path = self._build_category_hierarchy_path(category, lang_code)
                            categories_info[f'categories_{lang_suffix}'].append(hierarchy_path)
                        except Exception as e:
                            _logger.warning(f"Failed to build hierarchy for category {category.id} in {lang_code}: {str(e)}")
                            try:
                                categ_translated = category.with_context(lang=lang_code)
                                fallback_name = categ_translated.name or f'Category {category.id}'
                                categories_info[f'categories_{lang_suffix}'].append(fallback_name)
                            except:
                                categories_info[f'categories_{lang_suffix}'].append(f'Category {category.id}')
                
                # Create combined searchable fields (all categories joined)
                categories_info['combined_en'] = " | ".join(categories_info['categories_en'])
                categories_info['combined_ro'] = " | ".join(categories_info['categories_ro'])
                categories_info['combined_hu'] = " | ".join(categories_info['categories_hu'])
                
            elif template.categ_id:
                # Fallback to internal category
                categories_info['category_ids'] = [template.categ_id.id]
                
                for lang_code, lang_suffix in [('en_US', 'en'), ('ro_RO', 'ro'), ('hu_HU', 'hu')]:
                    try:
                        categ_translated = template.categ_id.with_context(lang=lang_code)
                        category_name = categ_translated.name or f'Internal Category {template.categ_id.id}'
                        categories_info[f'categories_{lang_suffix}'] = [category_name]
                        categories_info[f'combined_{lang_suffix}'] = category_name
                    except:
                        categories_info[f'categories_{lang_suffix}'] = [f'Internal Category {template.categ_id.id}']
                        categories_info[f'combined_{lang_suffix}'] = f'Internal Category {template.categ_id.id}'
            else:
                # Use default uncategorized values
                categories_info['categories_en'] = ['Uncategorized']
                categories_info['categories_ro'] = ['Fără categorie']
                categories_info['categories_hu'] = ['Kategória nélkül']
                categories_info['combined_en'] = 'Uncategorized'
                categories_info['combined_ro'] = 'Fără categorie'
                categories_info['combined_hu'] = 'Kategória nélkül'
                categories_info['category_ids'] = [0]
                
        except Exception as e:
            _logger.warning(f"Multiple categories extraction failed: {str(e)}")
            # Fallback to uncategorized
            categories_info['categories_en'] = ['Uncategorized']
            categories_info['categories_ro'] = ['Fără categorie']
            categories_info['categories_hu'] = ['Kategória nélkül']
            categories_info['combined_en'] = 'Uncategorized'
            categories_info['combined_ro'] = 'Fără categorie'
            categories_info['combined_hu'] = 'Kategória nélkül'
            categories_info['category_ids'] = [0]
        
        return categories_info
    
    def _build_category_hierarchy_path(self, category, lang_code):
        """BUILD RECURSIVE HIERARCHY: Parent / Child / GrandChild"""
        try:
            category_localized = category.with_context(lang=lang_code)
            hierarchy_parts = []
            current_category = category_localized
            max_depth = 10
            depth = 0
            
            while current_category and depth < max_depth:
                hierarchy_parts.append(current_category.name or 'Unknown Category')
                current_category = current_category.parent_id
                if current_category:
                    current_category = current_category.with_context(lang=lang_code)
                depth += 1
            
            hierarchy_parts.reverse()
            full_path = " / ".join(hierarchy_parts)
            return full_path
            
        except Exception as e:
            _logger.error(f"Failed to build category hierarchy path: {str(e)}")
            try:
                category_localized = category.with_context(lang=lang_code)
                return category_localized.name or 'Unknown Category'
            except:
                return 'Unknown Category'
    
    def _build_full_variant_names(self, product_variant):
        """MANUALLY BUILD: Template name + (Attribute: Value, Attribute: Value)"""
        variant_names = {}
        
        try:
            template = product_variant.product_tmpl_id
            template_name_translations = self._extract_translations_from_template(template, 'name')
            attribute_values = product_variant.product_template_attribute_value_ids
            
            for lang_code, lang_suffix in [('en_US', 'en'), ('ro_RO', 'ro'), ('hu_HU', 'hu')]:
                try:
                    template_name = template_name_translations.get(lang_code, '') or str(template.name or '')
                    
                    if not attribute_values:
                        variant_names[lang_code] = template_name
                    else:
                        attr_parts = []
                        for attr_val in attribute_values:
                            try:
                                attr_val_localized = attr_val.with_context(lang=lang_code)
                                attr_name = attr_val_localized.attribute_id.name or 'Unknown Attr'
                                attr_value = attr_val_localized.name or 'Unknown Value'
                                attr_parts.append(f"{attr_name}: {attr_value}")
                            except Exception as e:
                                attr_name = attr_val.attribute_id.name or 'Unknown Attr'
                                attr_value = attr_val.name or 'Unknown Value'
                                attr_parts.append(f"{attr_name}: {attr_value}")
                        
                        if attr_parts:
                            attributes_string = ", ".join(attr_parts)
                            full_name = f"{template_name} ({attributes_string})"
                        else:
                            full_name = template_name
                        
                        variant_names[lang_code] = full_name
                        
                except Exception as e:
                    template_name = template_name_translations.get(lang_code, '') or str(template.name or '')
                    variant_names[lang_code] = template_name
        
        except Exception as e:
            template = product_variant.product_tmpl_id
            for lang_code in ['en_US', 'ro_RO', 'hu_HU']:
                variant_names[lang_code] = str(template.name or '')
        
        return variant_names
    
    def _extract_translations_from_template(self, template, field_name):
        """Extract translations from template JSONB field or use context-based translation"""
        translations = {}
        
        try:
            field_value = getattr(template, field_name, '')
            
            if isinstance(field_value, dict):
                translations = field_value
            else:
                for lang in ['en_US', 'ro_RO', 'hu_HU']:
                    try:
                        template_translated = template.with_context(lang=lang)
                        translations[lang] = getattr(template_translated, field_name, '') or ''
                    except Exception as e:
                        translations[lang] = str(field_value) if field_value else ''
        except Exception as e:
            for lang in ['en_US', 'ro_RO', 'hu_HU']:
                translations[lang] = str(getattr(template, field_name, '') or '')
        
        return translations
    
    def _extract_brand(self, product_name):
        """Extract brand name from product name"""
        if not product_name:
            return ""
        
        brands = ['ZowoHome', 'Dulux', 'Caparol', 'Sadolin', 'Kober', 'Benjamin Moore', 'KLEIBERIT']
        
        product_name_upper = product_name.upper()
        for brand in brands:
            if brand.upper() in product_name_upper:
                return brand
        
        words = product_name.split()
        if words and words[0][0].isupper() and len(words[0]) > 2:
            return words[0]
        
        return ""


# 🚀 NEW ENHANCED SEARCH TOOLS - NO BREAKING CHANGES

@register_tool
class MeiliProductSearchTool(AgenticAIToolBase):
    code = "meili_product_search"
    name = "Enhanced MeiliSearch Product Search"
    description = "Advanced product search using MeiliSearch with typo tolerance, intelligent ranking, and multilingual support"
    category = "meilisearch"
    parameters = {
        "query": {
            "type": "string",
            "required": True,
            "description": "Search term for product name, brand, SKU, or description"
        },
        "lang": {
            "type": "string",
            "required": False,
            "description": "Language code (en_US, ro_RO, hu_HU). Auto-detected if not provided."
        },
        "category_filter": {
            "type": "string",
            "required": False,
            "description": "Filter by category name or partial category path"
        },
        "brand_filter": {
            "type": "string",
            "required": False,
            "description": "Filter by specific brand (e.g., 'ZowoHome', 'KLEIBERIT')"
        },
        "available_only": {
            "type": "boolean",
            "required": False,
            "description": "Only show products in stock (default: false)"
        },
        "limit": {
            "type": "integer",
            "required": False,
            "description": "Maximum number of results (default: 10, max: 50)"
        },
        "price_range": {
            "type": "string",
            "required": False,
            "description": "Price range filter, e.g., '10-100' for products between 10 and 100 RON"
        }
    }
    keywords = [
        "product", "produs", "termék", "search", "find", "cauta", "gaseste", "keres", 
        "aveti", "have", "van", "show", "arata", "lac", "vopsea", "paint", "festék",
        "zowohome", "kleiberit", "dulux", "caparol", "parchet", "parquet", "mat", "matt"
    ]
    examples = [
        {
            "input": {"query": "zowohome mat", "lang": "ro_RO", "limit": 5},
            "output": {
                "products": [
                    {
                        "id": 12345,
                        "name": "ZowoHome 8400 - lac interior si parchet - mat",
                        "price": 45.0,
                        "available": True,
                        "brand": "ZowoHome",
                        "ranking_score": 0.987
                    }
                ],
                "total_found": 3,
                "search_quality": "enhanced_meilisearch"
            },
            "description": "Enhanced search with typo tolerance and intelligent ranking"
        }
    ]
    output_format = {
        "products": [
            {
                "id": "int - Product variant ID",
                "name": "string - Product name in requested language",
                "default_code": "string - SKU/Reference",
                "price": "float - Price in RON",
                "currency": "string - Currency code",
                "available": "boolean - In stock status",
                "brand": "string - Extracted brand name",
                "category": "string - Primary category in requested language",
                "description": "string - Product description", 
                "ranking_score": "float - MeiliSearch relevance score",
                "language": "string - Language of returned data"
            }
        ],
        "total_found": "int - Total number of matching products",
        "search_time_ms": "int - Search execution time in milliseconds",
        "search_quality": "string - 'enhanced_meilisearch' indicates advanced search",
        "language_used": "string - Language code used for search",
        "query_analyzed": "string - How the query was interpreted"
    }
    
    def call(self, **kwargs):
        validated = self.validate_parameters(**kwargs)
        query = validated["query"]
        lang = self._validate_language(validated.get("lang", "en_US"))
        limit = min(validated.get("limit", 10), 50)  # Max 50 results
        category_filter = validated.get("category_filter")
        brand_filter = validated.get("brand_filter")
        available_only = validated.get("available_only", False)
        price_range = validated.get("price_range")
        
        start_time = datetime.now()
        _logger.info(f"🔍 Enhanced MeiliSearch: '{query}' in {lang}, limit={limit}")
        
        try:
            # Get MeiliSearch configuration
            config = self.env['meilisearch.config'].get_active_config()
            client_info = config.get_meilisearch_client()
            
            # Build search parameters
            search_params = {
                "q": query,
                "limit": limit,
                "attributesToRetrieve": ["*"],
                "showRankingScore": True,
            }
            
            # Build language-specific search strategy
            lang_suffix = self._get_language_suffix(lang)
            
            # Enhanced search attributes based on language
            search_attributes = [
                f"name_{lang_suffix}^3",      # Boost name in target language
                f"description_{lang_suffix}^2", # Boost description in target language  
                "default_code^4",             # Boost SKU/code (highest priority)
                "brand^3",                    # Boost brand
                f"categories_combined_{lang_suffix}^2", # Boost categories in target language
            ]
            
            # Add other languages with lower priority for multilingual matching
            other_languages = ['en', 'ro', 'hu']
            other_languages.remove(lang_suffix)
            for other_lang in other_languages:
                search_attributes.extend([
                    f"name_{other_lang}^1",
                    f"description_{other_lang}^0.8",
                    f"categories_combined_{other_lang}^1"
                ])
            
            search_params["attributesToSearchOn"] = search_attributes
            
            # Build filters
            filters = []
            
            if available_only:
                filters.append("available = true")
            
            if brand_filter:
                filters.append(f"brand = '{brand_filter}'")
            
            if price_range:
                try:
                    min_price, max_price = map(float, price_range.split('-'))
                    filters.append(f"price >= {min_price} AND price <= {max_price}")
                except:
                    _logger.warning(f"Invalid price range format: {price_range}")
            
            if category_filter:
                # Search in category fields for the filter term
                category_filters = [
                    f"categories_combined_en CONTAINS '{category_filter}'",
                    f"categories_combined_ro CONTAINS '{category_filter}'", 
                    f"categories_combined_hu CONTAINS '{category_filter}'"
                ]
                filters.append(f"({' OR '.join(category_filters)})")
            
            if filters:
                search_params["filter"] = " AND ".join(filters)
            
            # Execute search
            search_url = f"{client_info['endpoint']}/indexes/{config.products_index_name}/search"
            
            response = requests.post(
                search_url,
                headers=client_info['headers_post'],
                json=search_params,
                timeout=15
            )
            
            search_time = (datetime.now() - start_time).total_seconds() * 1000
            
            if response.status_code != 200:
                _logger.error(f"MeiliSearch error: HTTP {response.status_code} - {response.text}")
                return {
                    "products": [],
                    "total_found": 0,
                    "error": f"Search failed: HTTP {response.status_code}",
                    "search_quality": "enhanced_meilisearch",
                    "language_used": lang
                }
            
            search_result = response.json()
            hits = search_result.get('hits', [])
            
            _logger.info(f"🎯 Enhanced search found {len(hits)} results in {search_time:.1f}ms")
            
            # Transform results
            products = []
            for hit in hits:
                try:
                    # Get localized name based on language
                    name = hit.get(f'name_{lang_suffix}', '') or hit.get('name_en', '') or 'Unknown Product'
                    description = hit.get(f'description_{lang_suffix}', '') or hit.get('description_en', '') or ''
                    category = hit.get(f'category_name_{lang_suffix}', '') or hit.get('category_name_en', '') or 'Uncategorized'
                    
                    product_data = {
                        "id": hit.get('id', 0),
                        "name": name,
                        "default_code": hit.get('default_code', ''),
                        "price": float(hit.get('price', 0.0)),
                        "currency": "RON",
                        "available": bool(hit.get('available', False)),
                        "brand": hit.get('brand', ''),
                        "category": category,
                        "description": description[:200] + "..." if len(description) > 200 else description,
                        "ranking_score": hit.get('_rankingScore', 0.0),
                        "language": lang
                    }
                    products.append(product_data)
                    
                except Exception as e:
                    _logger.error(f"Error processing search result: {str(e)}")
                    continue
            
            return {
                "products": products,
                "total_found": len(products),
                "search_time_ms": int(search_time),
                "search_quality": "enhanced_meilisearch",
                "language_used": lang,
                "query_analyzed": f"Enhanced search for '{query}' with typo tolerance and intelligent ranking",
                "filters_applied": len(filters),
                "multilingual_search": True
            }
            
        except Exception as e:
            error_msg = f"Enhanced search failed: {str(e)}"
            _logger.error(f"❌ {error_msg}")
            return {
                "products": [],
                "total_found": 0,
                "error": error_msg,
                "search_quality": "enhanced_meilisearch",
                "language_used": lang
            }
    
    def _get_language_suffix(self, lang_code):
        """Get language suffix for MeiliSearch fields"""
        lang_mapping = {
            'en_US': 'en',
            'ro_RO': 'ro', 
            'hu_HU': 'hu'
        }
        return lang_mapping.get(lang_code, 'en')


@register_tool
class MeiliProductCategoryTool(AgenticAIToolBase):
    code = "meili_product_category"
    name = "Enhanced MeiliSearch Category Search"
    description = "Search and browse product categories using public ecommerce categories with multilingual support and MeiliSearch intelligence"
    category = "meilisearch"
    parameters = {
        "action": {
            "type": "string",
            "required": False,
            "enum": ["search_categories", "browse_by_category", "get_category_hierarchy", "find_products_in_category"],
            "description": "Action to perform (default: search_categories)"
        },
        "search_term": {
            "type": "string",
            "required": False,
            "description": "Search term for category names (e.g., 'adhesives', 'adezivi', 'ragasztók')"
        },
        "category_name": {
            "type": "string",
            "required": False,
            "description": "Specific category name to browse products"
        },
        "lang": {
            "type": "string",
            "required": False,
            "description": "Language code (en_US, ro_RO, hu_HU). Auto-detected if not provided."
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
    keywords = [
        "category", "categories", "categorie", "categorii", "kategória", "kategóriák",
        "browse", "section", "department", "tip", "type", "classification", 
        "adhesives", "adezivi", "ragasztók", "paint", "vopsea", "festék",
        "interior", "exterior", "parchet", "parquet", "carpenter", "tâmplar"
    ]
    examples = [
        {
            "input": {"action": "search_categories", "search_term": "adhesives", "lang": "en_US"},
            "output": {
                "categories": [
                    {
                        "name": "KLEIBERIT - Adhesives / Products Type / Hot melt Adhesives",
                        "product_count": 15,
                        "hierarchy_path": "KLEIBERIT - Adhesives / Products Type / Hot melt Adhesives"
                    }
                ],
                "search_quality": "enhanced_meilisearch"
            },
            "description": "Search categories using MeiliSearch intelligence"
        }
    ]
    output_format = {
        "categories": [
            {
                "name": "string - Category name/path in requested language",
                "product_count": "int - Number of products in this category",
                "hierarchy_path": "string - Full category hierarchy path",
                "language": "string - Language of returned data"
            }
        ],
        "products": [
            {
                "id": "int - Product ID (when action=find_products_in_category)",
                "name": "string - Product name",
                "category_match": "string - Matching category path"
            }
        ],
        "total_found": "int - Total results found",
        "search_quality": "string - 'enhanced_meilisearch' for intelligent search",
        "action_performed": "string - Action that was executed",
        "language_used": "string - Language used for results"
    }
    
    def call(self, **kwargs):
        validated = self.validate_parameters(**kwargs)
        action = validated.get("action", "search_categories")
        search_term = validated.get("search_term", "")
        category_name = validated.get("category_name", "")
        lang = self._validate_language(validated.get("lang", "en_US"))
        limit = validated.get("limit", 20)
        include_product_count = validated.get("include_product_count", True)
        
        _logger.info(f"🏷️ Enhanced category search: action={action}, term='{search_term}', lang={lang}")
        
        try:
            # Get MeiliSearch configuration
            config = self.env['meilisearch.config'].get_active_config()
            client_info = config.get_meilisearch_client()
            lang_suffix = self._get_language_suffix(lang)
            
            if action == "search_categories":
                return self._search_categories_in_meilisearch(
                    client_info, config, search_term, lang, lang_suffix, limit, include_product_count
                )
            elif action == "browse_by_category":
                return self._browse_by_category(
                    client_info, config, category_name, lang, lang_suffix, limit
                )
            elif action == "find_products_in_category":
                return self._find_products_in_category(
                    client_info, config, category_name, lang, lang_suffix, limit
                )
            elif action == "get_category_hierarchy":
                return self._get_category_hierarchy(
                    client_info, config, lang, lang_suffix, limit
                )
            else:
                return {
                    "categories": [],
                    "total_found": 0,
                    "error": f"Unknown action: {action}",
                    "search_quality": "enhanced_meilisearch"
                }
                
        except Exception as e:
            error_msg = f"Enhanced category search failed: {str(e)}"
            _logger.error(f"❌ {error_msg}")
            return {
                "categories": [],
                "total_found": 0,
                "error": error_msg,
                "search_quality": "enhanced_meilisearch",
                "language_used": lang
            }
    
    def _search_categories_in_meilisearch(self, client_info, config, search_term, lang, lang_suffix, limit, include_product_count):
        """Search for categories using MeiliSearch category fields"""
        if not search_term:
            search_term = "*"  # Return all categories if no term
        
        # Search specifically in category fields
        search_params = {
            "q": search_term,
            "limit": limit * 5,  # Get more results to deduplicate categories
            "attributesToSearchOn": [
                f"categories_combined_{lang_suffix}^3",  # Primary language
                f"categories_combined_en^2",             # English fallback
                f"categories_combined_ro^1",             # Romanian fallback
                f"categories_combined_hu^1"              # Hungarian fallback
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
            timeout=15
        )
        
        if response.status_code != 200:
            raise Exception(f"MeiliSearch error: HTTP {response.status_code}")
        
        search_result = response.json()
        hits = search_result.get('hits', [])
        
        # Extract unique categories
        unique_categories = {}
        
        for hit in hits:
            categories_list = hit.get(f'categories_{lang_suffix}', [])
            if not categories_list:
                categories_list = hit.get('categories_en', [])  # Fallback
            
            for category_path in categories_list:
                if category_path and category_path not in unique_categories:
                    unique_categories[category_path] = {
                        "name": category_path,
                        "hierarchy_path": category_path,
                        "product_count": 0,
                        "language": lang
                    }
        
        # Count products per category if requested
        if include_product_count:
            for category_path in unique_categories.keys():
                count = self._count_products_in_category(client_info, config, category_path, lang_suffix)
                unique_categories[category_path]["product_count"] = count
        
        # Convert to list and limit results
        categories_list = list(unique_categories.values())[:limit]
        
        return {
            "categories": categories_list,
            "total_found": len(categories_list),
            "search_quality": "enhanced_meilisearch",
            "action_performed": "search_categories",
            "language_used": lang,
            "search_term": search_term
        }
    
    def _find_products_in_category(self, client_info, config, category_name, lang, lang_suffix, limit):
        """Find products that belong to a specific category"""
        if not category_name:
            raise ValueError("category_name is required for find_products_in_category action")
        
        search_params = {
            "q": "",  # Empty query to get all products
            "limit": limit,
            "filter": f"categories_combined_{lang_suffix} CONTAINS '{category_name}' OR categories_combined_en CONTAINS '{category_name}'",
            "attributesToRetrieve": [
                "id", f"name_{lang_suffix}", "name_en", "default_code", "price",
                f"categories_combined_{lang_suffix}", "brand", "available"
            ]
        }
        
        response = requests.post(
            f"{client_info['endpoint']}/indexes/{config.products_index_name}/search",
            headers=client_info['headers_post'],
            json=search_params,
            timeout=15
        )
        
        if response.status_code != 200:
            raise Exception(f"MeiliSearch error: HTTP {response.status_code}")
        
        search_result = response.json()
        hits = search_result.get('hits', [])
        
        products = []
        for hit in hits:
            name = hit.get(f'name_{lang_suffix}', '') or hit.get('name_en', '') or 'Unknown Product'
            category_match = hit.get(f'categories_combined_{lang_suffix}', '') or hit.get('categories_combined_en', '')
            
            products.append({
                "id": hit.get('id', 0),
                "name": name,
                "default_code": hit.get('default_code', ''),
                "price": hit.get('price', 0.0),
                "brand": hit.get('brand', ''),
                "available": hit.get('available', False),
                "category_match": category_match,
                "language": lang
            })
        
        return {
            "products": products,
            "total_found": len(products),
            "search_quality": "enhanced_meilisearch",
            "action_performed": "find_products_in_category",
            "language_used": lang,
            "category_searched": category_name
        }
    
    def _browse_by_category(self, client_info, config, category_name, lang, lang_suffix, limit):
        """Browse products by category with enhanced filtering"""
        return self._find_products_in_category(client_info, config, category_name, lang, lang_suffix, limit)
    
    def _get_category_hierarchy(self, client_info, config, lang, lang_suffix, limit):
        """Get hierarchical view of all categories"""
        # Get a sample of products to extract category hierarchies
        search_params = {
            "q": "",
            "limit": limit * 2,
            "attributesToRetrieve": [f"categories_{lang_suffix}", "categories_en"]
        }
        
        response = requests.post(
            f"{client_info['endpoint']}/indexes/{config.products_index_name}/search",
            headers=client_info['headers_post'],
            json=search_params,
            timeout=15
        )
        
        if response.status_code != 200:
            raise Exception(f"MeiliSearch error: HTTP {response.status_code}")
        
        search_result = response.json()
        hits = search_result.get('hits', [])
        
        # Build hierarchy
        hierarchy = {}
        
        for hit in hits:
            categories_list = hit.get(f'categories_{lang_suffix}', [])
            if not categories_list:
                categories_list = hit.get('categories_en', [])  # Fallback
            
            for category_path in categories_list:
                if category_path:
                    # Split hierarchy path and build tree
                    parts = [part.strip() for part in category_path.split('/')]
                    current_level = hierarchy
                    
                    for part in parts:
                        if part not in current_level:
                            current_level[part] = {}
                        current_level = current_level[part]
        
        # Convert hierarchy to list format
        def flatten_hierarchy(node, prefix="", result_list=[]):
            for key, value in node.items():
                full_path = f"{prefix}{key}".strip()
                result_list.append({
                    "name": full_path,
                    "hierarchy_path": full_path,
                    "product_count": 0,  # Could be calculated if needed
                    "language": lang
                })
                if value:  # Has children
                    flatten_hierarchy(value, f"{full_path} / ", result_list)
            return result_list
        
        categories_list = flatten_hierarchy(hierarchy)[:limit]
        
        return {
            "categories": categories_list,
            "total_found": len(categories_list),
            "search_quality": "enhanced_meilisearch",
            "action_performed": "get_category_hierarchy",
            "language_used": lang
        }
    
    def _count_products_in_category(self, client_info, config, category_path, lang_suffix):
        """Count products in a specific category"""
        try:
            search_params = {
                "q": "",
                "limit": 1,
                "filter": f"categories_combined_{lang_suffix} CONTAINS '{category_path}' OR categories_combined_en CONTAINS '{category_path}'",
                "attributesToRetrieve": ["id"]
            }
            
            response = requests.post(
                f"{client_info['endpoint']}/indexes/{config.products_index_name}/search",
                headers=client_info['headers_post'],
                json=search_params,
                timeout=10
            )
            
            if response.status_code == 200:
                search_result = response.json()
                return search_result.get('estimatedTotalHits', 0)
            
        except:
            pass
        
        return 0
    
    def _get_language_suffix(self, lang_code):
        """Get language suffix for MeiliSearch fields"""
        lang_mapping = {
            'en_US': 'en',
            'ro_RO': 'ro',
            'hu_HU': 'hu'
        }
        return lang_mapping.get(lang_code, 'en')

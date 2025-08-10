from odoo import models, fields, api
import requests
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

class MeiliSearchProductBrowse(models.TransientModel):
    _name = 'meilisearch.product.browse'
    _description = 'Browse MeiliSearch Indexed Product Variants'
    _rec_name = 'name_en'

    # Product variant data from MeiliSearch
    meili_id = fields.Integer("Variant ID", readonly=True)
    template_id = fields.Integer("Template ID", readonly=True)
    name_en = fields.Char("Full Name (English)", readonly=True)
    name_ro = fields.Char("Full Name (Romanian)", readonly=True)
    name_hu = fields.Char("Full Name (Hungarian)", readonly=True)
    description_en = fields.Text("Description (EN)", readonly=True)
    description_ro = fields.Text("Description (RO)", readonly=True)
    description_hu = fields.Text("Description (HU)", readonly=True)
    default_code = fields.Char("SKU/Reference", readonly=True)
    brand = fields.Char("Brand", readonly=True)
    price = fields.Float("Price", readonly=True)
    available = fields.Boolean("Available", readonly=True)
    
    # ✅ NEW: Multiple categories fields
    categories_combined_en = fields.Text("All Categories (EN)", readonly=True)
    categories_combined_ro = fields.Text("All Categories (RO)", readonly=True)
    categories_combined_hu = fields.Text("All Categories (HU)", readonly=True)
    
    # Legacy single category fields (for compatibility)
    category_name_en = fields.Char("First Category (EN)", readonly=True)
    category_name_ro = fields.Char("First Category (RO)", readonly=True)
    category_name_hu = fields.Char("First Category (HU)", readonly=True)
    
    is_variant = fields.Boolean("Is Variant", readonly=True)
    variant_count = fields.Integer("Variant Count", readonly=True)
    updated_date = fields.Datetime("Updated Date", readonly=True)

    def _parse_iso_datetime(self, iso_string):
        """Parse ISO datetime string to Odoo datetime"""
        if not iso_string:
            return False
        
        try:
            if 'T' in iso_string:
                if '.' in iso_string:
                    iso_string = iso_string.split('.')[0]
                dt = datetime.strptime(iso_string, '%Y-%m-%dT%H:%M:%S')
                return dt
            else:
                dt = datetime.strptime(iso_string, '%Y-%m-%d %H:%M:%S')
                return dt
        except Exception as e:
            _logger.warning(f"Failed to parse datetime '{iso_string}': {str(e)}")
            return False

    @api.model
    def load_from_meilisearch(self, limit=1500):
        """Load product variants from MeiliSearch and create transient records"""
        try:
            # Clear existing records
            self.search([]).unlink()
            
            # Get MeiliSearch config
            config = self.env['meilisearch.config'].get_active_config()
            client_info = config.get_meilisearch_client()
            
            _logger.info(f"🔍 Loading {limit} product variants from: {client_info['endpoint']}/indexes/{config.products_index_name}/documents")
            
            # Fetch product variants from MeiliSearch
            url = f"{client_info['endpoint']}/indexes/{config.products_index_name}/documents?limit={limit}"
            
            response = requests.get(
                url,
                headers=client_info['headers'],
                timeout=30
            )
            
            _logger.info(f"📡 Response status: {response.status_code}")
            
            if response.status_code == 200:
                response_data = response.json()
                products_data = response_data.get('results', [])
                
                _logger.info(f"📦 Product variants found: {len(products_data)}")
                
                if not products_data:
                    _logger.warning("❌ No product variants in response results")
                    return 0
                
                records_created = 0
                for product_data in products_data:
                    try:
                        _logger.info(f"🔄 Processing variant: {product_data.get('id')} - {product_data.get('name_en', 'No name')}")
                        
                        # Create transient record with ALL category fields
                        record_data = {
                            'meili_id': product_data.get('id', 0),
                            'template_id': product_data.get('template_id', 0),
                            'name_en': product_data.get('name_en', '') or '',
                            'name_ro': product_data.get('name_ro', '') or '',
                            'name_hu': product_data.get('name_hu', '') or '',
                            'description_en': product_data.get('description_en', '') or '',
                            'description_ro': product_data.get('description_ro', '') or '',
                            'description_hu': product_data.get('description_hu', '') or '',
                            'default_code': product_data.get('default_code', '') or '',
                            'brand': product_data.get('brand', '') or '',
                            'price': float(product_data.get('price', 0.0) or 0.0),
                            'available': bool(product_data.get('available', False)),
                            
                            # ✅ NEW: Multiple categories
                            'categories_combined_en': product_data.get('categories_combined_en', '') or '',
                            'categories_combined_ro': product_data.get('categories_combined_ro', '') or '',
                            'categories_combined_hu': product_data.get('categories_combined_hu', '') or '',
                            
                            # Legacy single categories
                            'category_name_en': product_data.get('category_name_en', '') or '',
                            'category_name_ro': product_data.get('category_name_ro', '') or '',
                            'category_name_hu': product_data.get('category_name_hu', '') or '',
                            
                            'is_variant': bool(product_data.get('is_variant', False)),
                            'variant_count': int(product_data.get('variant_count', 1)),
                        }
                        
                        # Handle datetime field properly
                        updated_date_str = product_data.get('updated_date')
                        if updated_date_str:
                            parsed_datetime = self._parse_iso_datetime(updated_date_str)
                            if parsed_datetime:
                                record_data['updated_date'] = parsed_datetime
                        
                        browse_record = self.create(record_data)
                        records_created += 1
                        
                        if records_created % 100 == 0:
                            _logger.info(f"📊 Progress: {records_created} variants loaded...")
                        
                    except Exception as e:
                        _logger.error(f"❌ Failed to create record for variant {product_data.get('id', 'unknown')}: {str(e)}")
                        continue
                
                _logger.info(f"✅ Successfully loaded {records_created} product variants from MeiliSearch")
                return records_created
                
            else:
                error_text = response.text if response.text else "No response body"
                _logger.error(f"❌ Failed to load from MeiliSearch: HTTP {response.status_code}")
                _logger.error(f"❌ Response body: {error_text}")
                return 0
                
        except requests.exceptions.RequestException as e:
            _logger.error(f"❌ Network error loading from MeiliSearch: {str(e)}")
            return 0
        except Exception as e:
            _logger.error(f"❌ Error loading from MeiliSearch: {str(e)}")
            import traceback
            _logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return 0

    @api.model
    def search_in_meilisearch(self, query="", limit=20):
        """Search product variants in MeiliSearch and load results"""
        try:
            # Clear existing records
            self.search([]).unlink()
            
            # Get MeiliSearch config
            config = self.env['meilisearch.config'].get_active_config()
            client_info = config.get_meilisearch_client()
            
            _logger.info(f"🔍 Searching for: '{query}' in MeiliSearch variants")
            
            # Search in MeiliSearch
            search_params = {
                "q": query,
                "limit": limit,
                "attributesToRetrieve": ["*"],
            }
            
            response = requests.post(
                f"{client_info['endpoint']}/indexes/{config.products_index_name}/search",
                headers=client_info['headers_post'],
                json=search_params,
                timeout=15
            )
            
            _logger.info(f"🔍 Search response status: {response.status_code}")
            
            if response.status_code == 200:
                search_result = response.json()
                hits = search_result.get('hits', [])
                
                _logger.info(f"🎯 Search found {len(hits)} variant results")
                
                records_created = 0
                for hit in hits:
                    try:
                        # Create transient record with ranking score in name
                        score = hit.get('_rankingScore', 0)
                        record_data = {
                            'meili_id': hit.get('id', 0),
                            'template_id': hit.get('template_id', 0),
                            'name_en': f"[Score: {score:.3f}] {hit.get('name_en', '')}",
                            'name_ro': hit.get('name_ro', '') or '',
                            'name_hu': hit.get('name_hu', '') or '',
                            'description_en': hit.get('description_en', '') or '',
                            'description_ro': hit.get('description_ro', '') or '',
                            'description_hu': hit.get('description_hu', '') or '',
                            'default_code': hit.get('default_code', '') or '',
                            'brand': hit.get('brand', '') or '',
                            'price': float(hit.get('price', 0.0) or 0.0),
                            'available': bool(hit.get('available', False)),
                            
                            # Multiple categories
                            'categories_combined_en': hit.get('categories_combined_en', '') or '',
                            'categories_combined_ro': hit.get('categories_combined_ro', '') or '',
                            'categories_combined_hu': hit.get('categories_combined_hu', '') or '',
                            
                            # Legacy single categories
                            'category_name_en': hit.get('category_name_en', '') or '',
                            'category_name_ro': hit.get('category_name_ro', '') or '',
                            'category_name_hu': hit.get('category_name_hu', '') or '',
                            
                            'is_variant': bool(hit.get('is_variant', False)),
                            'variant_count': int(hit.get('variant_count', 1)),
                        }
                        
                        # Handle datetime properly
                        updated_date_str = hit.get('updated_date')
                        if updated_date_str:
                            parsed_datetime = self._parse_iso_datetime(updated_date_str)
                            if parsed_datetime:
                                record_data['updated_date'] = parsed_datetime
                        
                        self.create(record_data)
                        records_created += 1
                        
                    except Exception as e:
                        _logger.error(f"❌ Failed to create search result record: {str(e)}")
                        continue
                
                _logger.info(f"✅ Search '{query}' created {records_created} browse records")
                return records_created
                
            else:
                _logger.error(f"❌ Search failed: HTTP {response.status_code} - {response.text}")
                return 0
                
        except Exception as e:
            _logger.error(f"❌ Search error: {str(e)}")
            return 0

from odoo import models, fields, api
from odoo.exceptions import UserError
import requests
import json
import logging

_logger = logging.getLogger(__name__)

class MeiliSearchConfig(models.Model):
    _name = 'meilisearch.config'
    _description = 'MeiliSearch Configuration'
    _rec_name = 'name'

    name = fields.Char("Configuration Name", required=True, default="Default MeiliSearch")
    endpoint_url = fields.Char("MeiliSearch Endpoint", required=True, default="http://localhost:7700")
    api_key = fields.Char("Master Key", help="MeiliSearch master key for authentication")
    is_active = fields.Boolean("Active", default=True)
    
    # Index settings
    products_index_name = fields.Char("Products Index Name", default="products", required=True)
    categories_index_name = fields.Char("Categories Index Name", default="categories", required=True)
    
    # Sync settings
    batch_size = fields.Integer("Sync Batch Size", default=100)
    auto_sync_enabled = fields.Boolean("Auto Sync on Product Changes", default=True)
    
    # Status
    last_sync_date = fields.Datetime("Last Sync Date", readonly=True)
    total_products_indexed = fields.Integer("Total Products Indexed", readonly=True)
    connection_status = fields.Selection([
        ('disconnected', 'Disconnected'),
        ('connected', 'Connected'),
        ('error', 'Error')
    ], string="Connection Status", default='disconnected', readonly=True)
    
    @api.model
    def get_active_config(self):
        """Get the active MeiliSearch configuration"""
        config = self.search([('is_active', '=', True)], limit=1)
        if not config:
            raise Exception("No active MeiliSearch configuration found. Please create one.")
        return config
    
    def test_connection(self):
        """Test connection to MeiliSearch with UI notification"""
        self.ensure_one()
        try:
            headers = {}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            response = requests.get(
                f"{self.endpoint_url}/health",
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                self.connection_status = 'connected'
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Connection Test',
                        'message': '✅ MeiliSearch connection successful!',
                        'type': 'success',
                        'sticky': True,
                    }
                }
            else:
                self.connection_status = 'error'
                raise UserError(f'❌ MeiliSearch connection failed: HTTP {response.status_code}')
                
        except requests.exceptions.RequestException as e:
            self.connection_status = 'error'
            raise UserError(f'❌ MeiliSearch connection error: {str(e)}')
        except Exception as e:
            self.connection_status = 'error'
            raise UserError(f'❌ Connection test failed: {str(e)}')
    
    def get_meilisearch_client(self):
        """Get configured MeiliSearch client info"""
        headers = {}
        
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        
        return {
            'endpoint': self.endpoint_url,
            'api_key': self.api_key,
            'headers': headers,
            'headers_post': {**headers, 'Content-Type': 'application/json'}
        }
    
    def clear_meilisearch_index(self):
        """✅ NEW: Clear MeiliSearch index"""
        self.ensure_one()
        try:
            client_info = self.get_meilisearch_client()
            
            response = requests.delete(
                f"{client_info['endpoint']}/indexes/{self.products_index_name}/documents",
                headers=client_info['headers_post'],
                timeout=30
            )
            
            if response.status_code in [200, 201, 202, 204]:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Index Cleared',
                        'message': '🗑️ MeiliSearch index cleared successfully! No duplicates anymore.',
                        'type': 'success',
                        'sticky': True,
                    }
                }
            else:
                raise UserError(f'❌ Clear index failed: HTTP {response.status_code}')
                
        except Exception as e:
            raise UserError(f'❌ Clear index failed: {str(e)}')
    
    def browse_indexed_products(self):
        """Open proper browse view with working form view"""
        self.ensure_one()
        
        # Load products from MeiliSearch into browse model
        browse_model = self.env['meilisearch.product.browse']
        count = browse_model.load_from_meilisearch(limit=1500)
        
        if count > 0:
            return {
                'type': 'ir.actions.act_window',
                'name': f'MeiliSearch Product Variants ({count} loaded)',
                'res_model': 'meilisearch.product.browse',
                'view_mode': 'tree,form',
                'view_id': self.env.ref('agentic_ai_integration_with_livechat.view_meilisearch_product_browse_tree').id,
                'target': 'current',
                'context': {'create': False, 'edit': False, 'delete': False},
                'views': [
                    (self.env.ref('agentic_ai_integration_with_livechat.view_meilisearch_product_browse_tree').id, 'tree'),
                    (self.env.ref('agentic_ai_integration_with_livechat.view_meilisearch_product_browse_form').id, 'form')
                ]
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Browse Failed',
                    'message': '❌ Could not load product variants from MeiliSearch. Check server logs for details.',
                    'type': 'warning',
                    'sticky': True,
                }
            }
    
    def test_meilisearch_search(self):
        """Test MeiliSearch search and show results in browse view"""
        self.ensure_one()
        
        # Load search results for "zowohome" as example
        browse_model = self.env['meilisearch.product.browse']
        count = browse_model.search_in_meilisearch("zowohome", limit=10)
        
        if count > 0:
            return {
                'type': 'ir.actions.act_window',
                'name': f'Search Results: "zowohome" ({count} found)',
                'res_model': 'meilisearch.product.browse',
                'view_mode': 'tree,form',
                'view_id': self.env.ref('agentic_ai_integration_with_livechat.view_meilisearch_product_browse_tree').id,
                'target': 'current',
                'context': {'create': False, 'edit': False, 'delete': False},
                'views': [
                    (self.env.ref('agentic_ai_integration_with_livechat.view_meilisearch_product_browse_tree').id, 'tree'),
                    (self.env.ref('agentic_ai_integration_with_livechat.view_meilisearch_product_browse_form').id, 'form')
                ]
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Results',
                    'message': '❌ No product variants found for "zowohome". Check server logs for details.',
                    'type': 'warning',
                    'sticky': True,
                }
            }
    
    def setup_indexes(self):
        """Setup MeiliSearch indexes with proper configuration"""
        self.ensure_one()
        try:
            client_info = self.get_meilisearch_client()
            _logger.info(f"Setting up MeiliSearch indexes at {client_info['endpoint']}")
            
            # Create products index
            products_response = requests.post(
                f"{client_info['endpoint']}/indexes",
                headers=client_info['headers_post'],
                json={
                    "uid": self.products_index_name,
                    "primaryKey": "id"
                },
                timeout=10
            )
            
            if products_response.status_code not in [200, 201, 202]:
                error_detail = ""
                try:
                    error_detail = products_response.json()
                except:
                    error_detail = products_response.text
                raise UserError(f'❌ Index creation failed: HTTP {products_response.status_code}\nDetails: {error_detail}')
            
            # Apply enhanced settings
            enhanced_settings = {
                "searchableAttributes": [
                    "name_en", "name_ro", "name_hu",
                    "description_en", "description_ro", "description_hu",
                    "default_code", "brand",
                    "categories_combined_en", "categories_combined_ro", "categories_combined_hu"
                ],
                "filterableAttributes": [
                    "category_id", "category_ids", "brand", "available", "is_variant", "template_id"
                ]
            }
            
            settings_response = requests.patch(
                f"{client_info['endpoint']}/indexes/{self.products_index_name}/settings",
                headers=client_info['headers_post'],
                json=enhanced_settings,
                timeout=10
            )
            
            if settings_response.status_code not in [200, 201, 202]:
                error_detail = ""
                try:
                    error_detail = settings_response.json()
                except:
                    error_detail = settings_response.text
                raise UserError(f'❌ Index settings failed: HTTP {settings_response.status_code}\nDetails: {error_detail}')
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Index Setup',
                    'message': '✅ MeiliSearch indexes created with multiple categories support!',
                    'type': 'success',
                    'sticky': True,
                }
            }
            
        except requests.exceptions.RequestException as e:
            raise UserError(f'❌ Index setup failed: Network error: {str(e)}')
        except Exception as e:
            raise UserError(f'❌ Index setup error: {str(e)}')
    
    def debug_meilisearch_info(self):
        """Debug method to check MeiliSearch status"""
        self.ensure_one()
        try:
            client_info = self.get_meilisearch_client()
            
            stats_response = requests.get(
                f"{client_info['endpoint']}/stats",
                headers=client_info['headers'],
                timeout=5
            )
            
            indexes_response = requests.get(
                f"{client_info['endpoint']}/indexes",
                headers=client_info['headers'],
                timeout=5
            )
            
            debug_info = {
                'endpoint': client_info['endpoint'],
                'stats_status': stats_response.status_code,
                'indexes_status': indexes_response.status_code,
                'stats_data': stats_response.json() if stats_response.status_code == 200 else stats_response.text,
                'indexes_data': indexes_response.json() if indexes_response.status_code == 200 else indexes_response.text
            }
            
            _logger.info(f"MeiliSearch debug info: {debug_info}")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Debug Info',
                    'message': f'🔍 Check server logs for MeiliSearch debug details. Stats: {stats_response.status_code}, Indexes: {indexes_response.status_code}',
                    'type': 'info',
                    'sticky': True,
                }
            }
            
        except Exception as e:
            raise UserError(f'❌ Debug failed: {str(e)}')

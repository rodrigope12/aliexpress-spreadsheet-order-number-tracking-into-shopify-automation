import requests
import os
import json

class ShopifyClient:
    def __init__(self, shop_url=None, access_token=None, api_version=None):
        self.shop_url = shop_url or os.getenv('SHOPIFY_SHOP_URL')
        self.access_token = access_token or os.getenv('SHOPIFY_ACCESS_TOKEN')
        self.api_version = api_version or os.getenv('SHOPIFY_API_VERSION', '2024-01')
        
        # Clean up shop URL
        if self.shop_url and not self.shop_url.startswith('https://'):
            self.shop_url = f"https://{self.shop_url}"
        
        self.base_url = f"{self.shop_url}/admin/api/{self.api_version}"
        self.headers = {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json"
        }

    def _get(self, endpoint, params=None):
        """Helper for GET requests"""
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint, data):
        """Helper for POST requests"""
        url = f"{self.base_url}/{endpoint}"
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()

    def _graphql(self, query, variables=None):
        """Executes a GraphQL query."""
        url = f"{self.shop_url}/admin/api/{self.api_version}/graphql.json"
        response = requests.post(url, headers=self.headers, json={'query': query, 'variables': variables})
        response.raise_for_status()
        return response.json()

    def find_order_by_ali_id(self, aliexpress_id):
        """
        Robust search for Shopify Order by AliExpress ID using GraphQL.
        Checks: tags, customAttributes (note_attributes), and name.
        """
        # GraphQL Query to find orders by tag or generic search
        # Note: 'query' filter matches against name, email, tags, etc.
        gql_query = """
        query($query: String!) {
            orders(first: 5, query: $query) {
                edges {
                    node {
                        id
                        legacyResourceId
                        name
                        tags
                        customAttributes {
                            key
                            value
                        }
                        displayFulfillmentStatus
                    }
                }
            }
        }
        """
        
        try:
            # 1. Search by Tag (most reliable if tagged)
            data = self._graphql(gql_query, variables={"query": f"tag:{aliexpress_id}"})
            orders = data.get('data', {}).get('orders', {}).get('edges', [])
            
            if orders:
                return self._parse_gql_order(orders[0]['node'])

            # 2. General Search (Matches Name, Note Attributes in some cases)
            data = self._graphql(gql_query, variables={"query": str(aliexpress_id)})
            orders = data.get('data', {}).get('orders', {}).get('edges', [])
            
            for edge in orders:
                order = edge['node']
                # Verify exact match in attributes or name to avoid partial matches
                if self._verify_match(order, aliexpress_id):
                    return self._parse_gql_order(order)
            
            # 3. Fallback: Scan recent open orders (Deep Scan)
            # Only do this if we really expect it in note_attributes but it wasn't indexed
            return self._deep_scan_open_orders(aliexpress_id)
            
        except Exception as e:
            print(f"Error searching for order {aliexpress_id}: {e}")
            return None

    def _verify_match(self, order, target_id):
        """Verifies if the order actually matches the target ID"""
        target_id = str(target_id)
        
        # Check Name
        if target_id in order['name']:
            return True
            
        # Check Tags
        if target_id in order['tags']:
            return True
            
        # Check Attributes
        for attr in order['customAttributes']:
            if attr['value'] == target_id:
                return True
                
        return False

    def _deep_scan_open_orders(self, target_id):
        """Fetches recent open orders to check non-indexed attributes."""
        query = """
        {
            orders(first: 50, query: "status:open") {
                edges {
                    node {
                        id
                        legacyResourceId
                        name
                        customAttributes {
                            key
                            value
                        }
                    }
                }
            }
        }
        """
        try:
            data = self._graphql(query)
            orders = data.get('data', {}).get('orders', {}).get('edges', [])
            
            for edge in orders:
                order = edge['node']
                for attr in order['customAttributes']:
                    if attr['value'] == str(target_id):
                        return self._parse_gql_order(order)
            return None
        except Exception as e:
            print(f"Deep scan error: {e}")
            return None

    def _parse_gql_order(self, node):
        """Converts GraphQL node to simple dict format used by the app"""
        return {
            "id": node['legacyResourceId'],  # REST ID is needed for REST fulfillment endpoint
            "name": node['name'],
            "graphql_id": node['id']
        }

    def update_fulfillment(self, order_id, tracking_number, tracking_company="Other"):
        """
        Updates the fulfillment status of an order.
        1. Checks fulfillment orders (newer API) or
        2. Creates a fulfillment (legacy but often standard for simple updates).
        
        Using the 'fulfillment_create' endpoint (POST /orders/{order_id}/fulfillments.json)
        """
        # First, we need to get the 'location_id' (usually) or 'line_items' to fulfill.
        # But for dropshipping, often we just want to fulfill everything that is unfulfilled.
        
        try:
            # Step 1: Get Fulfillment Orders (New mechanism as of 2023)
            # We need the fulfillment_order_id to create a fulfillment.
            f_orders_resp = self._get(f"orders/{order_id}/fulfillment_orders.json")
            fulfillment_orders = f_orders_resp.get("fulfillment_orders", [])
            
            target_f_order = None
            for fo in fulfillment_orders:
                if fo['status'] == 'open':
                    target_f_order = fo
                    break
            
            if not target_f_order:
                print(f"No open fulfillment orders found for Order {order_id}")
                return False

            # Step 2: Create Fulfillment
            payload = {
                "fulfillment": {
                    "line_items_by_fulfillment_order": [
                        {
                            "fulfillment_order_id": target_f_order['id']
                        }
                    ],
                    "tracking_info": {
                        "number": tracking_number,
                        "company": tracking_company
                    }
                }
            }
            
            self._post("fulfillments.json", payload)
            print(f"Successfully fulfilled Order {order_id} with Tracking {tracking_number}")
            return True

        except Exception as e:
            print(f"Error updating fulfillment for Order {order_id}: {e}")
            # Fallback to legacy (if the shop is on an older version, though deprecated)
            return False

import shopify
import json
import os
import time
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd
from termcolor import colored

# --- Constants & Setup ---
CONFIG_PATH = 'config/config.json'
LOG_DIR = 'logs'

def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(colored("Error: config.json not found.", "red"))
        return None
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def log_message(message, level="INFO"):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] [{level}] {message}"
    
    # Print to console with color
    color = "white"
    if level == "SUCCESS": color = "green"
    elif level == "WARNING": color = "yellow"
    elif level == "ERROR": color = "red"
    print(colored(formatted_msg, color))
    
    # Write to file
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    with open(f"{LOG_DIR}/log_{today}.txt", "a") as f:
        f.write(formatted_msg + "\n")

# --- Shopify Connection ---
def connect_shopify(config):
    try:
        session = shopify.Session(
            config['shopify']['shop_url'],
            config['shopify']['api_version'],
            config['shopify']['access_token']
        )
        shopify.ShopifyResource.activate_session(session)
        shop = shopify.Shop.current()
        log_message(f"Connected to Shopify Store: {shop.name}", "SUCCESS")
        return True
    except Exception as e:
        log_message(f"Failed to connect to Shopify: {str(e)}", "ERROR")
        return False

# --- Google Sheets Connection ---
def get_google_sheet_data(config):
    try:
        creds_file = config['google_sheets']['credentials_file']
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        creds = service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)
        service = build('sheets', 'v4', credentials=creds)

        sheet_id = config['google_sheets']['spreadsheet_id']
        range_name = config['google_sheets']['worksheet_name']

        # Call the Sheets API
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=sheet_id, range=range_name).execute()
        values = result.get('values', [])

        if not values:
            log_message("No data found in Google Sheet.", "WARNING")
            return pd.DataFrame()

        # Convert to Pandas DataFrame
        df = pd.DataFrame(values[1:], columns=values[0])
        return df
    except Exception as e:
        log_message(f"Failed to read Google Sheet: {str(e)}", "ERROR")
        return pd.DataFrame()

# --- Core Logic ---
def find_shopify_order(ali_order_id, config):
    location = config['settings']['ali_id_location_in_shopify']
    
    # Strategy 1: Search by Note
    if location == 'note':
        orders = shopify.Order.find(limit=1, note=ali_order_id, status='any')
        if orders: return orders[0]

    # Strategy 2: Search by Tag
    if location == 'tags':
        # Shopify allows searching by tag
        orders = shopify.Order.find(limit=1, tag=ali_order_id, status='any')
        if orders: return orders[0]
        
    # Strategy 3: Note Attributes (Complex search, requires iteration or GraphQL ideally, but REST allows some filtering)
    # REST API doesn't support filtering by specific note_attributes directly efficiently without iterating
    # Fallback: Search all open orders (assuming recent) or use a broad search
    # For now, we will perform a broad search of the last 50 orders if not found by direct query
    # NOTE: This part implies we might need to iterate.
    
    # General Fallback: Search generic query
    try:
        # Search query matching common text fields
        orders = shopify.Order.find(limit=5, query=ali_order_id, status='any')
        if orders:
            # Verify exact match in attributes if required
            if location == 'note_attributes':
                target_key = config['settings'].get('ali_id_attribute_name')
                for order in orders:
                    for attr in getattr(order, 'note_attributes', []):
                        if attr.code == target_key and str(attr.value) == str(ali_order_id): # attr.code or attr.name depending on version
                            return order
                        # Sometimes key is 'name'
                        if getattr(attr, 'name', '') == target_key and str(attr.value) == str(ali_order_id):
                            return order
            else:
                return orders[0] # Return first match for other modes
    except Exception:
        pass
        
    return None

def update_fulfillment(order, tracking_number, config):
    if config['settings']['dry_run']:
        log_message(f"[DRY RUN] Would update Order #{order.order_number} with tracking {tracking_number}", "INFO")
        return True

    try:
        # Check if already fulfilled with this tracking number to avoid duplicates
        for fulfillment in order.fulfillments:
            for tracking in fulfillment.tracking_numbers:
                if tracking == tracking_number:
                    log_message(f"Order #{order.order_number} already has tracking {tracking_number}. Skipping.", "WARNING")
                    return True

        # Create Fulfillment
        new_fulfillment = shopify.Fulfillment(prefix_options={'order_id': order.id})
        new_fulfillment.location_id = order.location_id if order.location_id else None # Often needs explicit location
        
        # If location is None, we might need to fetch locations
        if not new_fulfillment.location_id:
             locations = shopify.Location.find()
             if locations:
                 new_fulfillment.location_id = locations[0].id

        new_fulfillment.tracking_info = {
            "number": tracking_number,
            # "company": "China Post" # Optional, can be auto-detected or mapped
        }
        
        # In newer API versions requires line_items_by_fulfillment_order usually, 
        # but for simple implementations keeping it legacy-compatible for 'Fulfillment' resource if possible.
        # Actually, 2023-01+ deprecated fulfillment endpoints in favor of fulfillment_orders.
        # Implementing robust FulfillmentOrder logic:
        
        fulfillment_orders = shopify.FulfillmentOrder.find(order_id=order.id)
        if not fulfillment_orders:
            log_message(f"No fulfillment orders found for #{order.order_number}", "ERROR")
            return False

        # Fulfill the first open fulfillment order
        target_fo = None
        for fo in fulfillment_orders:
            if fo.status == 'open':
                target_fo = fo
                break
        
        if target_fo:
            fulfillment = shopify.Fulfillment.create({
                'line_items_by_fulfillment_order': [
                    {
                        "fulfillment_order_id": target_fo.id
                    }
                ],
                'tracking_info': {
                    'number': tracking_number
                }
            })
            log_message(f"Successfully updated Order #{order.order_number}", "SUCCESS")
            return True
        else:
             log_message(f"Order #{order.order_number} has no open fulfillment orders.", "WARNING")
             return False

    except Exception as e:
        log_message(f"Failed to update #{order.order_number}: {str(e)}", "ERROR")
        return False

def main():
    print(colored("Starting Shopify Tracking Automation...", "cyan"))
    config = load_config()
    if not config: return

    if not connect_shopify(config): return
    
    df = get_google_sheet_data(config)
    if df.empty: return

    ali_col = config['google_sheets']['columns']['aliexpress_order_id']
    track_col = config['google_sheets']['columns']['tracking_number']

    log_message(f"Processing {len(df)} rows found in Sheet...", "INFO")

    processed_count = 0
    
    for index, row in df.iterrows():
        ali_id = str(row.get(ali_col, '')).strip()
        tracking_num = str(row.get(track_col, '')).strip()

        if not ali_id or not tracking_num:
            continue

        log_message(f"Processing AliExpress ID: {ali_id} -> Tracking: {tracking_num}", "INFO")

        # Find the Shopify Order
        order = find_shopify_order(ali_id, config)
        
        if order:
            success = update_fulfillment(order, tracking_num, config)
            if success:
                processed_count += 1
        else:
            log_message(f"Could not find Shopify Order for AliExpress ID: {ali_id}", "WARNING")

    log_message(f"Job Complete. updated {processed_count} orders.", "SUCCESS")

if __name__ == "__main__":
    main()

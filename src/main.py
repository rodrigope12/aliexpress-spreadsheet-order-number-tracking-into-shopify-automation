import os
import json
import argparse
import csv
from datetime import datetime
from dotenv import load_dotenv
from sheets_client import SheetReader
from shopify_client import ShopifyClient

# Constants
PROCESSED_FILE = "processed_orders.json"
LOGS_DIR = "logs"

def load_processed_ids():
    if os.path.exists(PROCESSED_FILE):
        try:
            with open(PROCESSED_FILE, 'r') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_processed_id(order_id):
    current = load_processed_ids()
    current.add(str(order_id))
    with open(PROCESSED_FILE, 'w') as f:
        json.dump(list(current), f)

def generate_report(results):
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR)
        
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = os.path.join(LOGS_DIR, f"report_{timestamp}.csv")
    
    headers = ['Timestamp', 'AliExpress ID', 'Tracking Number', 'Shopify Order Name', 'Status', 'Message']
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(results)
        print(f"\n[REPORT] Detailed report saved to: {filename}")
    except Exception as e:
        print(f"[ERROR] Failed to save report: {e}")

def main():
    parser = argparse.ArgumentParser(description="Sync AliExpress Tracking to Shopify")
    parser.add_argument("--dry-run", action="store_true", help="Run without making changes to Shopify")
    args = parser.parse_args()

    load_dotenv()
    
    # Check for configuration
    if not os.getenv('SHOPIFY_ACCESS_TOKEN'):
        print("Configuration not found or incomplete.")
        try:
            from setup_wizard import run_wizard
            if input("Run setup wizard now? (y/n): ").lower() == 'y':
                run_wizard()
                load_dotenv() # Reload env
            else:
                print("Please configure .env manually or run with --setup.")
                return
        except ImportError:
            print("Setup wizard not found. Please configure .env manually.")
            return

    # Initialize Clients
    try:
        sheets = SheetReader()
        shopify = ShopifyClient()
    except Exception as e:
        print(f"Initialization Error: {e}")
        return

    # 1. Read Data
    try:
        all_data = sheets.get_data()
        if all_data.empty:
            print("No data to process.")
            return
            
        processed_ids = load_processed_ids()
        new_rows, id_col = sheets.get_new_rows(all_data, processed_ids)
        
        print(f"Found {len(new_rows)} new rows to process.")
        
    except Exception as e:
        print(f"Error reading sheets: {e}")
        return

    # 2. Process Rows
    success_count = 0
    fail_count = 0
    results = [] # Store results for reporting
    
    for index, row in new_rows.iterrows():
        ali_id = str(row[id_col])
        # Try to find tracking number column dynamically or assume standard
        tracking_col = next((c for c in row.keys() if 'tracking' in c.lower()), None)
        tracking_number = str(row[tracking_col]) if tracking_col else None
        
        log_entry = {
            'Timestamp': datetime.now().isoformat(),
            'AliExpress ID': ali_id,
            'Tracking Number': tracking_number,
            'Shopify Order Name': 'N/A',
            'Status': 'Failed',
            'Message': ''
        }
        
        if not tracking_number:
            msg = "No tracking number found in row."
            print(f"Skipping {ali_id}: {msg}")
            log_entry['Message'] = msg
            results.append(log_entry)
            fail_count += 1
            continue

        print(f"Processing AliExpress Order: {ali_id} -> Tracking: {tracking_number}")

        # 3. Find Shopify Order
        print(f"  Searching Shopify...")
        # Use new robust search
        shopify_order = shopify.find_order_by_ali_id(ali_id)
        
        if not shopify_order:
            msg = "Could not find Shopify Order for AliExpress ID."
            print(f"  [X] {msg}")
            log_entry['Message'] = msg
            results.append(log_entry)
            fail_count += 1
            continue
            
        shopify_order_id = shopify_order['id']
        shopify_order_name = shopify_order['name']
        log_entry['Shopify Order Name'] = shopify_order_name
        
        print(f"  [!] Match Found: {shopify_order_name} (ID: {shopify_order_id})")

        # 4. Update Fulfillment
        if args.dry_run:
            msg = "Dry Run - Match found, no update performed."
            print(f"  [DRY RUN] {msg}")
            log_entry['Status'] = 'Skipped'
            log_entry['Message'] = msg
            results.append(log_entry)
            success_count += 1
        else:
            if shopify.update_fulfillment(shopify_order_id, tracking_number):
                msg = "Successfully updated tracking."
                print(f"  [SUCCESS] {msg}")
                log_entry['Status'] = 'Success'
                log_entry['Message'] = msg
                results.append(log_entry)
                
                save_processed_id(ali_id)
                success_count += 1
            else:
                msg = "Failed to update fulfillment via API."
                print(f"  [ERROR] {msg}")
                log_entry['Message'] = msg
                results.append(log_entry)
                fail_count += 1

    # Generate Report
    if results:
        generate_report(results)

    print(f"\n--- Batch Complete ---")
    print(f"Success: {success_count}")
    print(f"Failed: {fail_count}")

if __name__ == "__main__":
    main()

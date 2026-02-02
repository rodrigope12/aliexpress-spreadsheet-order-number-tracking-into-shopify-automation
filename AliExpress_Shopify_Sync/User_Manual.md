# AliExpress to Shopify Tracking Automation - User Manual

## Overview
This tool automates the tedious process of updating tracking numbers in Shopify. It reads from your supplier's Google Sheet, finds the corresponding Shopify order using the AliExpress Order ID, and updates the tracking information automatically.

---

## 1. Prerequisites

Before running the tool, you need to set up credentials for Shopify and Google Sheets.

### A. Shopify Admin Token
1. Log in to your Shopify Admin panel.
2. Go to **Settings > Apps and sales channels > Develop apps**.
3. Click **Create an app**. Name it "Tracking Automation".
4. Click **Configure Admin API scopes**.
5. Enable the following scopes:
   - `write_fulfillments`
   - `read_fulfillments`
   - `read_orders`
   - `read_merchant_managed_fulfillment_orders`
   - `write_merchant_managed_fulfillment_orders`
6. Click **Save** and then **Install app**.
7. Reveal and copy the **Admin API access token** (starts with `shpat_...`). You will need this for the config file.

### B. Google Sheets API Credentials
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project.
3. Enable the **Google Sheets API**.
4. Go to **Credentials > Create Credentials > Service Account**.
5. Give it a name and click Done.
6. Click on the newly created email address, go to the **Keys** tab, and click **Add Key > Create new key > JSON**.
7. A file will download. Rename it to `credentials.json` and place it in the `config/` folder of this tool.
8. **CRITICAL:** Open your supplier's Google Sheet and click **Share**. Paste the `client_email` found inside the `credentials.json` file and give it **Viewer** access.

---

## 2. Configuration (`config.json`)

Open the `config/config.json` file and update the values:

```json
{
    "shopify": {
        "shop_url": "your-store.myshopify.com",
        "access_token": "PASTE_YOUR_SHPAT_TOKEN_HERE",
        "api_version": "2024-01"
    },
    "google_sheets": {
        "spreadsheet_id": "THE_LONG_ID_IN_THE_SHEET_URL",
        "worksheet_name": "Sheet1",
        "columns": {
            "aliexpress_order_id": "AliExpress Order ID",  <-- Update column header name
            "tracking_number": "Tracking Number"           <-- Update column header name
        }
    }
}
```

### Important: Order Matching Strategy
You must tell the script where to find the AliExpress Order ID inside your Shopify Order.
In `config.json`, change `"ali_id_location_in_shopify"` to one of:
- `"note"` (If the ID is in the order notes)
- `"tags"` (If the ID is a tag)
- `"note_attributes"` (Common for DSers. Also set `"ali_id_attribute_name"`)

---

## 3. Installation

1. Install Python (if not installed).
2. Open a terminal in this folder.
3. Run the following command to install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## 4. Running the Automation

To run the tool:
```bash
python main.py
```

### Dry Run Mode
By default, the tool is in **Dry Run Mode** (Safe Mode). It will scan and tell you what it *would* do, but it won't actually update Shopify.
To enable real updates, change `"dry_run": true` to `"dry_run": false` in `config.json`.

---

## 5. Logs & Troubleshooting
- A log file is generated daily in the `logs/` folder.
- If orders are skipped, check the log to see if the AliExpress ID was not found.

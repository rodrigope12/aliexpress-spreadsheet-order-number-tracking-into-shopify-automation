# AliExpress Tracking Automation - Setup & Usage

This automation reads tracking numbers from a Google Sheet and updates the corresponding orders in Shopify.

## 1. Setup

### Python Environment
Ensure you have Python installed. Install dependencies:
```bash
pip install -r requirements.txt
```

### 1. Interactive Setup (Recommended)
Run the setup wizard to automatically configure your credentials:
```bash
python3 src/setup_wizard.py
```
The wizard will ask for:
- **Shopify Shop URL** (e.g. `your-store.myshopify.com`)
- **Shopify Admin API Access Token**
- **Google Service Account JSON Path**
- **Google Sheet Name**

It will validate your connections immediately and save them to a `.env` file.

### Manual Setup (Alternative)
If you prefer to configure manually, copy `.env.example` to `.env` and fill in the values:

**A. Google Sheets**
1. Go to Google Cloud Console.
2. Create a Service Account and download the JSON key.
3. Save it as `credentials.json` in this folder.
4. **Important**: Share your Google Sheet with the service account email (inside the JSON).

**B. Shopify**
1. Go to Shopify Admin > Settings > Apps and sales channels > Develop apps.
2. Create an app (e.g., "Tracking Sync").
3. Configure Admin API Scopes: `write_fulfillments`, `read_fulfillments`, `read_orders`.
4. Install app and reveal the **Admin API Access Token**.
5. Add it to `.env`.

## 2. Usage

### Dry Run (Test Mode)
Checks for matches but **does not** update Shopify.
```bash
python3 src/main.py --dry-run
```

### Live Run
Updates Shopify and saves processed IDs to `processed_orders.json`.
```bash
python3 src/main.py
```

## 3. How Matching Works
The script tries to find the Shopify Order using the **AliExpress Order Number** from the sheet.
It checks in this order:
1. **Tags**: Checks if the order has a tag matching the ID (e.g. `123456789`).
2. **Note Attributes**: Checks recent open orders to see if a custom attribute matches.
3. **Legacy Name**: Checks if the order name matches directly (unlikely).

## 4. Automation
You can schedule this script to run every hour using `cron` (Mac/Linux) or Task Scheduler (Windows).
Example cron (every hour):
```bash
0 * * * * cd "/Users/rodrigoperezcordero/Documents/TRABAJO/Aliexpress: Spreadsheet order number tracking into shopify Automation" && /usr/bin/python3 src/main.py >> output.log 2>&1
```

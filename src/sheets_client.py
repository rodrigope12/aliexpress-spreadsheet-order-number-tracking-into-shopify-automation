import gspread
import pandas as pd
import os
from google.oauth2.service_account import Credentials

class SheetReader:
    def __init__(self, credentials_path=None, sheet_name=None):
        self.credentials_path = credentials_path or os.getenv('GOOGLE_SHEETS_CREDENTIALS_FILE')
        self.sheet_name = sheet_name or os.getenv('GOOGLE_SHEET_NAME')
        self.scope = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        self.client = None
        self.sheet = None

    def connect(self):
        """Authenticates with Google Sheets API."""
        if not self.credentials_path or not os.path.exists(self.credentials_path):
            raise FileNotFoundError(f"Credentials file not found at: {self.credentials_path}")
        
        creds = Credentials.from_service_account_file(self.credentials_path, scopes=self.scope)
        self.client = gspread.authorize(creds)
        print(f"Connected to Google Sheets services.")

    def get_data(self):
        """Reads all records from the sheet and returns a DataFrame."""
        if not self.client:
            self.connect()
        
        try:
            # Open the spreadsheet
            print(f"Opening sheet: {self.sheet_name}")
            spreadsheet = self.client.open(self.sheet_name)
            
            # Select the first worksheet (assuming data is there)
            self.sheet = spreadsheet.sheet1
            
            # Get all values
            data = self.sheet.get_all_records()
            
            if not data:
                print("No data found in the sheet.")
                return pd.DataFrame()
                
            df = pd.DataFrame(data)
            print(f"Successfully loaded {len(df)} rows.")
            return df
            
        except Exception as e:
            print(f"Error reading Google Sheet: {e}")
            raise

    def get_new_rows(self, all_data, processed_ids):
        """
        Filters the dataframe to return only rows that haven't been processed.
        Assumes 'AliExpress Order No' or similar unique ID exists.
        
        Args:
            all_data (pd.DataFrame): The full dataset from the sheet.
            processed_ids (set): A set of AliExpress Order IDs that were already processed.
        
        Returns:
            pd.DataFrame: A dataframe containing only the new rows.
        """
        # Determine the ID column (flexible check)
        # Determine the ID column (flexible check)
        possible_id_cols = ['AliExpress Order No', 'Order Number', 'Order No', 'AliExpress Order ID', 'AliExpress ID']
        id_col = next((col for col in possible_id_cols if col in all_data.columns), None)
        
        if not id_col:
            raise ValueError(f"Could not find an Order ID column. Available columns: {all_data.columns.tolist()}")
            
        # Filter rows
        # Ensure IDs are treated as strings and stripped of whitespace
        all_data[id_col] = all_data[id_col].astype(str).str.strip()
        
        # Clean up tracking numbers if the column exists
        possible_tracking_cols = ['Tracking Number', 'Tracking No', 'Tracking', 'Number']
        tracking_col = next((col for col in possible_tracking_cols if col in all_data.columns), None)
        if tracking_col:
             all_data[tracking_col] = all_data[tracking_col].astype(str).str.strip()

        # Filter where ID is NOT in processed_ids
        # We check if the ID is present in the processed_ids set
        new_rows = all_data[~all_data[id_col].isin(processed_ids)].copy()
        
        return new_rows, id_col

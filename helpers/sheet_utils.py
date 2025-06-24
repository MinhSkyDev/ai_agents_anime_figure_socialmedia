from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from config import SERVICE_ACCOUNT_FILE, SPREADSHEET_ID, RANGE_NAME, ARCHIVE_RANGE
from datetime import datetime
import logging

def get_sheet_service():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return build('sheets', 'v4', credentials=creds)

def fetch_image_url():
    service = get_sheet_service()
    result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
    values = result.get('values', [])
    if not values or not values[0]:
        raise ValueError('Cell A1 is empty')
    return values[0][0]

def archive_image_url(url):
    service = get_sheet_service()
    sheet = service.spreadsheets()
    timestamp = datetime.now().isoformat()
    sheet.values().append(spreadsheetId=SPREADSHEET_ID, range=ARCHIVE_RANGE, valueInputOption='RAW', body={'values': [[url, timestamp]]}).execute()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range='Sheet1!A2:A').execute()
    values = result.get('values', [])
    if values:
        sheet.values().update(spreadsheetId=SPREADSHEET_ID, range='Sheet1!A1', valueInputOption='RAW', body={'values': values}).execute()
        sheet.values().clear(spreadsheetId=SPREADSHEET_ID, range=f'Sheet1!A{len(values)+1}').execute()
    else:
        sheet.values().clear(spreadsheetId=SPREADSHEET_ID, range='Sheet1!A1').execute()
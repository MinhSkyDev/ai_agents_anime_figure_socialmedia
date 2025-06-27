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

def fetch_image_description():
    """Retrieve the user-provided image description from cell B1."""
    service = get_sheet_service()
    result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range='Sheet1!B1').execute()
    values = result.get('values', [])
    if not values or not values[0]:
        raise ValueError('Cell B1 is empty')
    return values[0][0]

def archive_image_data(url, description):
    """Archive image URL and description to the archive sheet."""
    service = get_sheet_service()
    sheet = service.spreadsheets()
    timestamp = datetime.now().isoformat()

    # Append URL and description to the archive sheet
    sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=ARCHIVE_RANGE,
        valueInputOption='RAW',
        body={'values': [[url, description, timestamp]]}
    ).execute()

    # Shift the remaining rows up in Sheet1
    url_result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range='Sheet1!A2:A').execute()
    url_values = url_result.get('values', [])

    desc_result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range='Sheet1!B2:B').execute()
    desc_values = desc_result.get('values', [])

    if url_values and desc_values:
        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range='Sheet1!A1',
            valueInputOption='RAW',
            body={'values': url_values}
        ).execute()

        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range='Sheet1!B1',
            valueInputOption='RAW',
            body={'values': desc_values}
        ).execute()

        sheet.values().clear(
            spreadsheetId=SPREADSHEET_ID,
            range=f'Sheet1!A{len(url_values)+1}'
        ).execute()

        sheet.values().clear(
            spreadsheetId=SPREADSHEET_ID,
            range=f'Sheet1!B{len(desc_values)+1}'
        ).execute()
    else:
        # If there are no remaining rows, clear A1 and B1
        sheet.values().clear(spreadsheetId=SPREADSHEET_ID, range='Sheet1!A1').execute()
        sheet.values().clear(spreadsheetId=SPREADSHEET_ID, range='Sheet1!B1').execute()

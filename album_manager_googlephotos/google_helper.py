import os

import httplib2
from google.oauth2.credentials import Credentials
from google_auth_httplib2 import Request
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

# The CLIENT_SECRETS_FILE variable specifies the name of a file that contains
# the OAuth 2.0 information for this application, including its client_id and
# client_secret.
CLIENT_SECRETS_FILE = "client_secret.json"
CLIENT_CREDENTIALS_FILE = "client_credentials.json"

# This access scope grants read-only access to the authenticated user's Drive
# account.
SCOPES = ['https://www.googleapis.com/auth/photoslibrary']
API_SERVICE_NAME = 'photoslibrary'
API_VERSION = 'v1'


def get_authenticated_photos_library_service(service=None):
    if service:
        return service

    creds = None
    if os.path.exists(CLIENT_CREDENTIALS_FILE):
        creds = Credentials.from_authorized_user_file(CLIENT_CREDENTIALS_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request(httplib2.Http()))
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server()
    with open(CLIENT_CREDENTIALS_FILE, 'w') as f:
        f.write(creds.to_json())
    return build(API_SERVICE_NAME, API_VERSION, credentials=creds, static_discovery=False)

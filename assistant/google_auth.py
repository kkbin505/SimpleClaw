import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from config import SCOPES, CREDENTIALS_FILE, TOKEN_FILE


def get_credentials() -> Credentials:
    creds = None

    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r") as f:
                token_data = json.load(f)
            actual_scopes = token_data.get("scopes", [])
            if actual_scopes:
                missing_scopes = [s for s in SCOPES if s not in actual_scopes]
                if not missing_scopes:
                    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            pass

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                # Token is revoked or invalid, re-authenticate
                print(f"Token refresh failed: {e}. Re-authenticating...")
                os.remove(TOKEN_FILE)
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return creds


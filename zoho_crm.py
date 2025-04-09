# zoho_crm.py

import requests
import os
from dotenv import load_dotenv

load_dotenv()

class ZohoCRMService:
    def __init__(self, client_id, client_secret, refresh_token):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.access_token = self._get_access_token()

    def _get_access_token(self):
        token_url = "https://accounts.zoho.eu/oauth/v2/token"
        params = {
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token"
        }
        resp = requests.post(token_url, data=params)
        resp.raise_for_status()
        data = resp.json()
        if "access_token" not in data:
            raise ValueError("Failed to get Zoho access token.")
        return data["access_token"]

    def _refresh_token_if_needed(self, response):
        if response.status_code == 401:
            # Possibly token expired
            self.access_token = self._get_access_token()
            return True
        return False

    def search_records(self, module_name, criteria):
        url = f"https://www.zohoapis.eu/crm/v2/{module_name}/search"
        headers = {"Authorization": f"Zoho-oauthtoken {self.access_token}"}
        params = {"criteria": criteria}

        r = requests.get(url, headers=headers, params=params)
        if self._refresh_token_if_needed(r):
            r = requests.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
        return data.get("data", [])

    def update_record(self, module_name, record_id, fields_to_update):
        url = f"https://www.zohoapis.eu/crm/v2/{module_name}/{record_id}"
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "data": [
                {
                    "id": record_id,
                    **fields_to_update
                }
            ]
        }
        r = requests.patch(url, headers=headers, json=payload)
        if self._refresh_token_if_needed(r):
            r = requests.patch(url, headers=headers, json=payload)
        r.raise_for_status()
        return r.json()

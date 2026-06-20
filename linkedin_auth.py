#!/usr/bin/env python3
"""LinkedIn OAuth 2.0 flow to get access token and person ID.

Usage:
  python3 linkedin_auth.py

This will:
1. Open your browser to LinkedIn authorization page
2. Start a local server to capture the callback
3. Exchange the code for an access token
4. Fetch your LinkedIn Person ID
5. Print the values to add to .env
"""

import http.server
import json
import os
import urllib.parse
import webbrowser
import httpx
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ["LINKEDIN_CLIENT_ID"]
CLIENT_SECRET = os.environ["LINKEDIN_CLIENT_SECRET"]
REDIRECT_URI = os.environ.get("LINKEDIN_REDIRECT_URI", "http://localhost:8080/callback")
SCOPES = "openid profile w_member_social"

auth_code = None


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Success! You can close this tab.</h1><p>Go back to your terminal.</p>")
        else:
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            error = params.get("error", ["unknown"])[0]
            self.wfile.write(f"<h1>Error: {error}</h1>".encode())

    def log_message(self, format, *args):
        pass  # Suppress log output


def main():
    # Step 1: Open browser for authorization
    auth_url = (
        f"https://www.linkedin.com/oauth/v2/authorization?"
        f"response_type=code&"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={urllib.parse.quote(REDIRECT_URI)}&"
        f"scope={urllib.parse.quote(SCOPES)}"
    )

    print("Opening browser for LinkedIn authorization...")
    print(f"If browser doesn't open, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    # Step 2: Start local server to capture callback
    print("Waiting for callback on http://localhost:8080/callback ...")
    server = http.server.HTTPServer(("localhost", 8080), CallbackHandler)
    server.handle_request()  # Handle one request

    if not auth_code:
        print("ERROR: No authorization code received.")
        return

    print(f"Authorization code received!")

    # Step 3: Exchange code for access token
    print("Exchanging code for access token...")
    token_resp = httpx.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    if token_resp.status_code != 200:
        print(f"ERROR: Token exchange failed: {token_resp.status_code}")
        print(token_resp.text)
        return

    token_data = token_resp.json()
    access_token = token_data["access_token"]
    expires_in = token_data.get("expires_in", "unknown")
    print(f"Access token received! Expires in {expires_in} seconds")

    # Step 4: Fetch person ID
    print("Fetching your LinkedIn Person ID...")
    profile_resp = httpx.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    if profile_resp.status_code == 200:
        profile = profile_resp.json()
        person_id = profile.get("sub", "")
        name = profile.get("name", "")
        print(f"Hello, {name}!")
    else:
        print(f"Profile fetch failed: {profile_resp.status_code}")
        print("Trying alternate endpoint...")
        me_resp = httpx.get(
            "https://api.linkedin.com/v2/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if me_resp.status_code == 200:
            me_data = me_resp.json()
            person_id = me_data.get("id", "")
            name = f"{me_data.get('localizedFirstName', '')} {me_data.get('localizedLastName', '')}"
            print(f"Hello, {name}!")
        else:
            print(f"ERROR: Could not fetch profile: {me_resp.text[:200]}")
            person_id = ""

    # Step 5: Print results
    print("\n" + "=" * 60)
    print("ADD THESE TO YOUR .env FILE:")
    print("=" * 60)
    print(f"LINKEDIN_ACCESS_TOKEN={access_token}")
    print(f"LINKEDIN_PERSON_ID={person_id}")
    print("=" * 60)
    print(f"\nToken expires in ~{int(expires_in)//86400} days")


if __name__ == "__main__":
    main()

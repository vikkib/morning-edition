#!/usr/bin/env python3
"""Run this locally ONCE to get your Google OAuth refresh token.
Then add the three values as GitHub Secrets.

Usage: python3 setup-google-auth.py
"""
import json, urllib.request, urllib.parse, webbrowser, http.server

print("=== Google OAuth Setup ===")
print("You need a Google Cloud project with Calendar API enabled.")
print("Create OAuth 2.0 credentials (Desktop app) at console.cloud.google.com\n")

CLIENT_ID     = input("Paste your Google Client ID: ").strip()
CLIENT_SECRET = input("Paste your Google Client Secret: ").strip()

REDIRECT_URI = "http://localhost:8080"
SCOPE        = "https://www.googleapis.com/auth/calendar.readonly"

auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
    "client_id":     CLIENT_ID,
    "redirect_uri":  REDIRECT_URI,
    "response_type": "code",
    "scope":         SCOPE,
    "access_type":   "offline",
    "prompt":        "consent"
})

print(f"\nOpening browser. If it doesn't open, visit:\n{auth_url}\n")
webbrowser.open(auth_url)

auth_code = None

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Done. Close this window and check your terminal.")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"No code found.")
    def log_message(self, *args):
        pass

print("Waiting for Google redirect on localhost:8080...")
http.server.HTTPServer(("localhost", 8080), Handler).handle_request()

if not auth_code:
    print("ERROR: No auth code received.")
    exit(1)

data = urllib.parse.urlencode({
    "client_id":     CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "code":          auth_code,
    "grant_type":    "authorization_code",
    "redirect_uri":  REDIRECT_URI
}).encode()

req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
with urllib.request.urlopen(req) as r:
    tokens = json.loads(r.read())

refresh_token = tokens.get("refresh_token")
if not refresh_token:
    print("\nERROR: No refresh token. Try running again.")
    exit(1)

print("\n=== Add these 3 secrets to your GitHub repo ===")
print(f"GOOGLE_CLIENT_ID:     {CLIENT_ID}")
print(f"GOOGLE_CLIENT_SECRET: {CLIENT_SECRET}")
print(f"GOOGLE_REFRESH_TOKEN: {refresh_token}")
print("\nGo to: github.com/vikkib/morning-edition/settings/secrets/actions")

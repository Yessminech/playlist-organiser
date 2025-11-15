import base64
import hashlib
import os
import urllib.parse
import requests
import http.server
import socketserver
import webbrowser
import argparse
import json
import time
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
SCOPES = os.getenv("SPOTIFY_SCOPES")
AUTH_CODE = None
CODE_VERIFIER = None

# ----------------------------------------------
#  PKCE HELPERS
# ----------------------------------------------
def generate_pkce_pair():
    verifier = base64.urlsafe_b64encode(os.urandom(64)).rstrip(b"=")
    digest = hashlib.sha256(verifier).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=")
    return verifier.decode(), challenge.decode()


# ----------------------------------------------
#  OAuth Callback Handler
# ----------------------------------------------
class OAuthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        global AUTH_CODE

        print("\n🔥 CALLBACK:", self.path)

        if self.path.startswith("/callback") and "code=" in self.path:
            AUTH_CODE = self.path.split("code=")[1].split("&")[0]

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h1>Spotify authentication complete!</h1>You may close this window.")
            return

        if "favicon" in self.path:
            self.send_response(204)
            self.end_headers()
            return

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Waiting for Spotify authentication...")


# ----------------------------------------------
#  Perform OAuth + Token Exchange with PKCE
# ----------------------------------------------
def get_spotify_token():
    global CODE_VERIFIER, AUTH_CODE

    CODE_VERIFIER, code_challenge = generate_pkce_pair()

    auth_url = (
        "https://accounts.spotify.com/authorize?"
        + urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge
        })
    )

    print("🔄 Opening Spotify login page...")
    webbrowser.open(auth_url)

    with socketserver.TCPServer(("127.0.0.1", 9090), OAuthHandler) as httpd:
        print("🔌 Waiting for Spotify authentication...")
        while AUTH_CODE is None:
            httpd.handle_request()

    print("🔑 Authorization code received, requesting token…")

    token_url = "https://accounts.spotify.com/api/token"
    data = {
        "client_id": CLIENT_ID,
        "grant_type": "authorization_code",
        "code": AUTH_CODE,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": CODE_VERIFIER
    }

    r = requests.post(token_url, data=data)
    token_info = r.json()

    if "error" in token_info:
        print("❌ ERROR:", token_info)
        raise RuntimeError("Could not obtain access token")

    print("✅ Access token OK.")
    return token_info["access_token"]

# --------------------------------------------------------
# SPOTIFY HELPERS
# --------------------------------------------------------
def spotify_search_track(song, artist, token):
    query = f"{song} {artist}"
    url = "https://api.spotify.com/v1/search?" + urllib.parse.urlencode({
        "q": query,
        "type": "track",
        "limit": 1
    })

    r = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    items = r.json().get("tracks", {}).get("items", [])
    if items:
        return items[0]["id"]

    # fallback (song only)
    url = "https://api.spotify.com/v1/search?" + urllib.parse.urlencode({
        "q": song,
        "type": "track",
        "limit": 1
    })
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    items = r.json().get("tracks", {}).get("items", [])
    if items:
        return items[0]["id"]

    return None


def get_user_id(token):
    r = requests.get("https://api.spotify.com/v1/me",
                     headers={"Authorization": f"Bearer {token}"})
    return r.json()["id"]


def create_playlist(user_id, name, token):
    r = requests.post(
        f"https://api.spotify.com/v1/users/{user_id}/playlists",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"},
        data=json.dumps({
            "name": name,
            "description": "Harmonic/ BPM Mix Playlist",
            "public": False
        })
    )
    return r.json()["id"]


def add_tracks_to_playlist(playlist_id, track_ids, token):
    for i in range(0, len(track_ids), 100):
        batch = track_ids[i:i+100]
        requests.post(
            f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            data=json.dumps({"uris": [f"spotify:track:{tid}" for tid in batch]})
        )
        time.sleep(0.2)


# --------------------------------------------------------
# MAIN UPLOAD LOGIC
# --------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="JSON mix file")
    parser.add_argument("--name", required=False, help="Playlist name")
    parser.add_argument(
    "--playlist-id",
    required=False,
    help="If provided, songs will be added to this existing playlist instead of creating a new one."
)
    args = parser.parse_args()

    # load playlist JSON
    with open(args.input, "r", encoding="utf-8") as f:
        songs = json.load(f)

    token = get_spotify_token()
    user_id = get_user_id(token)

    playlist_name = args.name or os.path.splitext(os.path.basename(args.input))[0]
    # 4) Determine target playlist
    if args.playlist_id:
        playlist_id = args.playlist_id
        print(f"📀 Using EXISTING playlist: {playlist_id}")
    else:
        playlist_name = args.name or os.path.splitext(os.path.basename(args.input))[0]
        print(f"📀 Creating NEW playlist: {playlist_name}")
        playlist_id = create_playlist(user_id, playlist_name, token)
        print("📀 Playlist created with ID:", playlist_id)

    track_ids = []
    missing = []

    for s in songs:

        # --- 1) If URL already exists, extract track ID ---
        if s.get("url"):
            match = None
            url = s["url"]
            if "track/" in url:
                match = url.split("track/")[1].split("?")[0]
            elif url.startswith("spotify:track:"):
                match = url.split(":")[-1]

            if match:
                track_ids.append(match)
                continue  # skip search entirely

        # --- 2) Otherwise: use Spotify search ---
        tid = spotify_search_track(s["song"], s["artist"], token)
        if tid:
            track_ids.append(tid)
        else:
            missing.append(s["song"])


    add_tracks_to_playlist(playlist_id, track_ids, token)

    print("\n✨ Playlist created!")
    print(f"https://open.spotify.com/playlist/{playlist_id}")

    if missing:
        print("\n⚠ Missing:")
        for m in missing:
            print("  -", m)


if __name__ == "__main__":
    main()

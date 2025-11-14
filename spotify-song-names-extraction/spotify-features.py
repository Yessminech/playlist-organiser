#!/usr/bin/env python3

import argparse 
import codecs
import http.server
import json
import logging
import re
import sys
import time
import os
import urllib.parse
import urllib.request
import webbrowser

logging.basicConfig(level=20, datefmt='%I:%M:%S', format='[%(asctime)s] %(message)s')


# ================================================================
#                         SPOTIFY API WRAPPER
# ================================================================
class SpotifyAPI:
    def __init__(self, auth):
        self._auth = auth

    # ------------------------------------------------------------
    # GET request with retries
    # ------------------------------------------------------------
    def get(self, url, params={}, tries=3):
        if not url.startswith("https://api.spotify.com/v1/"):
            url = "https://api.spotify.com/v1/" + url

        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)

        for _ in range(tries):
            try:
                req = urllib.request.Request(url)
                req.add_header("Authorization", "Bearer " + self._auth)
                res = urllib.request.urlopen(req)
                reader = codecs.getreader("utf-8")
                return json.load(reader(res))

            except Exception as err:
                logging.info(f"Could not load URL: {url} ({err})")
                time.sleep(2)
                logging.info("Retrying...")

        sys.exit(1)

    # ------------------------------------------------------------
    # Spotify pagination handler
    # ------------------------------------------------------------
    def list(self, url, params={}):
        last_log = time.time()
        response = self.get(url, params)
        items = response["items"]

        while response["next"]:
            if time.time() > last_log + 15:
                last_log = time.time()
                logging.info(f"Loaded {len(items)}/{response['total']} items")

            response = self.get(response["next"])
            items += response["items"]

        return items

    # ------------------------------------------------------------
    # Authorization (Implicit Grant)
    # ------------------------------------------------------------
    @staticmethod
    def authorize(client_id, scope):
        url = (
            "https://accounts.spotify.com/authorize?"
            + urllib.parse.urlencode({
                "response_type": "token",
                "client_id": client_id,
                "scope": scope,
                "redirect_uri": f"http://127.0.0.1:{SpotifyAPI._SERVER_PORT}/redirect"
            })
        )

        logging.info(f"Logging in: {url}")
        webbrowser.open(url)

        server = SpotifyAPI._AuthorizationServer("127.0.0.1", SpotifyAPI._SERVER_PORT)
        try:
            while True:
                server.handle_request()
        except SpotifyAPI._Authorization as auth:
            return SpotifyAPI(auth.access_token)

    _SERVER_PORT = 43019

    class _AuthorizationServer(http.server.HTTPServer):
        def __init__(self, host, port):
            super().__init__((host, port), SpotifyAPI._AuthorizationHandler)

        def handle_error(self, request, client_address):
            raise

    class _AuthorizationHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/redirect"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b'<script>location.replace("token?" + location.hash.slice(1));</script>'
                )

            elif self.path.startswith("/token?"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<script>close()</script>Thanks! You may now close this window.")

                access_token = re.search(r"access_token=([^&]*)", self.path).group(1)
                logging.info(f"Received Spotify token: {access_token}")

                raise SpotifyAPI._Authorization(access_token)

            else:
                self.send_error(404)

        def log_message(self, *args):
            pass

    class _Authorization(Exception):
        def __init__(self, token):
            self.access_token = token


# ================================================================
#                           MAIN PROGRAM
# ================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Export Spotify playlists as cleaned JSON (song + artist only)"
    )
    parser.add_argument("--token", help="Provide OAuth token manually")
    parser.add_argument(
        "--dump",
        default="playlists",
        choices=["liked", "playlists", "liked,playlists", "playlists,liked"],
        help="What to export"
    )
    parser.add_argument(
        "--filter",
        help="Export only playlists whose name contains this substring"
    )
    args = parser.parse_args()

    # authenticate
    if args.token:
        spotify = SpotifyAPI(args.token)
    else:
        spotify = SpotifyAPI.authorize(
            client_id="5c098bcc800e45d49e476265bc9b6934",
            scope="playlist-read-private playlist-read-collaborative user-library-read"
        )

    logging.info("Loading user info...")
    me = spotify.get("me")
    logging.info(f"Logged in as {me['display_name']} ({me['id']})")

    playlists = []
    liked_albums = []

    # ---------------- Liked songs ----------------
    if "liked" in args.dump:
        logging.info("Loading liked songs and albums...")
        liked_tracks = spotify.list("me/tracks", {"limit": 50})
        playlists.append({"name": "Liked Songs", "tracks": liked_tracks})

    # ---------------- Playlists ----------------
    if "playlists" in args.dump:
        logging.info("Loading playlists...")
        playlist_data = spotify.list(f"users/{me['id']}/playlists", {"limit": 50})
        logging.info(f"Found {len(playlist_data)} playlists")

        if args.filter:
            substring = args.filter.lower()
            playlist_data = [p for p in playlist_data if substring in p["name"].lower()]
            logging.info(f"Filtered → {len(playlist_data)} match '{args.filter}'")

        for playlist in playlist_data:
            logging.info(f"Loading playlist: {playlist['name']} ...")
            playlist["tracks"] = spotify.list(playlist["tracks"]["href"], {"limit": 100})

        playlists.extend(playlist_data)

    # ==========================================================
    #                  WRITE CLEAN JSON FILES
    # ==========================================================
    logging.info("Writing playlist files...")

    for playlist in playlists:
        name = playlist["name"]
        safe_name = re.sub(r'[\\/*?:"<>|]', "_", name).strip()

        # ensure unique filename
        filename = safe_name + ".json"
        base = safe_name
        counter = 1

        while os.path.exists(filename):
            filename = f"{base}_{counter}.json"
            counter += 1

        # build cleaned track list
        cleaned = []
        for item in playlist["tracks"]:
            track = item.get("track") or item
            if not track:
                continue
            song = track.get("name")
            artists = ", ".join(a["name"] for a in track.get("artists", []))
            cleaned.append({"song": song, "artist": artists})

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, indent=2, ensure_ascii=False)

        logging.info(f"Saved → {filename}")


# ================================================================
# RUN
# ================================================================
if __name__ == "__main__":
    main()

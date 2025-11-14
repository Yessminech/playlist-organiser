#!/usr/bin/env python3
import os
import json
import re
from difflib import SequenceMatcher
import argparse
from tqdm import tqdm

import numpy as np
from PIL import Image
import easyocr

# ---------- OCR SETUP ----------
OUTPUT_DIR = "outputs"
reader = easyocr.Reader(['en'], gpu=False)
# --------------------------------


# ---------- HELPERS ----------

def load_songs(path):
    """Charge la liste des chansons de référence."""
    with open(path, "r", encoding="utf-8") as f:
        songs = json.load(f)
    for s in songs:
        s.setdefault("bpm", None)
        s.setdefault("key", None)
    return songs


def group_by_rows(ocr_items):
    """Regroupe les boxes OCR par lignes."""
    entries = []
    for item in ocr_items:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            box, text = item[0], item[1]
            if isinstance(text, str):
                entries.append((box, text))

    # Sort by Y position
    entries.sort(key=lambda x: x[0][0][1])

    rows = []
    current = []
    last_y = None
    threshold = 60

    for box, text in entries:
        y1 = box[0][1]
        y2 = box[2][1]
        yc = (y1 + y2) / 2

        if last_y is None or abs(yc - last_y) < threshold:
            current.append(text)
        else:
            if current:
                rows.append(" ".join(current))
            current = [text]

        last_y = yc

    if current:
        rows.append(" ".join(current))

    return rows


def extract_features(text):
    """Extrait BPM et Key."""
    t = text.lower()

    m_bpm = re.search(r'(\d{2,3})\s*bpm', t)
    bpm = int(m_bpm.group(1)) if m_bpm else None

    m_key = re.search(r'\b([0-1]?[0-9][ab])\b', t)
    key = m_key.group(1).upper() if m_key else None

    return bpm, key


def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def best_song_match(row_text, songs, min_score=0.35):
    """Fuzzy-match row → best song in library."""
    row = row_text.lower()

    best_idx = None
    best_score = 0

    for i, s in enumerate(songs):
        title = s["song"]
        artist = s.get("artist", "")
        cand = (title + " " + artist).lower()

        score = similarity(row, cand)
        if score > best_score:
            best_score = score
            best_idx = i

    # Too weak match → reject
    if best_idx is None or best_score < min_score:
        return None, best_score

    # Reject fake artist-only matches
    title_tokens = [w for w in re.split(r'\W+', songs[best_idx]["song"].lower()) if len(w) >= 3]
    if title_tokens and not any(tok in row for tok in title_tokens):
        return None, best_score

    return best_idx, best_score


# ---------- MAIN SCRIPT ----------

def main():
    parser = argparse.ArgumentParser(description="Extract BPM/Key from Spotify screenshots")
    parser.add_argument("--screenshots", required=True, help="Folder with screenshots")
    parser.add_argument("--songs", required=True, help="JSON file with song list")

    args = parser.parse_args()

    # --- FIX PATH FOR SONG FILE ---
    SONGS_FILE = args.songs

    # If user only typed a filename → look inside playlists/
    if not os.path.exists(SONGS_FILE):
        # case: user passed only a filename like "songs.json"
        if os.path.dirname(SONGS_FILE) == "":
            candidate = os.path.join("playlists", SONGS_FILE)
            if os.path.exists(candidate):
                SONGS_FILE = candidate
            else:
                raise FileNotFoundError(f"❌ Cannot find songs file: {SONGS_FILE}")
        else:
            # path contains folder but still not found → error
            raise FileNotFoundError(f"❌ Cannot find songs file: {SONGS_FILE}")

    # Always keep screenshots directory untouched
    SCREENSHOT_DIR = args.screenshots


    # Auto name output file
    base = os.path.splitext(os.path.basename(SONGS_FILE))[0]
    OUTPUT_FILE = base + "_features.json"

    # Load reference list
    songs = load_songs(SONGS_FILE)
    print(f"Loaded {len(songs)} songs from {SONGS_FILE}")

    matched = [False] * len(songs)

    # List screenshots
    images = sorted([
        f for f in os.listdir(SCREENSHOT_DIR)
        if f.lower().endswith((".png", ".jpg", ".jpeg"))
    ])

    # Collect OCR lines from ALL screenshots before matching
    all_rows = []
    for fname in images:
        img = Image.open(os.path.join(SCREENSHOT_DIR, fname))
        ocr_raw = reader.readtext(np.array(img), detail=1)

        ocr_items = [(item[0], item[1]) for item in ocr_raw if len(item) >= 2]
        rows = group_by_rows(ocr_items)

        for r in rows:
            r_clean = " ".join(r.split())
            low = r_clean.lower()
            if "bpm" not in low:
                continue
            if "funky haus" in low or "auto" in low:
                continue
            all_rows.append(r_clean)

    print(f"\n📝 Extracted {len(all_rows)} candidate rows across screenshots")
    print("🔎 Matching rows to songs...\n")

    # ---------- PROGRESS BAR MATCHING ----------
    for row_text in tqdm(all_rows, desc="Matching", ncols=90):

        bpm, key = extract_features(row_text)
        if bpm is None and key is None:
            continue

        idx, score = best_song_match(row_text, songs)
        if idx is None:
            continue

        s = songs[idx]
        updated = False

        if bpm is not None and s.get("bpm") is None:
            s["bpm"] = bpm
            updated = True
        if key is not None and s.get("key") is None:
            s["key"] = key
            updated = True

        if updated:
            matched[idx] = True

    # ---------- SUMMARY ----------
    total = len(songs)
    matched_count = sum(1 for m in matched if m)

    print(f"\n🎶 Songs matched: {matched_count}/{total}")

    # Missing match entirely
    missing_match = [s["song"] for i, s in enumerate(songs) if not matched[i]]
    if missing_match:
        print("\n⚠️ Songs with NO match at all:")
        for m in missing_match:
            print("  -", m)

    # Missing bpm or key
    incomplete = [s for s in songs if s["bpm"] is None or s["key"] is None]
    if incomplete:
        print("\n⚠️ Songs with incomplete features:")
        for s in incomplete:
            print(f"  - {s['song']} ({s['artist']})  [bpm={s['bpm']}, key={s['key']}]")

    # Save final JSON
    # remove .json extension if user provided it
    base_name = os.path.splitext(os.path.basename(SONGS_FILE))[0] + "_features"

    # generate unique file name in outputs/
    output_path = generate_unique_filename(OUTPUT_DIR, base_name, ".json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(songs, f, indent=2, ensure_ascii=False)

    print(f"\n✨ DONE! Saved: {OUTPUT_FILE}")

def generate_unique_filename(folder, base_name, extension=".json"):
    """
    Returns a unique filename inside `folder` by appending _1, _2, _3… if needed.
    Example:
        base_name = "songs_features"
        → songs_features.json
        → songs_features_1.json
        → songs_features_2.json
    """
    # Clean extension
    if not extension.startswith("."):
        extension = "." + extension

    # First candidate
    filename = f"{base_name}{extension}"
    full_path = os.path.join(folder, filename)

    # If exists → iterate
    counter = 1
    while os.path.exists(full_path):
        filename = f"{base_name}_{counter}{extension}"
        full_path = os.path.join(folder, filename)
        counter += 1

    return full_path

if __name__ == "__main__":
    main()

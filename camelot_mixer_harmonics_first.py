#!/usr/bin/env python3
import json
import argparse
import os

from camelot_rules import *
from camelot_utilities import *

# ------------------ Scoring ------------------ #

MIX_SCORES = {
    "perfect mix": 5.0,
    "+1 mix": 4.0,
    "-1 mix": 4.0,
    "energy boost": 3.0,
    "scale change": 3.0,
    "diagonal mix": 2.0,
    "mood shifter": 2.0,
    "jaws mix": 1.0,
    "non-harmonic": 0.0,
    "unknown": 0.0,
}

def transition_score(song_a, song_b, weight_bpm=0.15):
    """
    Compute a global score for transition A → B.
    - Strong weight for harmonic rule.
    - Small penalty for big BPM jumps.
    weight_bpm: higher = more BPM smoothing, lower = more harmonic-focused.
    """
    key_a = song_a.get("key")
    key_b = song_b.get("key")
    bpm_a = song_a.get("bpm")
    bpm_b = song_b.get("bpm")

    mix_type = classify_mix_type(key_a, key_b)
    base = MIX_SCORES.get(mix_type, 0.0) * 10.0  # Amplify harmonic score

    if bpm_a is None or bpm_b is None:
        bpm_penalty = 0.0
    else:
        bpm_diff = abs(bpm_b - bpm_a)
        bpm_penalty = bpm_diff * weight_bpm

    score = base - bpm_penalty
    return score, mix_type

def build_harmonic_path(songs):
    """
    Build a "good enough" harmonic-first path using a greedy strategy:
    - Start from the lowest BPM song.
    - At each step, among remaining songs, choose the best-scoring transition.
    """
    if not songs:
        return []

    # Sort songs by BPM initially (for choosing a starting point)
    songs_sorted = sorted(
        songs,
        key=lambda s: (float("inf") if s.get("bpm") is None else s["bpm"])
    )

    # Index-based operations
    remaining_indices = list(range(len(songs_sorted)))
    path_indices = []

    # Start from the lowest BPM with valid key
    start_idx = None
    for idx in remaining_indices:
        if songs_sorted[idx].get("key"):
            start_idx = idx
            break
    if start_idx is None:
        # no song with key → just return the BPM-sorted order
        return songs_sorted

    path_indices.append(start_idx)
    remaining_indices.remove(start_idx)

    # Greedy extension of the path
    while remaining_indices:
        current_idx = path_indices[-1]
        current_song = songs_sorted[current_idx]

        best_next_idx = None
        best_score = float("-inf")
        best_type = None

        for idx in remaining_indices:
            candidate = songs_sorted[idx]
            score, mix_type = transition_score(current_song, candidate)

            # Prefer higher score; in case of tie, prefer closer BPM
            if score > best_score:
                best_score = score
                best_next_idx = idx
                best_type = mix_type

        path_indices.append(best_next_idx)
        remaining_indices.remove(best_next_idx)

    # Rebuild ordered list
    ordered_songs = [songs_sorted[i] for i in path_indices]
    return ordered_songs


def make_clean_output(ordered_songs):
    """
    Final output: ONLY the reordered tracklist.
    No transition metadata, no next_song, nothing extra.
    """
    result = []

    for s in ordered_songs:
        result.append({
            "song": s.get("song"),
            "artist": s.get("artist"),
            "bpm": s.get("bpm"),
            "key": s.get("key")
        })

    return result

# ------------------ IO + CLI ------------------ #

def main():
    parser = argparse.ArgumentParser(
        description="Build a harmonic-first DJ mix from a JSON of songs (song, artist, bpm, key)"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Input JSON file with songs."
    )
    parser.add_argument(
        "--output",
        required=False,
        help="Output JSON for the mixed playlist (default: input name + '_mixed.json')."
    )

    args = parser.parse_args()

    input_path = args.input
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        songs = json.load(f)

    # Filter: keep only songs with a key and bpm
    usable = [s for s in songs if s.get("key") and s.get("bpm") is not None]
    missing = [s for s in songs if not s.get("key") or s.get("bpm") is None]

    print(f"Loaded {len(songs)} songs.")
    print(f"  → Using {len(usable)} songs with both BPM and key.")
    if missing:
        print(f"  → {len(missing)} songs skipped (missing BPM or key).")

    # Compute final harmonic-first ordering
    ordered = build_harmonic_path(usable)

    # Build clean output (no transitions)
    mixed_output = make_clean_output(ordered)

    # Default output name
    if args.output:
        output_path = args.output
    else:
        base, _ = os.path.splitext(os.path.basename(input_path))
        output_path = base + "_mixed.json"

    # Create directory if necessary
    out_dir = os.path.dirname(output_path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    # Save the CLEAN mix
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(mixed_output, f, indent=2, ensure_ascii=False)

    print(f"\n✨ Harmonic-first mix saved → {output_path}")
    print(f"Tracks included: {len(mixed_output)}")

if __name__ == "__main__":
    main()
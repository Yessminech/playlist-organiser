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

def transition_score(song_a, song_b, weight_bpm=0.40):
    """
    BPM-FIRST scoring:
    - BPM closeness is the PRIMARY factor.
    - Harmonic strength still helps choose the best match within similar BPM.
    """
    key_a = song_a.get("key")
    key_b = song_b.get("key")
    bpm_a = song_a.get("bpm")
    bpm_b = song_b.get("bpm")

    # Harmonic score
    mix_type = classify_mix_type(key_a, key_b)
    harmonic = MIX_SCORES.get(mix_type, 0.0)

    # BPM score: the closer the better (inverse penalty)
    if bpm_a is None or bpm_b is None:
        bpm_score = 0.0
    else:
        diff = abs(bpm_b - bpm_a)
        bpm_score = max(0.0, 10.0 - diff)  # stronger weight

    # Final score: BPM dominates + harmony refines
    score = bpm_score * weight_bpm + harmonic * (1 - weight_bpm)

    return score, mix_type


# ------------------ BPM-FIRST PATH BUILDER ------------------ #

def build_bpm_first_path(songs):
    """
    BPM-FIRST strategy:
    1. Sort globally by BPM ascending.
    2. Inside close BPM groups, order harmonically using greedy selection.
    """

    if not songs:
        return []

    # 1) Sort by BPM primary (None → end)
    songs_sorted = sorted(
        songs,
        key=lambda s: (float("inf") if s.get("bpm") is None else s["bpm"])
    )

    remaining = list(range(len(songs_sorted)))
    path = []

    # Start from the absolute lowest BPM song
    current_idx = remaining.pop(0)
    path.append(current_idx)

    # 2) Greedy harmonic refinement, but BPM is already dominant
    while remaining:
        best_idx = None
        best_score = float("-inf")

        curr_song = songs_sorted[path[-1]]

        for idx in remaining:
            candidate = songs_sorted[idx]
            score, mix_type = transition_score(curr_song, candidate)

            if score > best_score:
                best_score = score
                best_idx = idx

        path.append(best_idx)
        remaining.remove(best_idx)

    return [songs_sorted[i] for i in path]


# ------------------ CLEAN OUTPUT ------------------ #

def make_clean_output(ordered_songs):
    """
    Final output: ONLY the reordered tracklist.
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
        description="Build a BPM-first DJ mix from a JSON of songs (song, artist, bpm, key)"
    )
    parser.add_argument("--input", required=True, help="Input JSON file")
    parser.add_argument("--output", required=False, help="Output JSON")

    args = parser.parse_args()

    input_path = args.input
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        songs = json.load(f)

    # Filter: keep only songs with key + bpm
    usable = [s for s in songs if s.get("key") and s.get("bpm") is not None]
    missing = [s for s in songs if not s.get("key") or s.get("bpm") is None]

    print(f"Loaded {len(songs)} songs.")
    print(f"  → Using {len(usable)} songs with BPM + key.")
    if missing:
        print(f"  → {len(missing)} songs skipped.")

    # BPM-first ordering
    ordered = build_bpm_first_path(usable)

    # Clean output
    mixed_output = make_clean_output(ordered)

    # Output naming
    if args.output:
        output_path = args.output
    else:
        base, _ = os.path.splitext(os.path.basename(input_path))
        output_path = base + "_mixed_bpm_first.json"

    # Save
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(mixed_output, f, indent=2, ensure_ascii=False)

    print(f"\n✨ BPM-first mix saved → {output_path}")
    print(f"Tracks in mix: {len(mixed_output)}")


if __name__ == "__main__":
    main()

from camelot_utilities import *

def is_perfect_mix(k1, k2):
    return k1 == k2


def is_plus1_mix(k1, k2):
    n1, l1 = parse_camelot(k1)
    n2, l2 = parse_camelot(k2)
    return l1 == l2 and n2 == camelot_increment(n1, +1)


def is_minus1_mix(k1, k2):
    n1, l1 = parse_camelot(k1)
    n2, l2 = parse_camelot(k2)
    return l1 == l2 and n2 == camelot_increment(n1, -1)


def is_energy_boost(k1, k2):
    n1, l1 = parse_camelot(k1)
    n2, l2 = parse_camelot(k2)
    return l1 == l2 and n2 == camelot_increment(n1, +2)


def is_scale_change(k1, k2):
    # same number, different letter A↔B
    n1, l1 = parse_camelot(k1)
    n2, l2 = parse_camelot(k2)
    return n1 == n2 and l1 != l2


def is_diagonal_mix(k1, k2):
    """
    One step anticlockwise AND change scale A/B.
    Example: 9A → 8B, or 8B → 9A.
    """
    n1, l1 = parse_camelot(k1)
    n2, l2 = parse_camelot(k2)

    changed_scale = (l1 != l2)
    anticlockwise_step = (n2 == camelot_increment(n1, -1))

    return changed_scale and anticlockwise_step

def is_mood_shifter(k1, k2):
    """
    Mood Shifter:
    - Move 3 steps clockwise (perfect +3)
    - Change scale A<->B
    Example: 1B → 4A
    """
    n1, l1 = parse_camelot(k1)
    n2, l2 = parse_camelot(k2)

    clockwise_3 = (n2 == camelot_increment(n1, +3))
    scale_change = (l1 != l2)

    return clockwise_3 and scale_change


def is_jaws_mix(k1, k2):
    """
    Jaw's Mix:
    - Move 5 steps anticlockwise
    - Keep same scale (A->A, B->B)
    Example: 1A → 8A
    """
    n1, l1 = parse_camelot(k1)
    n2, l2 = parse_camelot(k2)

    anticlockwise_5 = (n2 == camelot_increment(n1, -5))
    same_scale = (l1 == l2)

    return anticlockwise_5 and same_scale

def classify_mix_type(k1, k2):
    """Return a string label for the mix type."""
    if k1 is None or k2 is None:
        return "unknown"

    if is_perfect_mix(k1, k2):
        return "perfect mix"

    if is_plus1_mix(k1, k2):
        return "+1 mix"

    if is_minus1_mix(k1, k2):
        return "-1 mix"

    if is_energy_boost(k1, k2):
        return "energy boost"

    if is_scale_change(k1, k2):
        return "scale change"

    if is_diagonal_mix(k1, k2):
        return "diagonal mix"

    if is_mood_shifter(k1, k2):
        return "mood shifter"

    if is_jaws_mix(k1, k2):
        return "jaws mix"

    return "non-harmonic"

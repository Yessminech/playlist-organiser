def parse_camelot(key):
    """
    Key is like '9A' or '11B'
    Returns (number, letter) with number as int.
    """
    num = int(key[:-1])
    letter = key[-1].upper()
    return num, letter


def camelot_increment(num, step):
    """
    Circular increment: numbers 1–12 wrap around.
    """
    return ((num - 1 + step) % 12) + 1

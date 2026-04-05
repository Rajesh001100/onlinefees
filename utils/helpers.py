# utils/helpers.py

def to_int(val, default=0):
    """
    Safely convert input to int.
    - Handles None
    - Handles empty string
    - Handles float strings
    - Never throws ValueError
    """
    try:
        if val is None:
            return default

        s = str(val).strip()
        if s == "":
            return default

        return int(float(s))
    except Exception:
        return default

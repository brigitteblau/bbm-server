import re
import unicodedata


def safe_filename_part(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip())
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", ascii_value.lower())
    cleaned = cleaned.strip("-_")
    return cleaned or "perro"

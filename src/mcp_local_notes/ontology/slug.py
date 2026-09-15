"""normalize(): mint a note's id/slug from a title, and compare titles and
aliases for uniqueness. One canonical function used for both -- see the
"Decide the id/slug generation rule and collision handling" decision.
"""

import re
import unicodedata


def normalize(text: str) -> str:
    """Lowercase, transliterate to ASCII, hyphenate, trim. No length cap."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")

import unicodedata
import re


# ---------------------------------------------------
# BASIC CLEANER (your original logic, improved)
# ---------------------------------------------------
def clean_name(name: str) -> str:
    if not isinstance(name, str):
        return ""

    # Remove accents
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))

    # Lowercase
    name = name.lower()

    # Remove apostrophes
    name = name.replace("’", "").replace("'", "")

    # Replace dash types with space
    name = re.sub(r"[‐-‒–—-]", " ", name)

    # Remove punctuation
    name = re.sub(r"[.,]", " ", name)

    # Keep only letters and spaces
    name = re.sub(r"[^a-z\s]", "", name)

    # Collapse spaces
    name = re.sub(r"\s+", " ", name).strip()

    return name


# ---------------------------------------------------
# MULTI-KEY GENERATOR (THE IMPORTANT PART)
# ---------------------------------------------------
def generate_name_keys(name: str) -> set:
    """
    Produce multiple identity fingerprints for a tennis player name.
    Handles:
    - initials
    - double surnames
    - reversed first/last order
    """

    cleaned = clean_name(name)

    if not cleaned:
        return set()

    parts = cleaned.split()

    keys = set()

    def build_keys(p):
        """Generate keys assuming first name first"""
        local_keys = set()

        # full name
        local_keys.add("".join(p))

        if len(p) == 1:
            local_keys.add(p[0])
            return local_keys

        first = p[0]
        first_initial = first[0]

        surname_full = "".join(p[1:])
        surname_last = p[-1]

        # surname + first initial
        local_keys.add(surname_last + first_initial)

        # compound surname + first initial
        local_keys.add(surname_full + first_initial)

        # initial + surname
        local_keys.add(first_initial + surname_last)

        # initials + surname
        initials = "".join(x[0] for x in p[:-1])
        local_keys.add(initials + surname_last)

        # surname only
        local_keys.add(surname_last)

        # compound surname only
        local_keys.add(surname_full)

        return local_keys

    # Normal order
    keys |= build_keys(parts)

    # Reversed order (important for Asian names)
    if len(parts) == 2:
        keys |= build_keys(parts[::-1])

    return keys
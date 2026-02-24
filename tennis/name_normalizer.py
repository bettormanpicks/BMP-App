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
    This allows matching:
    Etcheverry T.
    T. Etcheverry
    Tomas Martin Etcheverry
    Etcheverry T. M.
    Martinez Portero P.
    Portero P.
    """

    cleaned = clean_name(name)

    if not cleaned:
        return set()

    parts = cleaned.split()

    keys = set()

    # -------- Full name --------
    keys.add("".join(parts))

    # -------- Single word (rare but safe) --------
    if len(parts) == 1:
        keys.add(parts[0])
        return keys

    # -------- Assume first name first --------
    first = parts[0]
    first_initial = first[0]

    # possible surnames
    surname_full = "".join(parts[1:])
    surname_last = parts[-1]

    # 1) surname + first initial  (Etcheverry T.)
    keys.add(surname_last + first_initial)

    # 2) full surname + first initial (MartinezPortero P.)
    keys.add(surname_full + first_initial)

    # 3) initial + surname (T Etcheverry)
    keys.add(first_initial + surname_last)

    # 4) initials + surname (T M Etcheverry)
    initials = "".join(p[0] for p in parts[:-1])
    keys.add(initials + surname_last)

    # 5) surname only (betting feeds sometimes)
    keys.add(surname_last)

    # 6) full surname only (double surname protection)
    keys.add(surname_full)

    return keys
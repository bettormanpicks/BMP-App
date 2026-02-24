import unicodedata
import re

def normalize_name(name: str) -> str:
    if not isinstance(name, str):
        return ""

    name = name.strip().lower()

    # remove accents (Carreño -> Carreno)
    name = unicodedata.normalize('NFKD', name)
    name = name.encode('ascii', 'ignore').decode('ascii')

    # remove punctuation
    name = re.sub(r"[^\w\s-]", "", name)

    # collapse spaces
    name = re.sub(r"\s+", " ", name)

    return name
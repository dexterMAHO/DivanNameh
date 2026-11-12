import unicodedata

from django.db.models import TextField, Value
from django.db.models.functions import Replace


REPLACEMENTS = (('ي', 'ی'), ('ى', 'ی'), ('ك', 'ک'), ('\u200c', ''), ('\u200d', ''), (' ', ''))


def search_text(value, *, limit=120):
    value = unicodedata.normalize('NFKC', value).strip()[:limit]
    for original, replacement in REPLACEMENTS:
        value = value.replace(original, replacement)
    return value


def search_field(field):
    for original, replacement in REPLACEMENTS:
        field = Replace(field, Value(original), Value(replacement), output_field=TextField())
    return field

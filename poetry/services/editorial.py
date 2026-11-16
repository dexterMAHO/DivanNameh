import re
import unicodedata

from django.utils.html import format_html, format_html_join

from poetry.models import TreasuryPick


def public_picks():
    return TreasuryPick.objects.filter(
        published=True, entry__kind='work', entry__book__publishes_text=True, entry__has_text=True,
    )


def verse_url(entry, position):
    return f'{entry.get_absolute_url()}#verse-{position}'


def quote_row(pick, position):
    rows = pick.entry.couplets or []
    return rows[position - 1] if 0 < position <= len(rows) else None


LETTER_VARIANTS = str.maketrans('يىك', 'ییک')


def indexed_text(text):
    chars, positions = [], []
    for index, character in enumerate(text):
        for folded in unicodedata.normalize('NFKD', character).casefold().translate(LETTER_VARIANTS):
            if folded.isalnum():
                chars.append(folded)
                positions.append(index)
    return ''.join(chars), positions


def query_terms(query):
    return [normalized for word in query.split() if (normalized := indexed_text(word)[0])]


def match_rank(text, words):
    if not words:
        return 0
    normalized, _ = indexed_text(text)
    phrase = ''.join(words)
    if normalized == phrase:
        return 3
    if phrase in normalized:
        return 2
    end = 0
    for word in words:
        start = normalized.find(word, end)
        if start < 0:
            return 0
        end = start + len(word)
    return 1


def highlight(text, words):
    normalized, positions = indexed_text(text)
    if not words or not positions:
        return text
    offsets = set()
    for word in words:
        for match in re.finditer(re.escape(word), normalized):
            offsets.update(range(positions[match.start()], positions[match.end() - 1] + 1))
    # Keep combining marks attached to the letter they belong to.
    parts = []
    for index, char in enumerate(text):
        marked = index in offsets or (
            bool(parts) and parts[-1][0] and unicodedata.category(char).startswith('M')
        )
        if not parts or parts[-1][0] != marked:
            parts.append((marked, []))
        parts[-1][1].append(char)
    return format_html_join('', '{}', [
        (format_html('<mark>{}</mark>', ''.join(part)) if marked else ''.join(part),)
        for marked, part in parts
    ])

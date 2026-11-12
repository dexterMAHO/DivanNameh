import unicodedata

from .search import search_text

ALPHABET = tuple('آابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی')
PERSIAN_LETTERS = str.maketrans('يكأإىؤئةۀ', 'یکاایویهه')
HEMISTICH_LIMIT = 90


def normalized_paragraphs(paragraphs):
    return '\n'.join(search_text(line, limit=None) for paragraph in paragraphs or [] for line in paragraph.splitlines())


def couplet_count(paragraphs):
    if not paragraphs or len(paragraphs) < 2 or len(paragraphs) % 2 or any(len(line) > HEMISTICH_LIMIT for line in paragraphs):
        return 0
    return len(paragraphs) // 2


def opening_ending(paragraphs):
    ending = unicodedata.normalize('NFKC', paragraphs[1]).translate(PERSIAN_LETTERS)
    return next((char for char in reversed(ending) if char in ALPHABET), '')


def metadata(paragraphs, *, line_layout=False):
    paired = 0 if line_layout else couplet_count(paragraphs)
    count = sum(bool(line.strip()) for paragraph in paragraphs or [] for line in paragraph.splitlines()) if line_layout else paired
    return {
        'search_body': normalized_paragraphs(paragraphs),
        'opening_ending': opening_ending(paragraphs) if paired else '',
        'reading_count': count,
        'has_text': bool(paragraphs),
    }

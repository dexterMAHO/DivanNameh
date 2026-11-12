"""Reading forms identified from the imported Ganjoor editions."""

import re
import unicodedata


# These collections preserve line order in the source rather than marking
# paired hemistichs. Earlier collections by mixed-form poets stay separate.
LINE_COLLECTIONS = {
    'ahmd-shamlv': frozenset(f'cat{number}' for number in range(5052, 5068)),
    'frvgh-frkhzad': {'cat5154', 'cat5155'},
    'mhdi-akhvan-sals': {'cat5252', 'cat5253'},
    'fridvn-mshiri': frozenset(f'cat{number}' for number in range(5602, 5616)),
}
NIMA_LINE_WORKS = {f'poem-{500000 + number}' for number in (3, *range(14, 55))}
LINE_SECTION = re.compile(r'شعر(?:های)? نو|نیمایی|(?:شعر(?:های)?|اشعار) (?:سپید|آزاد)|چهارپاره')
CLASSICAL_TITLE = re.compile(r'^(?:غزل|رباعی|مثنوی|قصیده|قطعه)(?:\s|[:‌]|$)')


def normalize_label(title):
    return unicodedata.normalize('NFKC', title).translate(
        str.maketrans('كي‌', 'کی ')
    )


def is_line_poem(slug, key, title, sections):
    if CLASSICAL_TITLE.match(normalize_label(title)):
        return False
    if slug == 'nima-ivshij':
        return key in NIMA_LINE_WORKS
    return (
        slug == 'shrab-sphri'
        or any(section_key in LINE_COLLECTIONS.get(slug, ())
               or LINE_SECTION.search(normalize_label(section_title))
               for section_key, section_title in sections)
    )

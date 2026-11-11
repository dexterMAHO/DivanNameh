"""Convert the Ganjoor EPUB catalogue to an UTF-8 JSON Lines gzip dataset."""

import argparse
import gzip
import hashlib
import json
import posixpath
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

INDEX_URL = 'https://epub.ganjoor.net/'
EPUB_ROOT = 'https://i.ganjoor.net/epub/'
GANJOOR_RIGHTS = 'https://ganjoor.net/faq?id=21'
# Ganjoor explicitly identifies these editions when describing works without
# a suspected copyright issue. Other editions require individual verification.
PUBLISHABLE_EDITIONS = {'hafez': GANJOOR_RIGHTS, 'saadi': GANJOOR_RIGHTS}
CATALOGUE_ROW = re.compile(r'<tr(?:\s[^>]*)?>(.*?)</tr>', re.I | re.S)
POEM_ANCHOR = re.compile(r'poem-\d+\Z')


class CatalogueRow(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_author = False
        self.author = []
        self.url = ''

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == 'td':
            self.in_author = attrs.get('class') == 'c2'
        if tag == 'a':
            url = attrs.get('href', '')
            if url.startswith(EPUB_ROOT) and re.fullmatch(r'[a-zA-Z0-9_-]+\.epub', url[len(EPUB_ROOT):]):
                self.url = url

    def handle_endtag(self, tag):
        if tag == 'td':
            self.in_author = False

    def handle_data(self, data):
        if self.in_author:
            self.author.append(data)


def catalogue(html):
    books = {}
    for match in CATALOGUE_ROW.finditer(html):
        row = CatalogueRow()
        row.feed(match[1])
        if row.url:
            slug = Path(urlsplit(row.url).path).stem
            books[slug] = {'slug': slug, 'author': ''.join(row.author).strip(), 'source_url': row.url}
    if not books or any(not book['author'] for book in books.values()):
        raise ValueError('Invalid or empty Ganjoor catalogue')
    return books


def source_url(value):
    target = urlsplit(value)
    if target.scheme in ('http', 'https') and target.netloc in ('ganjoor.net', 'www.ganjoor.net'):
        return target._replace(scheme='https').geturl()
    return ''


class WorkDocument(HTMLParser):
    def __init__(self, publish):
        super().__init__()
        self.publish = publish
        self.works = {}
        self.work = None
        self.anchor_title = None
        self.paragraph = None

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == 'a' and POEM_ANCHOR.fullmatch(attrs.get('id', '')):
            self.work = {'source_url': source_url(attrs.get('href', '')), 'title': '', 'paragraphs': []}
            self.works[attrs['id']] = self.work
            self.anchor_title = []
        if self.work and self.publish:
            if tag == 'p':
                self.paragraph = []
            elif tag == 'br' and self.paragraph is not None:
                self.paragraph.append('\n')

    def handle_endtag(self, tag):
        if tag == 'a' and self.anchor_title is not None:
            self.work['title'] = ''.join(self.anchor_title).strip()
            self.anchor_title = None
        if tag == 'p' and self.paragraph is not None:
            paragraph = ''.join(self.paragraph).strip()
            if paragraph:
                self.work['paragraphs'].append(paragraph)
            self.paragraph = None

    def handle_data(self, data):
        if self.anchor_title is not None:
            self.anchor_title.append(data)
        if self.paragraph is not None:
            self.paragraph.append(data)


def entry_key(reference, fragment):
    stem = Path(reference).stem
    if POEM_ANCHOR.fullmatch(fragment):
        return fragment
    if not fragment and re.fullmatch(r'cat\d+', stem):
        return stem
    return 'epub-' + hashlib.sha256(f'{reference}#{fragment}'.encode()).hexdigest()[:32]


def contents(path, publish):
    entries = []
    with ZipFile(path) as archive:
        ncx_path, = [name for name in archive.namelist() if name.endswith('.ncx')]
        ncx = ElementTree.fromstring(archive.read(ncx_path))
        nav = ncx.find('./{*}navMap')
        if nav is None:
            raise ValueError('No NCX navigation')
        documents = {}

        def visit(points, parent=None):
            for point in points:
                ref = urlsplit(point.find('./{*}content').attrib['src'])
                member = posixpath.normpath(posixpath.join(posixpath.dirname(ncx_path), unquote(ref.path)))
                fragment = unquote(ref.fragment)
                if Path(member).name in ('promo.xhtml', 'bio.xhtml', 'titlepage.xhtml'):
                    continue
                key = entry_key(member, fragment)
                label = (point.findtext('./{*}navLabel/{*}text') or '').strip()
                kind = 'work' if POEM_ANCHOR.fullmatch(fragment) else 'section'
                entry = {'key': key, 'parent': parent, 'title': label, 'kind': kind,
                         'position': len(entries), 'source_url': '', 'paragraphs': None}
                if kind == 'work':
                    if member not in documents:
                        doc = WorkDocument(publish)
                        doc.feed(archive.read(member).decode('utf-8-sig'))
                        documents[member] = doc.works
                    work = documents[member][fragment]
                    entry['source_url'] = work['source_url']
                    if publish:
                        entry['paragraphs'] = work['paragraphs']
                    else:
                        entry['title'] = work['title'] or label.split(' : ', 1)[0]
                if not entry['title']:
                    raise ValueError(f'Empty title at {member}#{fragment}')
                entries.append(entry)
                visit(point.findall('./{*}navPoint'), key)

        visit(nav.findall('./{*}navPoint'))
    if not entries or len({entry['key'] for entry in entries}) != len(entries):
        raise ValueError('Empty or duplicate navigation entries')
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('catalogue_html', type=Path)
    parser.add_argument('epub_directory', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--allow-incomplete', action='store_true', help='Keep catalogue records for unavailable EPUBs')
    args = parser.parse_args()
    books = catalogue(args.catalogue_html.read_text(encoding='utf-8'))
    counts = dict(books=0, contents=0, works=0, readable=0)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.partial')
    try:
        with gzip.open(temporary, 'wt', encoding='utf-8', newline='\n') as output:
            for slug, book in books.items():
                note = PUBLISHABLE_EDITIONS.get(slug, '')
                try:
                    entries = contents(args.epub_directory / f'{slug}.epub', bool(note))
                except (OSError, BadZipFile, ElementTree.ParseError, AttributeError, KeyError, ValueError) as error:
                    if not args.allow_incomplete:
                        raise ValueError(f'{slug}: {error}') from error
                    print(f'{slug}: {error}')
                    entries = None
                record = {**book, 'edition_note': note, 'entries': entries}
                output.write(json.dumps(record, ensure_ascii=False, separators=(',', ':')) + '\n')
                counts['books'] += 1
                if entries is not None:
                    counts['contents'] += 1
                    counts['works'] += sum(entry['kind'] == 'work' for entry in entries)
                    counts['readable'] += sum(bool(entry['paragraphs']) for entry in entries)
        temporary.replace(args.output)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps(counts))


if __name__ == '__main__':
    main()

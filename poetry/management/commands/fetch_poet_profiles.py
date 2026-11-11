"""Fill treasury poet profiles — life dates from Ganjoor, biography from Persian
Wikipedia, portrait from Wikimedia Commons with a Ganjoor fallback."""
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from PIL import Image, UnidentifiedImageError

from poetry.models import TreasuryBook

USER_AGENT = 'DivanNamehBot/1.0 (treasury poet profiles; https://ganjoor.net)'
GANJOOR_API = 'https://api.ganjoor.net/api/ganjoor'
GANJOOR_SITE = 'https://ganjoor.net'
WIKI_HOST = 'fa.wikipedia.org'
COMMONS_HOST = 'commons.wikimedia.org'
WIKIDATA_HOST = 'www.wikidata.org'
PORTRAIT_DIR = Path('img/poets')
PORTRAIT_BOX = (420, 560)
PAPER = (255, 252, 245)  # --color-surface, so flattened artwork keeps the paper ground
BIO_LIMIT = 420
BATCH = 15

# A Wikipedia title only counts as this poet when the summary names a literary or
# historical person; otherwise the name matched a place, a book or a dynasty.
PERSON_HINTS = (
    'شاعر', 'سراینده', 'سخن‌سرا', 'سخنور', 'نویسنده', 'ادیب', 'عارف', 'صوفی', 'حکیم',
    'فیلسوف', 'تاریخ‌نگار', 'مورخ', 'مترجم', 'ترانه‌سرا', 'متخلص', 'نقاش', 'خطاط',
    'فقیه', 'عالم', 'دانشمند', 'پزشک', 'منتقد', 'روزنامه‌نگار', 'نمایش‌نامه‌نویس',
)
# Signatures, seals and script samples are filed as page images but are not portraits.
NOT_A_PORTRAIT = ('signature', 'sig.', 'logo', 'calligraphy', 'امضا', 'نستعلیق', 'خط_')
SENTENCE_END = re.compile(r'(?<=[.!؟])\s+')
TAG = re.compile(r'<[^>]+>')
DOUBLED = re.compile(r'^(.{3,}?)\1$')
SPACES = re.compile(r'[ \t ]+')


def request_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': USER_AGENT}), timeout=60) as reply:
        return json.load(reply)


def request_bytes(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': USER_AGENT}), timeout=60) as reply:
        return reply.read()


def api(host, **params):
    query = urllib.parse.urlencode({**params, 'format': 'json', 'formatversion': 2})
    return request_json(f'https://{host}/w/api.php?{query}')


def lunar_century(*years):
    for year in years:
        if year and 0 < year < 1600:
            return (year - 1) // 100 + 1
    return None


def summarise(extract):
    """Keep the opening sentences of a Wikipedia summary, up to BIO_LIMIT characters."""
    text = SPACES.sub(' ', TAG.sub('', extract or '')).strip()
    if not text:
        return ''
    kept = []
    for sentence in SENTENCE_END.split(text.replace('\n', ' ')):
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = ' '.join(kept + [sentence])
        if kept and len(candidate) > BIO_LIMIT:
            break
        kept.append(sentence)
        if len(kept) == 3:
            break
    summary = ' '.join(kept)
    return summary if len(summary) <= BIO_LIMIT + 120 else summary[:BIO_LIMIT].rstrip() + '…'


def clean_metadata(value):
    """Commons credit fields arrive as HTML, sometimes with the name repeated twice."""
    text = SPACES.sub(' ', TAG.sub('', value)).strip()
    doubled = DOUBLED.match(text)
    return doubled.group(1) if doubled else text


def describes_person(extract):
    return any(hint in extract for hint in PERSON_HINTS)


def candidate_titles(book, poet):
    """Ganjoor's full name disambiguates short pen names such as «نظامی» or «حافظ»."""
    names = [(poet.get('name') or '').strip(), book.author.strip()]
    return list(dict.fromkeys(name for name in names if name))


class Command(BaseCommand):
    help = 'Fetch biographies and portraits for the treasury poets.'

    def add_arguments(self, parser):
        parser.add_argument('--only', nargs='+', metavar='SLUG', help='Limit the run to these book slugs.')
        parser.add_argument('--limit', type=int, help='Stop after this many books.')
        parser.add_argument('--refresh', action='store_true', help='Replace profiles that are already filled.')
        parser.add_argument('--delay', type=float, default=0.3, help='Seconds to pause between remote calls.')

    def handle(self, *args, **options):
        self.delay = options['delay']
        self.static_root = Path(settings.STATICFILES_DIRS[0])
        (self.static_root / PORTRAIT_DIR).mkdir(parents=True, exist_ok=True)

        books = TreasuryBook.objects.all()
        if options['only']:
            books = books.filter(slug__in=options['only'])
        if not options['refresh']:
            books = books.filter(biography='', portrait='')
        books = list(books[:options['limit']] if options['limit'] else books)
        if not books:
            self.stdout.write('No books to update.')
            return

        try:
            ganjoor = self.ganjoor_poets()
        except (OSError, ValueError) as error:
            raise CommandError(f'Ganjoor poet list unavailable: {error}') from error

        filled = {'biography': 0, 'portrait': 0, 'dates': 0}
        for start in range(0, len(books), BATCH):
            chunk = books[start:start + BATCH]
            try:
                summaries = self.wikipedia_summaries(chunk, ganjoor)
            except (OSError, ValueError) as error:
                self.stderr.write(f'Wikipedia batch {start // BATCH + 1} failed: {error}')
                summaries = {}
            for book in chunk:
                poet = ganjoor.get(book.slug, {})
                pages = [summaries[title] for title in candidate_titles(book, poet) if title in summaries]
                self.update_book(book, poet, pages, filled)
            self.stdout.write(f'Processed {min(start + BATCH, len(books))} of {len(books)} books')
        self.stdout.write(self.style.SUCCESS(
            f"Filled {filled['biography']} biographies, {filled['portrait']} portraits, {filled['dates']} life dates."
        ))

    def ganjoor_poets(self):
        poets = {}
        for poet in request_json(f'{GANJOOR_API}/poets'):
            slug = (poet.get('fullUrl') or '').strip('/')
            if slug:
                poets[slug] = poet
        return poets

    def wikipedia_summaries(self, books, ganjoor):
        titles = {title for book in books for title in candidate_titles(book, ganjoor.get(book.slug, {}))}
        payload = api(
            WIKI_HOST, action='query', prop='extracts|pageimages|pageprops', exintro=1, explaintext=1,
            piprop='thumbnail|name', pithumbsize=PORTRAIT_BOX[1], ppprop='disambiguation|wikibase_item', redirects=1,
            titles='|'.join(titles),
        )
        query = payload.get('query', {})
        # A redirect or normalisation means the answer is filed under a different title.
        aliases = {}
        for mapping in query.get('normalized', []) + query.get('redirects', []):
            aliases.setdefault(mapping['to'], []).append(mapping['from'])
        summaries = {}
        for page in query.get('pages', []):
            if page.get('missing') or 'disambiguation' in (page.get('pageprops') or {}):
                continue
            for name in [page['title']] + aliases.get(page['title'], []):
                summaries[name] = page
        time.sleep(self.delay)
        self.attach_wikidata_portraits(summaries.values())
        return summaries

    def attach_wikidata_portraits(self, pages):
        """Wikidata's image property (P18) is the article's canonical portrait."""
        entities = {(page.get('pageprops') or {}).get('wikibase_item') for page in pages}
        entities.discard(None)
        if not entities:
            return
        try:
            payload = api(WIKIDATA_HOST, action='wbgetentities', ids='|'.join(sorted(entities)), props='claims')
            time.sleep(self.delay)
        except (OSError, ValueError) as error:
            self.stderr.write(f'Wikidata lookup failed: {error}')
            return
        images = {}
        for entity, data in (payload.get('entities') or {}).items():
            for claim in (data.get('claims') or {}).get('P18', []):
                value = (claim.get('mainsnak') or {}).get('datavalue', {}).get('value')
                if isinstance(value, str):
                    images[entity] = value
                    break
        for page in pages:
            image = images.get((page.get('pageprops') or {}).get('wikibase_item'))
            if image:
                page['portrait_file'] = image

    def update_book(self, book, poet, pages, filled):
        fields = {}
        article = next((page for page in pages if describes_person(page.get('extract') or '')), None)
        if article:
            summary = summarise(article.get('extract'))
            if summary:
                fields['biography'] = summary
                fields['biography_source'] = 'https://{}/wiki/{}'.format(
                    WIKI_HOST, urllib.parse.quote(article['title'].replace(' ', '_')))
        for field, key in (('birth_year', 'birthYearInLHijri'), ('death_year', 'deathYearInLHijri')):
            value = poet.get(key)
            fields[field] = value if isinstance(value, int) and 0 < value < 1600 else None
        for field, key in (('birth_place', 'birthPlace'), ('death_place', 'deathPlace')):
            fields[field] = (poet.get(key) or '').strip()[:120]
        fields['century'] = lunar_century(fields['death_year'], fields['birth_year'])

        portrait = self.store_portrait(book, poet, article or {})
        if portrait:
            fields.update(portrait)
        elif not book.portrait:
            fields.update(portrait='', portrait_width=None, portrait_height=None,
                          portrait_source='', portrait_credit='')

        for name, value in fields.items():
            setattr(book, name, value)
        book.save(update_fields=list(fields))
        filled['biography'] += bool(fields.get('biography'))
        filled['portrait'] += bool(fields.get('portrait'))
        filled['dates'] += bool(fields['birth_year'] or fields['death_year'])
        label = 'bio' if fields.get('biography') else '—'
        self.stdout.write(f"  {book.slug}: {label}, portrait {fields.get('portrait_credit') or 'none'}")

    def store_portrait(self, book, poet, page):
        """Prefer a Commons-licensed Wikipedia portrait, fall back to the Ganjoor thumbnail."""
        for loader in (lambda: self.commons_portrait(page), lambda: self.ganjoor_portrait(poet)):
            try:
                candidate = loader()
            except (OSError, ValueError, UnidentifiedImageError) as error:
                self.stderr.write(f'  {book.slug}: portrait failed — {error}')
                continue
            if not candidate:
                continue
            payload, credit, source = candidate
            try:
                saved = self.save_image(book.slug, payload)
            except (OSError, ValueError, UnidentifiedImageError) as error:
                self.stderr.write(f'  {book.slug}: portrait unreadable — {error}')
                continue
            return {**saved, 'portrait_credit': credit[:200], 'portrait_source': source}
        return None

    def commons_portrait(self, page):
        name = page.get('portrait_file') or page.get('pageimage')
        if not name or any(mark in name.lower() for mark in NOT_A_PORTRAIT):
            return None
        payload = api(COMMONS_HOST, action='query', prop='imageinfo', iiprop='extmetadata|url',
                      iiurlwidth=PORTRAIT_BOX[1], iiextmetadatafilter='LicenseShortName|Artist',
                      titles=f'File:{name}')
        time.sleep(self.delay)
        files = payload.get('query', {}).get('pages', [])
        # A file missing from Commons is a local fair-use upload; it is not ours to republish.
        if not files or files[0].get('missing') or not files[0].get('imageinfo'):
            return None
        info = files[0]['imageinfo'][0]
        metadata = info.get('extmetadata') or {}
        license_name = clean_metadata((metadata.get('LicenseShortName') or {}).get('value', ''))
        artist = clean_metadata((metadata.get('Artist') or {}).get('value', ''))
        credit = ' — '.join(part for part in ('ویکی‌مدیا کامنز', artist, license_name) if part)
        source = 'https://{}/wiki/{}'.format(COMMONS_HOST, urllib.parse.quote(files[0]['title'].replace(' ', '_')))
        # The rendered thumbnail keeps SVG and TIFF originals readable and the download small.
        payload = request_bytes(info.get('thumburl') or info['url'])
        time.sleep(self.delay)
        return payload, credit, source

    def ganjoor_portrait(self, poet):
        path = poet.get('imageUrl')
        if not path:
            return None
        payload = request_bytes(f"https://api.ganjoor.net{path}")
        time.sleep(self.delay)
        return payload, 'گنجور', f"{GANJOOR_SITE}{poet.get('fullUrl', '')}"

    def save_image(self, slug, payload):
        with Image.open(io.BytesIO(payload)) as image:
            source = image.convert('RGBA')
            # Transparent artwork is flattened onto the paper surface, never onto black.
            portrait = Image.new('RGB', source.size, PAPER)
            portrait.paste(source, mask=source.getchannel('A'))
            portrait.thumbnail(PORTRAIT_BOX, Image.LANCZOS)
            relative = PORTRAIT_DIR / f'{slug}.webp'
            portrait.save(self.static_root / relative, 'WEBP', quality=82, method=6)
            return {'portrait': relative.as_posix(),
                    'portrait_width': portrait.width, 'portrait_height': portrait.height}

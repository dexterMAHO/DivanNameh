"""Public discovery metadata and bounded, database-backed XML sitemaps."""
from django.core.paginator import Paginator, InvalidPage
from django.http import HttpResponse, Http404
from django.urls import reverse
from django.utils.html import escape
from poetry.models import TreasuryBook, TreasuryEntry

ORIGIN = 'https://divannameh.com'
PUBLIC = {'treasury', 'treasury-book', 'treasury-entry', 'guide', 'guide-lesson', 'explore'}


def metadata(request):
    route = request.resolver_match.url_name if request.resolver_match else ''
    canonical = ORIGIN + request.path
    page = request.GET.get('page', '')
    if page.isdigit() and int(page) > 1:
        canonical += '?page=' + str(int(page))
    return {'seo_canonical': canonical, 'seo_indexable': route in PUBLIC and not request.GET.get('q'),
            'seo_description': 'گنجینهٔ شعر فارسی در دیوان نامه؛ متن کامل اشعار شاعران فارسی‌زبان، مطالعه، کشف شعر و مرور محفوظات.'}


def robots(request):
    return HttpResponse('User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /settings/\nDisallow: /api/\nSitemap: '+ORIGIN+'/sitemap.xml\n', content_type='text/plain; charset=utf-8')


def sitemap(request, section=None):
    def xml(body, root):
        return HttpResponse('<?xml version="1.0" encoding="UTF-8"?>\n<'+root+' xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+body+'</'+root+'>', content_type='application/xml')
    if section is None:
        count = TreasuryEntry.objects.filter(book__publishes_text=True).count()
        locations = ['/sitemap/pages.xml', *[f'/sitemap/poems-{i}.xml' for i in range(1, max(1, (count+999)//1000)+1)]]
        return xml(''.join('<sitemap><loc>'+ORIGIN+loc+'</loc></sitemap>' for loc in locations), 'sitemapindex')
    if section == 'pages':
        paths = [reverse('treasury'), reverse('guide'), reverse('explore')]
        paths += [book.get_absolute_url() for book in TreasuryBook.objects.filter(publishes_text=True)]
    else:
        try:
            number = int(section.removeprefix('poems-'))
            if not section.startswith('poems-') or number < 1: raise ValueError
            page = Paginator(TreasuryEntry.objects.filter(book__publishes_text=True).select_related('book').defer('paragraphs', 'search_body').order_by('pk'), 1000).page(number)
            paths = [entry.get_absolute_url() for entry in page]
        except (ValueError, InvalidPage) as error:
            raise Http404 from error
    return xml(''.join('<url><loc>'+str(escape(ORIGIN+path))+'</loc></url>' for path in paths), 'urlset')

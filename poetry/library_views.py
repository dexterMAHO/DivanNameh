import json
from collections import Counter
from datetime import timedelta

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from accounts.models import User

from .http import private
from .models import LibraryImport, Tag
from .services.library_transfer import FORMAT, VERSION, apply_plan, build_plan, export_poems, export_row, validate_document


class ImportForm(forms.Form):
    file = forms.FileField(label='فایل JSON دیوان‌نامه', widget=forms.FileInput(attrs={'accept': '.json,application/json'}))


@private
@never_cache
@require_http_methods(['GET', 'POST'])
def library_transfer(request):
    action = request.POST.get('action', '')
    form = ImportForm(request.POST, request.FILES) if action == 'preview' else ImportForm()
    cutoff = timezone.now() - timedelta(minutes=30)
    pending = LibraryImport.objects.filter(owner=request.user)
    if action == 'preview' and form.is_valid():
        try:
            document = validate_document(form.cleaned_data['file'])
        except ValidationError as error:
            form.add_error('file', error)
        else:
            with transaction.atomic():
                User.objects.select_for_update().get(pk=request.user.pk)
                pending.update_or_create(owner=request.user, defaults={'payload': document})
            return redirect('library-transfer')
    if action in ('apply', 'discard'):
        try:
            with transaction.atomic():
                User.objects.select_for_update().get(pk=request.user.pk)
                staged = pending.select_for_update().filter(created_at__gte=cutoff).first()
                if staged and request.POST.get('revision') != staged.created_at.isoformat():
                    messages.info(request, 'پیش‌نمایش در برگهٔ دیگری تغییر کرده است. نسخهٔ تازه را بررسی کنید.')
                    return redirect('library-transfer')
                if staged and action == 'apply':
                    document = staged.payload
                    created = apply_plan(request.user, document['poems'], topics=document['topics'],
                                         include_variants=request.POST.get('include_variants') == 'yes')
                    messages.success(request, f'{created} شعر تازه وارد شد. موضوع‌ها و شاه‌بیت‌های نسخه‌های یکسان هم ادغام شدند.')
                pending.delete()
                if not staged and action == 'apply':
                    messages.info(request, 'پیش‌نمایش منقضی شده است. فایل را دوباره انتخاب کنید.')
        except (ValidationError, IntegrityError):
            messages.error(request, 'درون‌ریزی ذخیره نشد. پیش‌نمایش را بررسی کنید و دوباره تلاش کنید.')
        return redirect('library-transfer')
    pending.filter(created_at__lt=cutoff).delete()
    staged = pending.first()
    plan = build_plan(request.user, staged.payload['poems'])[1] if staged else []
    incoming_cards = sum(len(row.get('cards', [])) for _, row, _ in plan)
    counts = Counter(kind for _, _, kind in plan)
    return render(request, 'poetry/library_transfer.html', {'form': form, 'staged': staged, 'counts': counts,
                                                            'revision': staged.created_at.isoformat() if staged else '', 'incoming_cards': incoming_cards,
                                                            'variants': [row for _, row, kind in plan if kind == 'variant'][:20]})


@private
@never_cache
@require_GET
def library_export(request, extension):
    poems = export_poems(request.user, include_cards=extension == 'json')
    if extension == 'json':
        def rows():
            topics = list(Tag.objects.filter(owner=request.user).values_list('name', flat=True))
            yield json.dumps({'format': FORMAT, 'version': VERSION, 'topics': topics}, ensure_ascii=False)[:-1] + ',"poems":['
            for index, poem in enumerate(poems.iterator(chunk_size=20)):
                if index:
                    yield ','
                yield json.dumps(export_row(poem), ensure_ascii=False)
            yield ']}'
        response = StreamingHttpResponse(rows(), content_type='application/json; charset=utf-8')
    elif extension == 'md':
        def lines():
            yield '# کتابخانهٔ دیوان‌نامه\n'
            for poem in poems.iterator(chunk_size=20):
                yield f'\n## {poem.display_title}\n\n{poem.poet_name}\n\n'
                for verse in poem.verses.all():
                    yield '> ' + verse.hemistich_1.replace('\n', '\n> ') + '\n'
                    if verse.hemistich_2:
                        yield '> ' + verse.hemistich_2.replace('\n', '\n> ') + '\n'
                    yield '\n'
                if poem.notes:
                    yield f'{poem.notes}\n\n'
                if poem.source_url:
                    yield f'{poem.source_url}\n'
        response = StreamingHttpResponse(lines(), content_type='text/markdown; charset=utf-8')
    else:
        return HttpResponse(status=404)
    response['Content-Disposition'] = f'attachment; filename="divannameh-library.{extension}"'
    return response

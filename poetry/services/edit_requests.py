from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import QueryDict
from django.utils import timezone

from poetry.forms import PoemForm
from poetry.models import Poem, PoemEditRequest
from .poem_editor import save_poem


@transaction.atomic
def submit_edit(poem, owner, data, verses):
    current = Poem.objects.select_for_update().get(pk=poem.pk, owner=owner)
    if current.updated_at != poem.updated_at:
        raise ValidationError('شعر تغییر کرده است. صفحه را دوباره باز کنید.')
    payload = {name: data.get(name, '') for name in ('title', 'poet_name', 'source_url', 'notes', 'new_tag')}
    payload['tags'] = [tag.pk for tag in data['tags']]
    payload['verses'] = verses
    _, created = PoemEditRequest.objects.get_or_create(
        poem=current, status=PoemEditRequest.Status.PENDING,
        defaults={'payload': payload, 'poem_updated_at': current.updated_at},
    )
    if not created:
        raise ValidationError('این شعر یک درخواست ویرایش در انتظار بررسی دارد.')


@transaction.atomic
def decide_edit(edit, reviewer, *, approve):
    if not reviewer.is_active or not reviewer.is_superuser:
        raise ValidationError('فقط مدیر می‌تواند درخواست را بررسی کند.')
    poem = Poem.objects.select_for_update().get(pk=edit.poem_id)
    edit = PoemEditRequest.objects.select_for_update().get(pk=edit.pk)
    if edit.status != PoemEditRequest.Status.PENDING:
        raise ValidationError('این درخواست قبلاً بررسی شده است.')
    if approve:
        if poem.updated_at != edit.poem_updated_at:
            raise ValidationError('شعر پس از ارسال درخواست تغییر کرده است. درخواست را رد کنید تا کاربر دوباره آن را بفرستد.')
        payload = edit.payload
        data = QueryDict(mutable=True)
        data.update({name: payload[name] for name in ('title', 'poet_name', 'source_url', 'notes', 'new_tag')})
        data['input_mode'] = 'structured'
        data.setlist('tags', payload['tags'])
        data.setlist('hemistich_1', [verse[0] for verse in payload['verses']])
        data.setlist('hemistich_2', [verse[1] for verse in payload['verses']])
        form = PoemForm(data, owner=poem.owner, instance=poem)
        if not form.is_valid():
            raise ValidationError('اطلاعات درخواست دیگر معتبر نیست. موضوع‌ها و متن را بررسی کنید.')
        save_poem(poem.owner, form.cleaned_data, form.cleaned_data['verses'], poem)
    edit.status = PoemEditRequest.Status.APPROVED if approve else PoemEditRequest.Status.REJECTED
    edit.decided_at = timezone.now()
    edit.decided_by = reviewer
    edit.save(update_fields=['status', 'decided_at', 'decided_by'])

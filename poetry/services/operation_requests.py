from functools import wraps
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import Http404
from django.db import transaction
from django.http import QueryDict
from django.test.client import RequestFactory
from django.urls import resolve
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from poetry.http import success
from poetry.models import OperationRequest

# Replays are limited to explicit operations and always run as the original owner.
ROUTES = {'item-new', 'poem-archive', 'treasury-save', 'share-save'}


def operation_gate(label, *, conditional=False, review=False):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            applies = (not conditional or request.POST.get('action', request.GET.get('action')) == 'memorize') and not kwargs.get('restore', False)
            if request.method == 'POST' and applies and request.POST.get('operation_mode') == 'request' and not getattr(request, '_operation_approved', False):
                if review:
                    request._operation_approved = True
                else:
                    payload = {key: values for key, values in request.POST.lists()
                               if key not in ('csrfmiddlewaretoken', 'action_password', 'operation_mode')}
                    OperationRequest.objects.get_or_create(owner=request.user, path=request.path, payload=payload, status='pending', defaults={'label': label})
                    target = request.headers.get('Referer', '')
                    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                        target = '/poems/'
                    return success(request, 'درخواست برای بررسی مدیر ثبت شد؛ پس از تأیید اجرا می‌شود.', target, pending_approval=True)
            return view(request, *args, **kwargs)
        return wrapped
    return decorate


@transaction.atomic
def decide_operation(pk, reviewer, *, approve):
    if not reviewer.is_active or not reviewer.is_superuser:
        raise ValidationError('فقط مدیر می‌تواند تصمیم بگیرد.')
    operation = OperationRequest.objects.select_for_update().select_related('owner').get(pk=pk)
    if operation.status != 'pending':
        raise ValidationError('این درخواست قبلاً بررسی شده است.')
    if approve:
        match = resolve(operation.path)
        if match.url_name not in ROUTES or not operation.owner.is_active:
            raise ValidationError('عملیات دیگر قابل اجرا نیست.')
        data = QueryDict(mutable=True)
        for key, values in operation.payload.items():
            data.setlist(key, values)
        request = RequestFactory().post(operation.path)
        request.POST = data
        request.user = operation.owner
        request._operation_approved = True
        request.META['HTTP_ACCEPT'] = 'application/json'
        try:
            response = match.func(request, *match.args, **match.kwargs)
        except (Http404, PermissionDenied) as error:
            raise ValidationError('منبع درخواست دیگر در دسترس نیست.') from error
        if response.status_code >= 400:
            raise ValidationError('اطلاعات درخواست دیگر معتبر نیست؛ عملیات اجرا نشد.')
    operation.status = 'approved' if approve else 'rejected'
    operation.decided_at = timezone.now()
    operation.decided_by = reviewer
    operation.save(update_fields=['status', 'decided_at', 'decided_by'])

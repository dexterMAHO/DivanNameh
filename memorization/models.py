from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError

class MemorizationItem(models.Model):
    SCOPES = [('full', 'تمام شعر'), ('range', 'بازهٔ ابیات')]
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    poem = models.ForeignKey('poetry.Poem', on_delete=models.CASCADE, related_name='items')
    scope = models.CharField(max_length=5, choices=SCOPES)
    start_verse = models.ForeignKey('poetry.Verse', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    end_verse = models.ForeignKey('poetry.Verse', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    status = models.CharField(max_length=6, choices=[('active', 'فعال'), ('paused', 'متوقف')], default='active')
    due_at = models.DateTimeField(default=timezone.now)
    interval_days = models.PositiveIntegerField(default=0)
    review_count = models.PositiveIntegerField(default=0)
    streak = models.PositiveIntegerField(default=0)
    lapses = models.PositiveIntegerField(default=0)
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_at', 'pk']
        indexes = [models.Index(fields=['owner', 'due_at'])]
        constraints = [
            models.UniqueConstraint(fields=['owner', 'poem'], condition=models.Q(scope='full'), name='unique_full_item'),
            models.UniqueConstraint(fields=['owner', 'start_verse', 'end_verse'], condition=models.Q(scope='range'), name='unique_range_item'),
            models.CheckConstraint(condition=(models.Q(scope='full', start_verse__isnull=True, end_verse__isnull=True) |
                                               models.Q(scope='range', start_verse__isnull=False, end_verse__isnull=False)), name='valid_item_scope')]

    def clean(self):
        if self.poem.owner_id != self.owner_id:
            raise ValidationError('شعر متعلق به شما نیست.')
        if self.scope == 'full' and (self.start_verse_id or self.end_verse_id):
            raise ValidationError('کارت کامل نباید مرز بازه داشته باشد.')
        if self.scope == 'range':
            if not self.start_verse_id or not self.end_verse_id:
                raise ValidationError('ابتدا و انتهای بازه را انتخاب کنید.')
            if (self.start_verse.poem_id != self.poem_id or self.end_verse.poem_id != self.poem_id or
                    self.start_verse.position > self.end_verse.position):
                raise ValidationError('بازهٔ انتخاب‌شده معتبر نیست.')

    @property
    def scope_label(self):
        if self.scope == 'full':
            return 'تمام شعر'
        unit = 'سطر' if self.poem.line_layout else 'بیت'
        return f'{unit} {self.start_verse.position} تا {self.end_verse.position}'

class ReviewLog(models.Model):
    RATINGS = [('again', 'دوباره؛ یادم نبود'), ('hard', 'سخت؛ با زحمت'), ('good', 'خوب؛ درست یادم آمد'), ('easy', 'آسان؛ کاملاً یادم بود')]
    item = models.ForeignKey(MemorizationItem, on_delete=models.CASCADE, related_name='logs')
    request_id = models.UUIDField(unique=True)
    transfer_id = models.UUIDField(null=True, blank=True, editable=False)
    rating = models.CharField(max_length=5, choices=RATINGS)
    reviewed_at = models.DateTimeField(default=timezone.now)
    previous_due_at = models.DateTimeField()
    next_due_at = models.DateTimeField()
    previous_interval_days = models.PositiveIntegerField()
    next_interval_days = models.PositiveIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['item', 'transfer_id'], name='unique_review_transfer')]

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.urls import reverse

class Tag(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=60)
    normalized_name = models.CharField(max_length=60)
    slug = models.CharField(max_length=90)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        constraints = [models.UniqueConstraint(fields=['owner', 'normalized_name'], name='unique_tag_name'),
                       models.UniqueConstraint(fields=['owner', 'slug'], name='unique_tag_slug')]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('tag-detail', args=[self.slug])

class Poem(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField('عنوان', max_length=200, blank=True)
    poet_name = models.CharField('شاعر', max_length=160)
    source_url = models.URLField('نشانی منبع', max_length=500, blank=True)
    notes = models.TextField('یادداشت', blank=True)
    line_layout = models.BooleanField(default=False)
    treasury_selection = models.CharField(max_length=64, null=True, editable=False)
    tags = models.ManyToManyField(Tag, blank=True, related_name='poems', verbose_name='موضوع‌ها')
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-pk']
        constraints = [models.UniqueConstraint(
            fields=['owner', 'treasury_selection'], name='unique_treasury_selection',
        )]

    @property
    def display_title(self):
        verses = list(self.verses.all())
        return self.title or (verses[0].hemistich_1[:70] if verses else 'شعر بی‌عنوان')

    def __str__(self):
        return self.title or self.poet_name

    def get_absolute_url(self):
        return reverse('poem-detail', args=[self.pk])

class Verse(models.Model):
    poem = models.ForeignKey(Poem, related_name='verses', on_delete=models.CASCADE)
    position = models.PositiveIntegerField()
    hemistich_1 = models.TextField(max_length=1000)
    hemistich_2 = models.TextField(max_length=1000, blank=True)

    class Meta:
        ordering = ['position', 'pk']
        constraints = [models.UniqueConstraint(fields=['poem', 'position'], name='unique_verse_position'),
                       models.CheckConstraint(condition=models.Q(position__gte=1), name='positive_position')]

class FavoriteVerse(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    verse = models.ForeignKey(Verse, on_delete=models.PROTECT, related_name='favorites')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['owner', 'verse'], name='unique_favorite')]
        indexes = [models.Index(fields=['owner', 'created_at'])]

    def clean(self):
        if self.verse.poem.owner_id != self.owner_id:
            raise ValidationError('این بیت متعلق به شما نیست.')


class PoemEditRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'در انتظار بررسی'
        APPROVED = 'approved', 'تأیید شده'
        REJECTED = 'rejected', 'رد شده'

    poem = models.ForeignKey(Poem, on_delete=models.CASCADE, related_name='edit_requests')
    payload = models.JSONField()
    original = models.JSONField(null=True, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='submitted_poem_edits',
    )
    poem_updated_at = models.DateTimeField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'درخواست ویرایش شعر'
        verbose_name_plural = 'درخواست‌های ویرایش شعر'
        constraints = [
            models.UniqueConstraint(fields=['poem'], condition=models.Q(status='pending'), name='one_pending_poem_edit'),
        ]

    def __str__(self):
        return str(self.poem)


HEMISTICH_LIMIT = 90  # Longer lines are prose, not a hemistich of a couplet.


class TreasuryBook(models.Model):
    slug = models.SlugField(max_length=120, unique=True)
    author = models.CharField(max_length=240)
    source_url = models.URLField(max_length=500)
    has_contents = models.BooleanField(default=False)
    publishes_text = models.BooleanField(default=False)
    edition_note = models.CharField(max_length=500, blank=True)
    dataset_digest = models.CharField(max_length=64)
    section_count = models.PositiveIntegerField(default=0)
    work_count = models.PositiveIntegerField(default=0)
    biography = models.TextField(blank=True)
    biography_source = models.URLField(max_length=500, blank=True)
    portrait = models.CharField(max_length=120, blank=True)
    portrait_width = models.PositiveSmallIntegerField(null=True, blank=True)
    portrait_height = models.PositiveSmallIntegerField(null=True, blank=True)
    portrait_source = models.URLField(max_length=500, blank=True)
    portrait_credit = models.CharField(max_length=200, blank=True)
    birth_year = models.SmallIntegerField(null=True, blank=True)
    death_year = models.SmallIntegerField(null=True, blank=True)
    birth_place = models.CharField(max_length=120, blank=True)
    death_place = models.CharField(max_length=120, blank=True)
    century = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ('author', 'slug')
        indexes = [models.Index(fields=['century', 'author'], name='treasury_century_order')]

    def __str__(self):
        return self.author

    def get_absolute_url(self):
        return reverse('treasury-book', args=[self.slug])

    @property
    def initial(self):
        return self.author.lstrip('\u200c ')[:1]

    @property
    def life_span(self):
        """Lunar hijri birth–death years as a single Persian label."""
        if self.birth_year and self.death_year:
            return f'{self.birth_year} – {self.death_year} ق'
        if self.death_year:
            return f'درگذشتهٔ {self.death_year} ق'
        if self.birth_year:
            return f'زادهٔ {self.birth_year} ق'
        return ''

    @property
    def ganjoor_url(self):
        return f'https://ganjoor.net/{self.slug}/'


class TreasuryEntry(models.Model):
    book = models.ForeignKey(TreasuryBook, on_delete=models.CASCADE, related_name='entries')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, related_name='children')
    key = models.SlugField(max_length=80)
    title = models.TextField()
    position = models.PositiveIntegerField()
    kind = models.CharField(max_length=8, choices=[('section', 'بخش'), ('work', 'اثر')])
    source_url = models.URLField(max_length=500, blank=True)
    paragraphs = models.JSONField(null=True)

    class Meta:
        ordering = ('position',)
        constraints = [
            models.UniqueConstraint(fields=['book', 'key'], name='treasury_entry_unique_key'),
        ]
        indexes = [models.Index(fields=['book', 'parent', 'position'], name='treasury_browse_order')]

    def get_absolute_url(self):
        return reverse('treasury-entry', args=[self.book.slug, self.key])

    @property
    def couplets(self):
        """Pair the stored hemistichs into verses; prose pages stay as paragraphs."""
        lines = self.paragraphs or []
        if len(lines) < 2 or len(lines) % 2 or any(len(line) > HEMISTICH_LIMIT for line in lines):
            return None
        return list(zip(lines[::2], lines[1::2]))

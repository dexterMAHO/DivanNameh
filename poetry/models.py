import uuid

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.urls import reverse

from .services.treasury_metadata import couplet_count, metadata
from .treasury_forms import is_line_poem

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
    treasury_book_slug = models.SlugField(max_length=120, blank=True)
    treasury_entry_key = models.SlugField(max_length=80, blank=True)
    treasury_positions = models.JSONField(default=list, blank=True)
    treasury_edition = models.CharField(max_length=64, blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name='poems', verbose_name='موضوع‌ها')
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-pk']
        indexes = [models.Index(fields=['owner', 'treasury_book_slug', 'treasury_entry_key'], name='poem_treasury_origin')]
        constraints = [models.UniqueConstraint(
            fields=['owner', 'treasury_selection'], name='unique_treasury_selection',
        )]

    @property
    def display_title(self):
        if self.title:
            return self.title
        verse = next(iter(self.verses.all()), None)
        return verse.hemistich_1[:70] if verse else 'شعر بی‌عنوان'

    @property
    def excerpt_verse(self):
        verses = self.verses.all()
        match_id = getattr(self, 'match_id', None)
        if match_id:
            return next((verse for verse in verses if verse.pk == match_id), None)
        return next(iter(verses), None)

    def __str__(self):
        return self.title or self.poet_name

    def get_absolute_url(self):
        return reverse('poem-detail', args=[self.pk])

class Verse(models.Model):
    poem = models.ForeignKey(Poem, related_name='verses', on_delete=models.CASCADE)
    position = models.PositiveIntegerField()
    treasury_position = models.PositiveIntegerField(null=True, blank=True, editable=False)
    hemistich_1 = models.TextField(max_length=1000)
    hemistich_2 = models.TextField(max_length=1000, blank=True)

    class Meta:
        ordering = ['position', 'pk']
        constraints = [models.UniqueConstraint(fields=['poem', 'position'], name='unique_verse_position'),
                       models.CheckConstraint(condition=models.Q(position__gte=1), name='positive_position'),
                       models.UniqueConstraint(fields=['poem', 'treasury_position'], name='unique_verse_treasury_position')]

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
    rejection_reason = models.CharField(max_length=500, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'درخواست ویرایش شعر'
        verbose_name_plural = 'درخواست‌های ویرایش شعر'
        constraints = [
            models.UniqueConstraint(fields=['poem'], condition=models.Q(status='pending'), name='one_pending_poem_edit'),
        ]

    def __str__(self):
        return str(self.poem)


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


class TreasuryEntryQuerySet(models.QuerySet):
    def bulk_create(self, objs, **kwargs):
        objs = list(objs)
        for obj in objs:
            obj.update_reading_metadata()
        return super().bulk_create(objs, **kwargs)


class TreasuryEntry(models.Model):
    objects = TreasuryEntryQuerySet.as_manager()
    book = models.ForeignKey(TreasuryBook, on_delete=models.CASCADE, related_name='entries')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, related_name='children')
    key = models.SlugField(max_length=80)
    title = models.TextField()
    position = models.PositiveIntegerField()
    kind = models.CharField(max_length=8, choices=[('section', 'بخش'), ('work', 'اثر')])
    source_url = models.URLField(max_length=500, blank=True)
    paragraphs = models.JSONField(null=True)
    search_body = models.TextField(blank=True, default='')
    opening_ending = models.CharField(max_length=1, blank=True, default='')
    has_text = models.BooleanField(default=False)
    reading_count = models.PositiveIntegerField(default=0)

    def update_reading_metadata(self):
        line_layout = getattr(self, '_reading_layout', None)
        if line_layout is None and self.paragraphs:
            sections = []
            parent = self.parent
            while parent:
                sections.append((parent.key, parent.title))
                parent = parent.parent
            line_layout = is_line_poem(self.book.slug, self.key, self.title, sections)
        fields = metadata(self.paragraphs, line_layout=bool(line_layout))
        for key, value in fields.items():
            setattr(self, key, value)
        return fields.keys()

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if (update_fields is None and 'paragraphs' not in self.get_deferred_fields()) or (update_fields and 'paragraphs' in update_fields):
            fields = self.update_reading_metadata()
            if update_fields is not None:
                kwargs['update_fields'] = set(update_fields) | fields
        return super().save(*args, **kwargs)

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
        if not couplet_count(lines):
            return None
        return list(zip(lines[::2], lines[1::2]))


class Collection(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='collections')
    name = models.CharField(max_length=100)
    normalized_name = models.CharField(max_length=100, editable=False)

    class Meta:
        ordering = ('name', 'pk')
        constraints = [models.UniqueConstraint(fields=['owner', 'normalized_name'], name='unique_collection_name')]

    def get_absolute_url(self):
        return reverse('collection-detail', args=[self.pk])


class CollectionItem(models.Model):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name='items')
    poem = models.ForeignKey(Poem, on_delete=models.CASCADE, null=True, blank=True)
    favorite = models.ForeignKey(FavoriteVerse, on_delete=models.CASCADE, null=True, blank=True)
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ('position', 'pk')
        constraints = [
            models.CheckConstraint(condition=models.Q(poem__isnull=False, favorite__isnull=True) |
                                   models.Q(poem__isnull=True, favorite__isnull=False), name='collection_item_one_target'),
            models.UniqueConstraint(fields=['collection', 'poem'], name='unique_collection_poem'),
            models.UniqueConstraint(fields=['collection', 'favorite'], name='unique_collection_favorite'),
            models.UniqueConstraint(fields=['collection', 'position'], name='unique_collection_position'),
        ]


class LibraryImport(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pending_library_import')
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now=True)


class TreasuryTopic(models.Model):
    slug = models.SlugField(unique=True, allow_unicode=True)
    title = models.CharField('عنوان', max_length=100)

    class Meta:
        ordering = ('title',)
        verbose_name_plural = 'موضوع‌های گنجینه'

    def __str__(self):
        return self.title


class TreasuryPick(models.Model):
    entry = models.OneToOneField(TreasuryEntry, on_delete=models.CASCADE, related_name='editorial')
    topics = models.ManyToManyField(TreasuryTopic, blank=True)
    published = models.BooleanField('انتشار عمومی', default=False)
    featured = models.BooleanField('برگزیده', default=False)
    sample_position = models.PositiveIntegerField('بیت نمونه', default=1)

    class Meta:
        verbose_name_plural = 'شعرهای عمومی گنجینه'

    def clean(self):
        if self.entry_id and self.published:
            rows = self.entry.couplets or []
            if (self.entry.kind != 'work' or not self.entry.book.publishes_text or not rows
                    or not self.entry.source_url):
                raise ValidationError({'entry': 'برای انتشار، اثر باید متن کامل و نشانی منبع داشته باشد.'})
            if self.sample_position and self.sample_position > len(rows):
                raise ValidationError({'sample_position': 'شمارهٔ بیت در متن اثر وجود ندارد.'})
            if self.sample_position == 0:
                raise ValidationError({'sample_position': 'شمارهٔ بیت باید از یک شروع شود.'})

    def __str__(self):
        return str(self.entry)


class TreasurySet(models.Model):
    slug = models.SlugField(unique=True, allow_unicode=True)
    title = models.CharField('عنوان', max_length=120)
    description = models.TextField('معرفی', blank=True)
    published = models.BooleanField('انتشار عمومی', default=False)

    class Meta:
        ordering = ('title',)
        verbose_name_plural = 'مجموعه‌های ادبی گنجینه'

    def __str__(self):
        return self.title


class TreasurySetVerse(models.Model):
    collection = models.ForeignKey(TreasurySet, on_delete=models.CASCADE, related_name='quotes')
    pick = models.ForeignKey(TreasuryPick, on_delete=models.CASCADE, related_name='quotes')
    verse = models.PositiveIntegerField('شمارهٔ بیت')
    commentary = models.CharField('توضیح', max_length=320)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('order', 'pk')

    def clean(self):
        if self.pick_id and self.verse is not None and not 1 <= self.verse <= len(self.pick.entry.couplets or []):
            raise ValidationError({'verse': 'شمارهٔ بیت در متن اثر وجود ندارد.'})


class TreasuryVerseLink(models.Model):
    class Kind(models.TextChoices):
        IMAGE = 'image', 'تصویر مشترک'
        REFRAIN = 'refrain', 'ردیف مشترک'
        RESPONSE = 'response', 'استقبال'
        QUOTATION = 'quotation', 'تضمین'

    origin = models.ForeignKey(TreasuryPick, on_delete=models.CASCADE, related_name='outgoing_links')
    origin_verse = models.PositiveIntegerField('شمارهٔ بیت مبدأ')
    target = models.ForeignKey(TreasuryPick, on_delete=models.CASCADE, related_name='incoming_links')
    target_verse = models.PositiveIntegerField('شمارهٔ بیت مقصد')
    kind = models.CharField(max_length=10, choices=Kind.choices)
    explanation = models.CharField('دلیل ارتباط', max_length=320)
    source_url = models.URLField('منبع', max_length=500, blank=True)

    class Meta:
        verbose_name_plural = 'پیوندهای ادبی گنجینه'

    def clean(self):
        for field in ('origin', 'target'):
            position = getattr(self, f'{field}_verse')
            if getattr(self, f'{field}_id') and position is not None:
                if not 1 <= position <= len(getattr(self, field).entry.couplets or []):
                    raise ValidationError({f'{field}_verse': 'شمارهٔ بیت در متن اثر وجود ندارد.'})
        if self.kind in (self.Kind.RESPONSE, self.Kind.QUOTATION) and not self.source_url:
            raise ValidationError({'source_url': 'برای استقبال و تضمین، منبع لازم است.'})


class PoemShare(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='poem_shares')
    token = models.UUIDField(unique=True, editable=False, default=uuid.uuid4)
    snapshot = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at', '-pk')


class ExplorePost(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='explore_posts')
    title = models.CharField(max_length=200)
    poet_name = models.CharField(max_length=160)
    rows = models.JSONField()
    line_layout = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=[('pending', 'در انتظار تأیید'), ('published', 'منتشرشده'), ('rejected', 'ردشده')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']

    def get_absolute_url(self):
        return reverse('explore-post', args=[self.pk])


class ExploreLike(models.Model):
    post = models.ForeignKey(ExplorePost, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['post', 'user'], name='unique_explore_like')]


class ExploreSave(models.Model):
    post = models.ForeignKey(ExplorePost, on_delete=models.CASCADE, related_name='saves')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    poem = models.ForeignKey(Poem, null=True, on_delete=models.SET_NULL)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['post', 'user'], name='unique_explore_save')]


class ExploreView(models.Model):
    post = models.ForeignKey(ExplorePost, on_delete=models.CASCADE, related_name='views')
    visitor = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['post', 'visitor'], name='unique_explore_view')]


class OperationRequest(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    path = models.CharField(max_length=500)
    payload = models.JSONField(default=dict)
    label = models.CharField(max_length=120)
    status = models.CharField(max_length=12, default='pending', choices=[('pending', 'در انتظار'), ('approved', 'تأییدشده'), ('rejected', 'ردشده')])
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    def __str__(self):
        return f'{self.owner} · {self.label}'

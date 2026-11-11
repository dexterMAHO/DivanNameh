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
    tags = models.ManyToManyField(Tag, blank=True, related_name='poems', verbose_name='موضوع‌ها')
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-pk']

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

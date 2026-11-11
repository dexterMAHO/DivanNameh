import io
import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase
from django.db import IntegrityError
from poetry.models import Poem


class LibraryImportTests(TestCase):
    def fixture(self, rows):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / 'library.json'
        path.write_text(json.dumps(rows), encoding='utf-8')
        return path

    def test_requires_explicit_confirmation(self):
        with self.assertRaisesMessage(CommandError, '--confirm-empty-target'):
            call_command('import_library', 'unused.json')

    def test_refuses_nonempty_target(self):
        user = get_user_model().objects.create_user('existing')
        path = self.fixture([{'model': 'auth.group', 'pk': 1, 'fields': {'name': 'new', 'permissions': []}}])
        with self.assertRaisesMessage(CommandError, 'not empty'):
            call_command('import_library', path, confirm_empty_target=True)
        self.assertTrue(get_user_model().objects.filter(pk=user.pk).exists())

    def test_rejects_unrelated_models(self):
        path = self.fixture([{'model': 'sessions.session', 'pk': 'x', 'fields': {}}])
        with self.assertRaisesMessage(CommandError, 'unsupported'):
            call_command('import_library', path, confirm_empty_target=True)

    def test_empty_target_roundtrip_and_replay_rejected(self):
        path = self.fixture([{'model': 'auth.group', 'pk': 7, 'fields': {'name': 'fixture-test', 'permissions': []}}])
        call_command('import_library', path, confirm_empty_target=True, stdout=io.StringIO())
        from django.contrib.auth.models import Group
        self.assertTrue(Group.objects.filter(pk=7, name='fixture-test').exists())
        with self.assertRaisesMessage(CommandError, 'not empty'):
            call_command('import_library', path, confirm_empty_target=True)

    def test_invalid_reference_rolls_back_entire_import(self):
        path = self.fixture([
            {'model': 'auth.group', 'pk': 7, 'fields': {'name': 'rollback-test', 'permissions': []}},
            {'model': 'poetry.poem', 'pk': 1, 'fields': {'owner': 99999, 'title': 'fixture', 'poet_name': 'test',
             'source_url': '', 'notes': '', 'tags': [], 'archived_at': None,
             'created_at': '2026-01-01T00:00:00Z', 'updated_at': '2026-01-01T00:00:00Z'}},
        ])
        with self.assertRaises(IntegrityError):
            call_command('import_library', path, confirm_empty_target=True, stdout=io.StringIO())
        from django.contrib.auth.models import Group
        self.assertFalse(Group.objects.exists())
        self.assertFalse(Poem.objects.exists())

    def test_real_library_export_restores_users_relations_and_review_history(self):
        import uuid
        from django.contrib.auth.models import Group, Permission
        from django.db import transaction
        from poetry.models import FavoriteVerse, Tag
        from poetry.services.poem_editor import save_poem
        from poetry.services.tags import save_tag
        from memorization.models import MemorizationItem, ReviewLog
        from memorization.services.selections import create_item
        from memorization.services.reviews import rate_item

        output = io.StringIO()
        # Create a disposable source in a savepoint, export it, then roll it back.
        with transaction.atomic():
            user = get_user_model().objects.create_user('fixture-reader', password='fixture-only-password')
            group = Group.objects.create(name='fixture-group')
            group.permissions.add(Permission.objects.filter(codename='view_poem').get())
            user.groups.add(group)
            tag = save_tag(user, 'نمونه')
            poem = save_poem(user, dict(title='شعر آزمایشی', poet_name='آزمایشی', source_url='', notes='', tags=[tag]), [('یک', 'دو')])
            verse = poem.verses.first()
            FavoriteVerse.objects.create(owner=user, verse=verse)
            item = create_item(user, poem, 'range', verse, verse)
            rate_item(user, item.pk, 'good', uuid.uuid4())
            call_command('dumpdata', 'accounts', 'auth.group', 'poetry', 'memorization', natural_foreign=True, stdout=output)
            transaction.set_rollback(True)
        path = self.fixture(json.loads(output.getvalue()))
        call_command('import_library', path, confirm_empty_target=True, stdout=io.StringIO())
        restored = get_user_model().objects.get(username='fixture-reader')
        self.assertTrue(restored.check_password('fixture-only-password'))
        self.assertTrue(restored.has_perm('poetry.view_poem'))
        poem = Poem.objects.get()
        self.assertEqual(poem.owner_id, restored.pk)
        self.assertEqual(poem.tags.get().pk, Tag.objects.get().pk)
        self.assertEqual(FavoriteVerse.objects.get().verse.poem_id, poem.pk)
        item = MemorizationItem.objects.get()
        self.assertEqual(item.start_verse_id, poem.verses.get().pk)
        self.assertEqual(item.review_count, 1)
        self.assertEqual(ReviewLog.objects.get().item_id, item.pk)

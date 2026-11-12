"""Seed only the disposable SQLite database configured by check_browser.mjs."""
import json

from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore

from accounts.models import User
from memorization.models import MemorizationItem
from poetry.models import Poem, TreasuryBook, TreasuryEntry, Verse
from poetry.services.tags import save_tag

user = User.objects.create_user(username='browser-check')
poem = Poem.objects.create(owner=user, title='شعر آزمایشی', poet_name='شاعر آزمایشی')
Verse.objects.bulk_create([
    Verse(poem=poem, position=1, hemistich_1='به نام خداوند جان و خرد', hemistich_2='کزین برتر اندیشه برنگذرد'),
    Verse(poem=poem, position=2, hemistich_1='مي رود کنار گل', hemistich_2='با ردیف دوم'),
])
poem.tags.add(save_tag(user, 'بهار'))
MemorizationItem.objects.create(owner=user, poem=poem, scope='full')
book = TreasuryBook.objects.create(slug='browser-check', author='شاعر آزمایشی', publishes_text=True, has_contents=True,
                                   source_url='https://example.org/book', work_count=1)
long_verse = 'آزمایش خوانایی یک مصرع طولانی در گنجینهٔ فارسی روی صفحهٔ کوچک با خط فارسی'
work = TreasuryEntry.objects.create(book=book, key='work', title='اثر آزمایشی', kind='work', position=1,
                                    paragraphs=[long_verse, 'مصرع دوم آزمایش'] * 500)
session = SessionStore()
session[SESSION_KEY] = str(user.pk)
session[BACKEND_SESSION_KEY] = 'django.contrib.auth.backends.ModelBackend'
session[HASH_SESSION_KEY] = user.get_session_auth_hash()
session.save()
print(json.dumps({'session': session.session_key, 'poem': poem.get_absolute_url(), 'work': work.get_absolute_url()}))

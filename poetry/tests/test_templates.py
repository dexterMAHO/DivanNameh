"""Guards against template defects that only show up in rendered output."""
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

TEMPLATES = Path(settings.BASE_DIR) / 'templates'


class TemplateCommentTests(SimpleTestCase):
    def test_no_multiline_django_comments(self):
        """A {# #} comment spanning lines is not a comment.

        Django's tag pattern is not DOTALL, so {# … #} across a newline never
        matches and the text renders to the page. One of these reached
        production and showed an English developer note above the treasury.
        Multi-line notes must use {% comment %}.
        """
        offenders = []
        for template in sorted(TEMPLATES.rglob('*.html')):
            text = template.read_text(encoding='utf-8')
            for match in re.finditer(r'\{#', text):
                close = text.find('#}', match.end())
                if close == -1 or '\n' in text[match.end():close]:
                    line = text[:match.start()].count('\n') + 1
                    offenders.append(f'{template.relative_to(TEMPLATES)}:{line}')
        self.assertEqual(offenders, [], 'Use {% comment %} for multi-line notes: ' + ', '.join(offenders))

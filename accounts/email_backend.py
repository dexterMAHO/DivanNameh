import json
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class ResendEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for email in email_messages:
            request = Request(
                'https://api.resend.com/emails',
                data=json.dumps({
                    'from': email.from_email,
                    'to': email.to,
                    'subject': email.subject,
                    'text': email.body,
                }).encode(),
                headers={
                    'Authorization': f'Bearer {settings.RESEND_API_KEY}',
                    'Content-Type': 'application/json',
                    'User-Agent': 'DivanNameh/1.0',
                },
                method='POST',
            )
            try:
                with urlopen(request, timeout=10):
                    sent += 1
            except OSError:
                if not self.fail_silently:
                    raise
        return sent

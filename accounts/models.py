from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    login_email = models.EmailField('ایمیل ورود', unique=True, null=True, blank=True)

    @property
    def display_name(self):
        return self.get_full_name() or (self.login_email or self.username).split('@', 1)[0]


class LoginChallenge(models.Model):
    email = models.EmailField(primary_key=True)
    token_hash = models.CharField(max_length=64, unique=True)
    issued_at = models.DateTimeField()

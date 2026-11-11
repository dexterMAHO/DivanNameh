from django.contrib.auth.models import AbstractUser
from django.contrib.auth.hashers import check_password
from django.db import models


class User(AbstractUser):
    login_email = models.EmailField('ایمیل ورود', unique=True, null=True, blank=True)
    action_password = models.CharField(max_length=128, blank=True)
    theme = models.CharField(max_length=5, choices=[
        ('auto', 'مطابق دستگاه'), ('light', 'روشن'), ('dark', 'تاریک'),
    ], default='auto')

    def verify_action_password(self, password):
        return check_password(password, self.action_password)

    @property
    def display_name(self):
        return self.get_full_name() or (self.login_email or self.username).split('@', 1)[0]


class LoginChallenge(models.Model):
    email = models.EmailField(primary_key=True)
    token_hash = models.CharField(max_length=64, unique=True)
    issued_at = models.DateTimeField()

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.hashers import check_password
from django.db import models


class User(AbstractUser):
    login_email = models.EmailField('ایمیل ورود', unique=True, null=True, blank=True)
    browser_token_hash = models.CharField(max_length=64, blank=True, editable=False)
    access_link_hash = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)
    access_link_expires_at = models.DateTimeField(null=True, blank=True, editable=False)
    action_password = models.CharField(max_length=128, blank=True)
    theme = models.CharField(max_length=5, choices=[
        ('auto', 'مطابق دستگاه'), ('light', 'روشن'), ('dark', 'تاریک'),
    ], default='auto')

    palette = models.CharField(max_length=12, choices=[
        ('paper', 'کاغذ و انار'), ('ocean', 'لاجورد'),
        ('forest', 'سرو'), ('plum', 'ارغوان'),
    ], default='paper')

    recovery_digest = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)
    reading_size = models.CharField(max_length=8, choices=[
        ('normal', 'معمولی'), ('large', 'درشت'), ('largest', 'بسیار درشت'),
    ], default='normal')
    reading_spacing = models.CharField(max_length=8, choices=[
        ('normal', 'معمولی'), ('wide', 'باز'),
    ], default='normal')
    reading_layout = models.CharField(max_length=8, choices=[
        ('original', 'چیدمان اثر'), ('stacked', 'مصرع‌ها زیر هم'), ('columns', 'مصرع‌ها کنار هم در عرض کافی'),
    ], default='original')
    reading_numbers = models.BooleanField(default=True)

    def verify_action_password(self, password):
        return check_password(password, self.action_password)

    @property
    def display_name(self):
        return self.get_full_name() or (self.login_email or self.username).split('@', 1)[0]


class LoginChallenge(models.Model):
    email = models.EmailField(primary_key=True)
    token_hash = models.CharField(max_length=64, unique=True)
    issued_at = models.DateTimeField()


class TrustedBrowser(models.Model):
    label = models.CharField(max_length=80, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trusted_browsers')
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    expires_at = models.DateTimeField()


class ProfilePhoto(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile_photo')
    image = models.BinaryField()


class BrowserAccessLink(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='browser_access_links')
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    expires_at = models.DateTimeField()

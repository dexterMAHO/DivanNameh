def action_password_error(request, *, required=False):
    """Return a message when this request needs the reader's operation password."""
    user = request.user
    if not user.action_password:
        return 'برای برداشتن شعر از کتابخانه، در تنظیمات حساب رمز عملیات بسازید.' if required else ''
    password = request.POST.get('action_password', '')
    if len(password) > 128 or not user.verify_action_password(password):
        return 'رمز عملیات درست نیست.'
    return ''

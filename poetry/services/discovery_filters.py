"""Length categories shared by personal and treasury discovery."""
LENGTH_CHOICES = (
    ('single', 'تک‌بیتی'), ('double', 'دوبیتی'), ('under15', 'زیر ۱۵ بیت'),
    ('over15', 'بالای ۱۵ بیت'), ('modern', 'شعر نو'),
)


def matches_length(length, count, line_layout=False):
    if length == 'modern':
        return line_layout
    if length in ('single', 'double', 'under15', 'over15') and line_layout:
        return False
    return {
        'single': count == 1, 'double': count == 2,
        'under15': 0 < count < 15, 'over15': count > 15,
        'short': count <= 8, 'long': count > 8,
    }.get(length, True)

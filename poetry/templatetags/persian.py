"""Persian digit rendering — Django localises formats but never the digits themselves."""
from django import template

register = template.Library()

DIGITS = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
THOUSANDS = '٬'


@register.filter
def persian(value):
    """Latin digits become Persian ones; everything else passes through."""
    return str(value).translate(DIGITS)


@register.filter
def tally(value):
    """A counted quantity: grouped in threes, then written with Persian digits."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return persian(value)
    return f'{number:,}'.replace(',', THOUSANDS).translate(DIGITS)

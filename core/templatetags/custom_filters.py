"""
Custom template filters for ERP system.
"""
from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()


@register.filter
def multiply(value, arg):
    """Multiply the value by the argument."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def intcomma(value):
    """Format number with commas as thousand separator."""
    try:
        # Format với dấu phẩy phân cách phần nghìn
        return f"{int(float(value)):,}"
    except (ValueError, TypeError):
        return value


@register.filter
def add_thousand_sep(value, sep='.'):
    """
    Format số với dấu phân cách phần nghìn (mặc định dùng '.').
    Ví dụ: 500000 -> 500.000
    """
    try:
        if value is None:
            return ""
        number = int(Decimal(str(value)))
        return f"{number:,}".replace(',', sep)
    except (InvalidOperation, ValueError, TypeError):
        return value


@register.filter
def hours_hhmm(value):
    """Format Decimal hours to days+HH:MMh (e.g. 48 -> 2d 00:00h, 7.5 -> 7:30h, 0 -> 0:00h)."""
    try:
        if value is None:
            return "0:00h"
        hours = Decimal(str(value))
        if hours < 0:
            return "0:00h"
        total_minutes = int((hours * Decimal(60)).quantize(Decimal('1')))
        h = total_minutes // 60
        m = total_minutes % 60
        if h >= 24:
            days = h // 24
            hh = h % 24
            return f"{days}d {hh:02d}:{m:02d}h"
        return f"{h:02d}:{m:02d}h"
    except (InvalidOperation, ValueError, TypeError):
        return "0:00h"


@register.filter
def hours_format(value):
    """Format hours without trailing zeros (e.g. 141.0 -> 141, 7.5 -> 7.5)."""
    try:
        if value is None:
            return "0"
        hours = Decimal(str(value))
        # Nếu là số nguyên, trả về không có phần thập phân
        if hours == hours.quantize(Decimal('1')):
            return str(int(hours))
        # Nếu có phần thập phân, format 1 chữ số
        return f"{float(hours):.1f}".rstrip('0').rstrip('.')
    except (InvalidOperation, ValueError, TypeError):
        return "0"

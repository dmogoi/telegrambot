# bot/templatetags/log_tags.py
from django import template

register = template.Library()


@register.filter(name='log_badge_color')
def log_badge_color(action_type):
    color_map = {
        'CREATE': 'success',
        'UPDATE': 'primary',
        'DELETE': 'danger',
        'USER_UPDATE': 'warning',
        'SYSTEM_EVENT': 'info'
    }
    return color_map.get(action_type, 'secondary')

from django import template

register = template.Library()

@register.filter
def dict_get(dictionary, key):
    """Get value from dictionary by key in templates"""
    if isinstance(dictionary, dict):
        return dictionary.get(key, {})
    return {}
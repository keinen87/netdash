from django import template

register = template.Library()


@register.filter
def get_item_label(dictionary, key):
    """Возвращает заголовок поля по ключу из словаря {key: (label, getter)}."""
    item = dictionary.get(key)
    if not item:
        return key
    return item[0]
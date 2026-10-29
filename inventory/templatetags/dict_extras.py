from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Возвращает значение словаря по ключу: d['key']. Для ldap_search.html."""
    if not dictionary:
        return ""
    if not isinstance(dictionary, dict):
        return ""
    return dictionary.get(key, "")


@register.filter
def get_item_label(dictionary, key):
    """Возвращает заголовок поля: d['key'][0]. Для export.html."""
    if not dictionary:
        return key
    item = dictionary.get(key)
    if not item:
        return key
    # item = (label, getter), нужен только label
    if isinstance(item, (tuple, list)) and len(item) >= 1:
        return item[0]
    return key
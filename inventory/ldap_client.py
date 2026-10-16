"""Клиент для поиска в LDAP-каталоге (Active Directory)."""

from ldap3 import ALL, SUBTREE, Connection, Server
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

from django.conf import settings


# Атрибуты, которые запрашиваем у каталога и показываем пользователю
LDAP_ATTRIBUTES = [
    "cn",
    "sAMAccountName",
    "displayName",
    "givenName",
    "sn",
    "mail",
    "telephoneNumber",
    "mobile",
    "title",
    "department",
    "company",
    "physicalDeliveryOfficeName",
    "whenCreated",
    "lastLogonTimestamp",
    "userAccountControl",
]


# Человекочитаемые подписи для атрибутов в шаблоне
ATTRIBUTE_LABELS = {
    "domain_login": "Логин с доменом",
    "cn": "Полное имя (CN)",
    "sAMAccountName": "Логин",
    "displayName": "Отображаемое имя",
    "givenName": "Имя",
    "sn": "Фамилия",
    "mail": "Email",
    "telephoneNumber": "Телефон",
    "mobile": "Мобильный",
    "title": "Должность",
    "department": "Отдел",
    "company": "Организация",
    "physicalDeliveryOfficeName": "Кабинет",
    "whenCreated": "Учётка создана",
    "lastLogonTimestamp": "Последний вход",
    "userAccountControl": "Состояние учётки",
}


def is_configured():
    """Настроен ли LDAP — есть ли минимально необходимые параметры."""
    return bool(settings.LDAP_SERVER and settings.LDAP_BIND_DN and settings.LDAP_BASE_DN)


def _netbios_domain():
    """
    Возвращает NetBIOS-имя домена.

    1. Если в .env задано LDAP_NETBIOS_DOMAIN — используем его.
    2. Иначе — берём первый DC=... из LDAP_BASE_DN.
    3. Если и его нет — возвращаем пустую строку.
    """
    explicit = (getattr(settings, "LDAP_NETBIOS_DOMAIN", "") or "").strip()
    if explicit:
        return explicit

    base = (settings.LDAP_BASE_DN or "").strip()
    for part in base.split(","):
        part = part.strip()
        if part.lower().startswith("dc="):
            return part[3:]
    return ""


def _build_search_filter(query: str) -> str:
    """Строит LDAP-фильтр с экранированием ввода (защита от LDAP-инъекций)."""
    safe = escape_filter_chars(query)
    return (
        "(|"
        f"(sAMAccountName=*{safe}*)"
        f"(cn=*{safe}*)"
        f"(sn=*{safe}*)"
        f"(givenName=*{safe}*)"
        f"(displayName=*{safe}*)"
        f"(mail=*{safe}*)"
        f"(telephoneNumber=*{safe}*)"
        f"(mobile=*{safe}*)"
        ")"
    )


def _fmt(value):
    """Приводит значение атрибута из ldap3 к строке или пустой строке."""
    if value is None:
        return ""
    text = str(value).strip()
    return text


def search_ldap(query: str, size_limit: int = None):
    """
    Ищет записи в LDAP по подстроке.

    Возвращает кортеж (results, error):
      - results — список словарей {attribute: value, ...}
      - error — строка с описанием ошибки или None при успехе
    """
    if not is_configured():
        return [], "LDAP не настроен. Проверьте переменные в .env."

    query = (query or "").strip()
    if len(query) < 2:
        return [], None

    limit = size_limit or settings.LDAP_SIZE_LIMIT

    try:
        server = Server(
            settings.LDAP_SERVER,
            port=settings.LDAP_PORT,
            use_ssl=settings.LDAP_USE_SSL,
            connect_timeout=settings.LDAP_TIMEOUT,
            get_info=ALL,
        )
        conn = Connection(
            server,
            user=settings.LDAP_BIND_DN,
            password=settings.LDAP_BIND_PASSWORD,
            auto_bind=True,
            receive_timeout=settings.LDAP_TIMEOUT,
        )
    except LDAPException as exc:
        return [], f"Не удалось подключиться к LDAP: {exc}"

    try:
        conn.search(
            search_base=settings.LDAP_BASE_DN,
            search_filter=_build_search_filter(query),
            search_scope=SUBTREE,
            attributes=LDAP_ATTRIBUTES,
            size_limit=limit,
            time_limit=settings.LDAP_TIMEOUT,
        )

        domain = _netbios_domain()

        results = []
        for entry in conn.entries:
            row = {"entry_dn": entry.entry_dn}
            for attr in LDAP_ATTRIBUTES:
                if attr in entry:
                    row[attr] = _fmt(entry[attr].value)
                else:
                    row[attr] = ""

            # Вычисляемое поле «логин с доменом» вида DOMAIN\login
            sam = row.get("sAMAccountName", "")
            if sam and domain:
                row["domain_login"] = f"{domain}\\{sam}"
            else:
                row["domain_login"] = sam

            results.append(row)

        return results, None

    except LDAPException as exc:
        return [], f"Ошибка поиска в LDAP: {exc}"
    finally:
        try:
            conn.unbind()
        except Exception:
            pass
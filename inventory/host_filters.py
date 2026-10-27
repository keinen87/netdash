"""Общая логика фильтрации хостов для главной и выгрузки в Excel."""

import re

from ipaddress import ip_network

from django.db.models import F, Q, Value
from django.db.models.functions import Replace, Upper


# Все символы, кроме hex (0-9, A-F)
_NON_HEX = re.compile(r"[^0-9A-Fa-f]")
# Любой из разделителей MAC-адреса
_HAS_SEPARATOR = re.compile(r"[-:.]")


def normalize_mac(text: str) -> str:
    """Убирает разделители из MAC: 'AA-BB-CC' → 'AABBCC'. Верхний регистр."""
    return _NON_HEX.sub("", text).upper()


def looks_like_mac(text: str) -> bool:
    """
    Похоже ли на MAC:
      - ровно 12 hex-символов (AA:BB:CC:DD:EE:FF, AABBCCDDEEFF);
      - или содержит разделитель и чётное число hex (AA-BB, AA:BB:CC).
    """
    cleaned = _NON_HEX.sub("", text)
    if not cleaned:
        return False
    if _HAS_SEPARATOR.search(text) and len(cleaned) % 2 == 0:
        return True
    return len(cleaned) == 12


def apply_host_filters(request, hosts):
    """
    Применяет к queryset хостов все фильтры из GET-запроса:
      - q        — текстовый поиск (включая MAC в любом формате)
      - kind     — выбранные типы (OR между значениями)
      - subnet   — выбранные подсети /24 (OR между значениями)
      - has_sim  — только хосты с привязанной SIM-картой

    Возвращает отфильтрованный queryset.
    """
    query = request.GET.get("q", "").strip()
    kinds = request.GET.getlist("kind")
    subnets = request.GET.getlist("subnet")
    has_sim = request.GET.get("has_sim") == "1"

    if kinds:
        hosts = hosts.filter(kind__in=kinds)

    if subnets:
        subnet_q = Q()
        has_valid_subnet = False
        for subnet in subnets:
            try:
                ip_network(subnet, strict=False)
            except (ValueError, TypeError):
                continue
            prefix = subnet.split("/")[0].rsplit(".", 1)[0] + "."
            subnet_q |= Q(ip_addresses__address__startswith=prefix)
            has_valid_subnet = True
        if has_valid_subnet:
            hosts = hosts.filter(subnet_q)

    if has_sim:
        hosts = hosts.filter(sims__isnull=False).distinct()

    if query:
        q = (
            Q(description__icontains=query)
            | Q(kind__icontains=query)
            | Q(domain_name__icontains=query)
            | Q(mac_address__icontains=query)
            | Q(ssid__icontains=query)
            | Q(serial_number__icontains=query)
            | Q(comment__icontains=query)
            | Q(ip_addresses__address__icontains=query)
            | Q(ip_addresses__comment__icontains=query)
            | Q(users__full_name__icontains=query)
            | Q(users__position__icontains=query)
            | Q(users__phone_work__icontains=query)
            | Q(users__description__icontains=query)
            | Q(users__comment__icontains=query)
            | Q(softwares__name__icontains=query)
            | Q(softwares__version__icontains=query)
            | Q(softwares__comment__icontains=query)
            | Q(hardware__manufacturer__icontains=query)
            | Q(hardware__cpu__icontains=query)
            | Q(hardware__ram__icontains=query)
            | Q(hardware__motherboard__icontains=query)
            | Q(hardware__storage_type__icontains=query)
            | Q(hardware__storage_capacity__icontains=query)
            | Q(hardware__comment__icontains=query)
            | Q(accounts__login__icontains=query)
            | Q(accounts__kind__icontains=query)
            | Q(accounts__comment__icontains=query)
            | Q(accounts__person__full_name__icontains=query)
            | Q(sims__full_number__icontains=query)
            | Q(sims__short_number__icontains=query)
            | Q(sims__icc__icontains=query)
            | Q(sims__apn__icontains=query)
            | Q(sims__comment__icontains=query)
            | Q(sims__person__full_name__icontains=query)
            | Q(history__fact__icontains=query)
        )

        # Поиск по MAC в любом формате
        if looks_like_mac(query):
            # Нормализуем mac_address в БД: убираем :, -, ., в верхний регистр
            mac_clean = Upper(
                Replace(
                    Replace(
                        Replace(F("mac_address"), Value(":"), Value("")),
                        Value("-"),
                        Value(""),
                    ),
                    Value("."),
                    Value(""),
                )
            )
            norm_query = normalize_mac(query)
            hosts = hosts.annotate(_mac_clean=mac_clean)
            q |= Q(_mac_clean__contains=norm_query)

        hosts = hosts.filter(q).distinct()

    return hosts
"""Реестр полей для выгрузки в Excel.

Чтобы добавить новое поле в отчёт:
  1. Дописать строку в EXPORT_FIELDS: (ключ, заголовок, функция извлечения)
  2. Дописать ключ в подходящую группу FIELD_GROUPS
  3. Перезапустить сервер — поле появится в форме выгрузки

Больше нигде править не нужно.
"""


def _format_hardware(host):
    hw = getattr(host, "hardware", None)
    if not hw:
        return ""
    parts = [hw.manufacturer, hw.cpu, hw.ram, hw.motherboard]
    return " / ".join(p for p in parts if p)


# Порядок в этом списке = порядок столбцов в Excel, если пользователь
# ничего не менял. Реальный порядок задаётся выбором в форме.
EXPORT_FIELDS = [
    # --- Идентификация ---
    ("kind", "Тип", lambda h: h.get_kind_display()),
    ("description", "Описание", lambda h: h.description),
    ("domain_name", "Доменное имя", lambda h: h.domain_name),

    # --- Сеть ---
    ("primary_ip", "Основной IP", lambda h: h.primary_ip or ""),
    (
        "all_ips",
        "Все IP",
        lambda h: "\n".join(ip.address for ip in h.ip_addresses.all()),
    ),
    ("mac_address", "MAC-адрес", lambda h: h.mac_address),
    ("ssid", "SSID", lambda h: h.ssid if h.supports_ssid else ""),

    # --- Пользователи ---
    (
        "users",
        "Пользователи",
        lambda h: ", ".join(u.full_name for u in h.users.all()),
    ),
    (
        "phones",
        "Телефоны",
        lambda h: ", ".join(
            u.phone_work for u in h.users.all() if u.phone_work
        ),
    ),

    # --- Оборудование ---
    (
        "serial_number",
        "Серийный номер",
        lambda h: h.serial_number if h.supports_serial else "",
    ),
    ("hardware", "Аппаратная часть", _format_hardware),
    (
        "softwares",
        "ПО",
        lambda h: ", ".join(str(s) for s in h.softwares.all()),
    ),

    # --- SIM ---
    (
        "sims",
        "SIM-карты",
        lambda h: ", ".join(s.full_number for s in h.sims.all()),
    ),

    # --- Служебное ---
    ("comment", "Комментарий", lambda h: h.comment),
]


# Для быстрого доступа по ключу: EXPORT_FIELDS_BY_KEY["kind"] → ("Тип", getter)
EXPORT_FIELDS_BY_KEY = {
    key: (label, getter) for key, label, getter in EXPORT_FIELDS
}


# Группировка для формы выбора полей. Порядок групп = порядок в форме,
# порядок ключей внутри группы = порядок чекбоксов в этой группе.
FIELD_GROUPS = [
    ("Идентификация", ["kind", "description", "domain_name"]),
    ("Сеть", ["primary_ip", "all_ips", "mac_address", "ssid"]),
    ("Пользователи", ["users", "phones"]),
    ("Оборудование", ["serial_number", "hardware", "softwares"]),
    ("SIM", ["sims"]),
    ("Служебное", ["comment"]),
]
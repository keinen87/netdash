import ipaddress
import platform
import subprocess

from django.core.exceptions import PermissionDenied
from django.db.models import OuterRef, Q, Subquery
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from urllib.parse import quote

from . import ldap_client
from .models import (
    Account,
    HardwareInfo,
    History,
    Host,
    Person,
    SIM,
    Software,
)


HOST_SORT_FIELDS = {
    "fio": "first_user_name",
    "domain": "domain_name",
    "ip": "ip_address",
    "phone": "first_user_phone",
}


def dashboard(request):
    query = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "").strip()
    direction = request.GET.get("dir", "asc").strip()

    hosts = Host.objects.all().prefetch_related("users", "softwares")
    persons = Person.objects.none()
    accounts = Account.objects.none()
    sims = SIM.objects.none()
    history = History.objects.none()
    softwares = Software.objects.none()

    if query:
        hosts = hosts.filter(
            Q(description__icontains=query)
            | Q(kind__icontains=query)
            | Q(domain_name__icontains=query)
            | Q(ip_address__icontains=query)
            | Q(mac_address__icontains=query)
            | Q(comment__icontains=query)
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
        ).distinct()

        persons = Person.objects.filter(
            Q(full_name__icontains=query)
            | Q(position__icontains=query)
            | Q(phone_work__icontains=query)
            | Q(description__icontains=query)
            | Q(comment__icontains=query)
            | Q(hosts__domain_name__icontains=query)
            | Q(hosts__ip_address__icontains=query)
            | Q(accounts__login__icontains=query)
            | Q(accounts__comment__icontains=query)
            | Q(sims__full_number__icontains=query)
            | Q(sims__icc__icontains=query)
        ).distinct()

        accounts = Account.objects.filter(
            Q(login__icontains=query)
            | Q(kind__icontains=query)
            | Q(comment__icontains=query)
            | Q(person__full_name__icontains=query)
            | Q(person__position__icontains=query)
            | Q(host__domain_name__icontains=query)
            | Q(host__ip_address__icontains=query)
        ).distinct()

        sims = SIM.objects.filter(
            Q(full_number__icontains=query)
            | Q(short_number__icontains=query)
            | Q(icc__icontains=query)
            | Q(apn__icontains=query)
            | Q(comment__icontains=query)
            | Q(person__full_name__icontains=query)
            | Q(host__domain_name__icontains=query)
            | Q(host__ip_address__icontains=query)
        ).distinct()

        history = History.objects.filter(
            Q(fact__icontains=query)
            | Q(host__domain_name__icontains=query)
            | Q(host__ip_address__icontains=query)
            | Q(person__full_name__icontains=query)
        ).distinct()

        softwares = Software.objects.filter(
            Q(name__icontains=query)
            | Q(version__icontains=query)
            | Q(comment__icontains=query)
            | Q(hosts__domain_name__icontains=query)
            | Q(hosts__ip_address__icontains=query)
        ).distinct()

    first_user = (
        Person.objects
        .filter(hosts=OuterRef("pk"))
        .order_by("full_name")
    )
    hosts = hosts.annotate(
        first_user_name=Subquery(first_user.values("full_name")[:1]),
        first_user_phone=Subquery(first_user.values("phone_work")[:1]),
    )

    if sort in HOST_SORT_FIELDS:
        field = HOST_SORT_FIELDS[sort]
        if direction == "desc":
            field = "-" + field
        hosts = hosts.order_by(field)

    context = {
        "query": query,
        "sort": sort,
        "direction": direction,
        "hosts": hosts,
        "persons": persons,
        "accounts": accounts,
        "sims": sims,
        "history": history,
        "softwares": softwares,
    }
    return render(request, "inventory/dashboard.html", context)


def host_detail(request, pk):
    host = get_object_or_404(Host, pk=pk)

    can_edit = request.user.is_authenticated and request.user.is_staff

    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied("Добавлять записи в историю может только администратор.")

        fact = request.POST.get("fact", "").strip()
        if fact:
            default_person = host.users.first()
            History.objects.create(
                host=host,
                person=default_person,
                fact=fact,
            )
        return redirect("inventory:host_detail", pk=host.pk)

    hardware = HardwareInfo.objects.filter(host=host).first()

    # ---------- Путь к рабочему столу ----------
    desktop_path = ""
    desktop_url = ""
    desktop_login = ""

    if host.supports_desktop_share and (host.domain_name or host.ip_address):
        first_user = host.users.first()
        if first_user:
            # 1) аккаунт этого пользователя, привязанный к этому хосту
            acc = first_user.accounts.filter(host=host).first()
            # 2) если нет — любой его аккаунт
            if acc is None:
                acc = first_user.accounts.first()
            if acc and acc.login:
                desktop_login = acc.login
                hostname = host.domain_name or host.ip_address
                # UNC-путь для копирования (реальные имена папок: Users, Desktop)
                desktop_path = f"\\\\{hostname}\\C$\\Users\\{acc.login}\\Desktop"
                # file://-URL для кнопки «Открыть» (логин URL-кодируется)
                desktop_url = (
                    f"file://{hostname}/C$/Users/{quote(acc.login, safe='')}/Desktop"
                )

    context = {
        "host": host,
        "hardware": hardware,
        "users": host.users.all(),
        "accounts": host.accounts.select_related("person").all(),
        "sims": host.sims.select_related("person").all(),
        "softwares": host.softwares.all(),
        "history": host.history.all(),
        "can_edit": can_edit,
        "desktop_path": desktop_path,
        "desktop_url": desktop_url,
        "desktop_login": desktop_login,
    }
    return render(request, "inventory/host_detail.html", context)


@require_POST
def host_ping(request, pk):
    if not (request.user.is_authenticated and request.user.is_staff):
        return JsonResponse(
            {"ok": False, "error": "Проверка связи доступна только администратору."},
            status=403,
        )

    host = get_object_or_404(Host, pk=pk)
    ip = host.ip_address

    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return JsonResponse({"ok": False, "error": "Некорректный IP-адрес."}, status=400)

    system = platform.system().lower()
    if system == "windows":
        cmd = ["ping", "-n", "4", "-w", "2000", ip]
    else:
        cmd = ["ping", "-c", "4", "-W", "2", ip]

    try:
        result = subprocess.run(cmd, capture_output=True, timeout=15)
    except subprocess.TimeoutExpired:
        return JsonResponse({"ok": False, "error": "Тайм-аут ping (15 секунд)."})
    except FileNotFoundError:
        return JsonResponse({"ok": False, "error": "Утилита ping не найдена на сервере."})
    except Exception as exc:
        return JsonResponse({"ok": False, "error": f"Ошибка: {exc}"})

    raw = (result.stdout or b"") + (result.stderr or b"")
    if system == "windows":
        candidates = ("cp866", "cp1251", "utf-8")
    else:
        candidates = ("utf-8",)

    output = None
    for enc in candidates:
        try:
            output = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if output is None:
        output = raw.decode("utf-8", errors="replace")

    return JsonResponse({"ok": result.returncode == 0, "output": output.strip()})


def ldap_search_view(request):
    if not (request.user.is_authenticated and request.user.is_staff):
        raise PermissionDenied("Поиск в каталоге доступен только администратору.")

    query = request.GET.get("q", "").strip()
    results = []
    error = None

    if query:
        results, error = ldap_client.search_ldap(query)

    context = {
        "query": query,
        "results": results,
        "error": error,
        "is_configured": ldap_client.is_configured(),
        "attribute_labels": ldap_client.ATTRIBUTE_LABELS,
        "attribute_order": [
            "domain_login",
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
        ],
    }
    return render(request, "inventory/ldap_search.html", context)
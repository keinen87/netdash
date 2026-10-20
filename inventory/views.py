import ipaddress
import platform
import subprocess

from django.core.exceptions import PermissionDenied
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import OuterRef, Q, Subquery
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import ldap_client
from .models import (
    Account,
    HardwareInfo,
    History,
    Host,
    IPAddress,
    Person,
    SIM,
    Software,
)


HOST_SORT_FIELDS = {
    "fio": "first_user_name",
    "domain": "domain_name",
    "ip": "first_ip_address",
    "phone": "first_user_phone",
}

HOSTS_PER_PAGE = 25


def _build_page_range(current, total, window=2):
    if total <= 1:
        return [1]

    pages = {1, total}
    low = max(1, current - window)
    high = min(total, current + window)
    for n in range(low, high + 1):
        pages.add(n)

    result = []
    prev = None
    for n in sorted(pages):
        if prev is not None and n - prev > 1:
            result.append(None)
        result.append(n)
        prev = n
    return result


def dashboard(request):
    query = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "").strip()
    direction = request.GET.get("dir", "asc").strip()
    page_number = request.GET.get("page", "1").strip()
    kinds_selected = request.GET.getlist("kind")

    hosts = Host.objects.all().prefetch_related("users", "softwares", "ip_addresses")
    persons = Person.objects.none()
    accounts = Account.objects.none()
    sims = SIM.objects.none()
    history = History.objects.none()
    softwares = Software.objects.none()

    # Фильтр по типам — применяется независимо от текстового поиска
    if kinds_selected:
        hosts = hosts.filter(kind__in=kinds_selected)

    if query:
        hosts = hosts.filter(
            Q(description__icontains=query)
            | Q(kind__icontains=query)
            | Q(domain_name__icontains=query)
            | Q(mac_address__icontains=query)
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
        ).distinct()

        persons = Person.objects.filter(
            Q(full_name__icontains=query)
            | Q(position__icontains=query)
            | Q(phone_work__icontains=query)
            | Q(description__icontains=query)
            | Q(comment__icontains=query)
            | Q(hosts__domain_name__icontains=query)
            | Q(hosts__ip_addresses__address__icontains=query)
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
            | Q(host__ip_addresses__address__icontains=query)
        ).distinct()

        sims = SIM.objects.filter(
            Q(full_number__icontains=query)
            | Q(short_number__icontains=query)
            | Q(icc__icontains=query)
            | Q(apn__icontains=query)
            | Q(comment__icontains=query)
            | Q(person__full_name__icontains=query)
            | Q(host__domain_name__icontains=query)
            | Q(host__ip_addresses__address__icontains=query)
        ).distinct()

        history = History.objects.filter(
            Q(fact__icontains=query)
            | Q(host__domain_name__icontains=query)
            | Q(host__ip_addresses__address__icontains=query)
            | Q(person__full_name__icontains=query)
        ).distinct()

        softwares = Software.objects.filter(
            Q(name__icontains=query)
            | Q(version__icontains=query)
            | Q(comment__icontains=query)
            | Q(hosts__domain_name__icontains=query)
            | Q(hosts__ip_addresses__address__icontains=query)
        ).distinct()

    first_user = (
        Person.objects
        .filter(hosts=OuterRef("pk"))
        .order_by("full_name")
    )
    first_ip = (
        IPAddress.objects
        .filter(host=OuterRef("pk"))
        .order_by("-is_primary", "address")
    )
    hosts = hosts.annotate(
        first_user_name=Subquery(first_user.values("full_name")[:1]),
        first_user_phone=Subquery(first_user.values("phone_work")[:1]),
        first_ip_address=Subquery(first_ip.values("address")[:1]),
    )

    if sort in HOST_SORT_FIELDS:
        field = HOST_SORT_FIELDS[sort]
        if direction == "desc":
            field = "-" + field
        hosts = hosts.order_by(field)

    paginator = Paginator(hosts, HOSTS_PER_PAGE)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Все GET-параметры, кроме page — для ссылок пагинации
    query_params = request.GET.copy()
    query_params.pop("page", None)
    query_suffix = query_params.urlencode()
    if query_suffix:
        query_suffix += "&"

    # Все GET-параметры, кроме page, sort, dir — для ссылок сортировки
    sort_params = request.GET.copy()
    sort_params.pop("page", None)
    sort_params.pop("sort", None)
    sort_params.pop("dir", None)
    sort_suffix = sort_params.urlencode()
    if sort_suffix:
        sort_suffix += "&"

    context = {
        "query": query,
        "sort": sort,
        "direction": direction,
        "kinds_selected": kinds_selected,
        "kind_choices": Host.KIND_CHOICES,
        "page_obj": page_obj,
        "paginator": paginator,
        "page_range": _build_page_range(page_obj.number, paginator.num_pages),
        "query_suffix": query_suffix,
        "sort_suffix": sort_suffix,
        "hosts": page_obj,
        "persons": persons,
        "accounts": accounts,
        "sims": sims,
        "history": history,
        "softwares": softwares,
    }
    return render(request, "inventory/dashboard.html", context)


def host_detail(request, pk):
    host = get_object_or_404(
        Host.objects.prefetch_related("ip_addresses", "users", "softwares"),
        pk=pk,
    )

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

    web_account = host.accounts.filter(kind=Account.KIND_HOST).first()
    base_web_url = host.web_ui_url
    web_ui_url = base_web_url
    web_ui_autologin = False

    if base_web_url and web_account and web_account.login:
        autologin = host.get_web_ui_autologin_url(
            web_account.login, web_account.password or ""
        )
        if autologin:
            web_ui_url = autologin
            web_ui_autologin = True

    context = {
        "host": host,
        "hardware": hardware,
        "users": host.users.all(),
        "ip_addresses": host.ip_addresses.all(),
        "accounts": host.accounts.select_related("person").all(),
        "sims": host.sims.select_related("person").all(),
        "softwares": host.softwares.all(),
        "history": host.history.all(),
        "can_edit": can_edit,
        "web_account": web_account,
        "web_ui_url": web_ui_url,
        "web_ui_autologin": web_ui_autologin,
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
    ip = host.primary_ip

    if not ip:
        return JsonResponse(
            {"ok": False, "error": "У хоста не задан IP-адрес."},
            status=400,
        )

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
import ipaddress
import platform
import subprocess

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import (
    Account,
    HardwareInfo,
    History,
    Host,
    Person,
    SIM,
    Software,
)


def dashboard(request):
    query = request.GET.get("q", "").strip()

    hosts = Host.objects.all().prefetch_related("users", "softwares")
    persons = Person.objects.none()
    accounts = Account.objects.none()
    sims = SIM.objects.none()
    history = History.objects.none()
    softwares = Software.objects.none()

    if query:
        # ---------- ХОСТЫ ----------
        # Ищем во всех собственных полях, а также во всех связанных моделях:
        # HardwareInfo (OneToOne), Account/SIM/History (FK),
        # Person/Software (M2M).
        hosts = hosts.filter(
            # Собственные поля хоста
            Q(description__icontains=query)
            | Q(kind__icontains=query)
            | Q(domain_name__icontains=query)
            | Q(ip_address__icontains=query)
            | Q(mac_address__icontains=query)
            | Q(comment__icontains=query)
            # M2M: пользователи
            | Q(users__full_name__icontains=query)
            | Q(users__position__icontains=query)
            | Q(users__phone_work__icontains=query)
            | Q(users__description__icontains=query)
            | Q(users__comment__icontains=query)
            # M2M: ПО
            | Q(softwares__name__icontains=query)
            | Q(softwares__version__icontains=query)
            | Q(softwares__comment__icontains=query)
            # OneToOne: аппаратная часть
            | Q(hardware__manufacturer__icontains=query)
            | Q(hardware__cpu__icontains=query)
            | Q(hardware__ram__icontains=query)
            | Q(hardware__motherboard__icontains=query)
            | Q(hardware__storage_type__icontains=query)
            | Q(hardware__storage_capacity__icontains=query)
            | Q(hardware__comment__icontains=query)
            # FK: учётные записи
            | Q(accounts__login__icontains=query)
            | Q(accounts__kind__icontains=query)
            | Q(accounts__comment__icontains=query)
            | Q(accounts__person__full_name__icontains=query)
            # FK: SIM-карты
            | Q(sims__full_number__icontains=query)
            | Q(sims__short_number__icontains=query)
            | Q(sims__icc__icontains=query)
            | Q(sims__comment__icontains=query)
            | Q(sims__person__full_name__icontains=query)
            # FK: история
            | Q(history__fact__icontains=query)
        ).distinct()

        # ---------- ПОЛЬЗОВАТЕЛИ ----------
        persons = Person.objects.filter(
            Q(full_name__icontains=query)
            | Q(position__icontains=query)
            | Q(phone_work__icontains=query)
            | Q(description__icontains=query)
            | Q(comment__icontains=query)
            # ищем и по связанным хостам, учёткам, SIM
            | Q(hosts__domain_name__icontains=query)
            | Q(hosts__ip_address__icontains=query)
            | Q(accounts__login__icontains=query)
            | Q(accounts__comment__icontains=query)
            | Q(sims__full_number__icontains=query)
            | Q(sims__icc__icontains=query)
        ).distinct()

        # ---------- УЧЁТНЫЕ ЗАПИСИ ----------
        # Пароль исключён намеренно — см. комментарий выше.
        accounts = Account.objects.filter(
            Q(login__icontains=query)
            | Q(kind__icontains=query)
            | Q(comment__icontains=query)
            | Q(person__full_name__icontains=query)
            | Q(person__position__icontains=query)
            | Q(host__domain_name__icontains=query)
            | Q(host__ip_address__icontains=query)
        ).distinct()

        # ---------- SIM-КАРТЫ ----------
        sims = SIM.objects.filter(
            Q(full_number__icontains=query)
            | Q(short_number__icontains=query)
            | Q(icc__icontains=query)
            | Q(comment__icontains=query)
            | Q(person__full_name__icontains=query)
            | Q(host__domain_name__icontains=query)
            | Q(host__ip_address__icontains=query)
        ).distinct()

        # ---------- ИСТОРИЯ ----------
        history = History.objects.filter(
            Q(fact__icontains=query)
            | Q(host__domain_name__icontains=query)
            | Q(host__ip_address__icontains=query)
            | Q(person__full_name__icontains=query)
        ).distinct()

        # ---------- ПО ----------
        softwares = Software.objects.filter(
            Q(name__icontains=query)
            | Q(version__icontains=query)
            | Q(comment__icontains=query)
            | Q(hosts__domain_name__icontains=query)
            | Q(hosts__ip_address__icontains=query)
        ).distinct()

    context = {
        "query": query,
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

    context = {
        "host": host,
        "hardware": hardware,
        "users": host.users.all(),
        "accounts": host.accounts.select_related("person").all(),
        "sims": host.sims.select_related("person").all(),
        "softwares": host.softwares.all(),
        "history": host.history.all(),
        "can_edit": can_edit,
    }
    return render(request, "inventory/host_detail.html", context)


@require_POST
def host_ping(request, pk):
    """Запускает ping до IP-адреса хоста. Возвращает JSON с выводом команды."""
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
        return JsonResponse(
            {"ok": False, "error": "Утилита ping не найдена на сервере."}
        )
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

    output = output.strip()
    return JsonResponse({"ok": result.returncode == 0, "output": output})
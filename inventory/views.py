from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

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
        hosts = hosts.filter(
            Q(description__icontains=query)
            | Q(ip_address__icontains=query)
            | Q(mac_address__icontains=query)
            | Q(domain_name__icontains=query)
            | Q(comment__icontains=query)
            | Q(users__full_name__icontains=query)
            | Q(softwares__name__icontains=query)
            | Q(hardware__manufacturer__icontains=query)
            | Q(hardware__cpu__icontains=query)
            | Q(hardware__ram__icontains=query)
            | Q(hardware__motherboard__icontains=query)
            | Q(hardware__storage_type__icontains=query)
            | Q(hardware__storage_capacity__icontains=query)
        ).distinct()

        persons = Person.objects.filter(
            Q(full_name__icontains=query)
            | Q(position__icontains=query)
            | Q(phone_work__icontains=query)
            | Q(description__icontains=query)
            | Q(comment__icontains=query)
        ).distinct()

        accounts = Account.objects.filter(
            Q(login__icontains=query)
            | Q(kind__icontains=query)
            | Q(comment__icontains=query)
            | Q(person__full_name__icontains=query)
        ).distinct()

        sims = SIM.objects.filter(
            Q(full_number__icontains=query)
            | Q(short_number__icontains=query)
            | Q(icc__icontains=query)
            | Q(comment__icontains=query)
        ).distinct()

        history = History.objects.filter(
            Q(fact__icontains=query)
        ).distinct()

        softwares = Software.objects.filter(
            Q(name__icontains=query)
            | Q(version__icontains=query)
            | Q(comment__icontains=query)
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
            History.objects.create(host=host, fact=fact)
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
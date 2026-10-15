from django import forms
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import render

from .models import (
    Account,
    HardwareInfo,
    History,
    Host,
    Person,
    SIM,
    Software,
)


# ---------- Inline-блоки ----------

class AccountInlineForPerson(admin.TabularInline):
    model = Account
    fk_name = "person"
    extra = 0
    fields = ("kind", "login", "password", "host", "comment")


class AccountInlineForHost(admin.TabularInline):
    model = Account
    fk_name = "host"
    extra = 0
    fields = ("kind", "login", "password", "person", "comment")


class SIMInlineForPerson(admin.TabularInline):
    model = SIM
    fk_name = "person"
    extra = 0
    fields = ("full_number", "short_number", "icc", "apn", "host", "comment")


class SIMInlineForHost(admin.TabularInline):
    model = SIM
    fk_name = "host"
    extra = 0
    fields = ("full_number", "short_number", "icc", "apn", "person", "comment")


class HistoryInlineForPerson(admin.TabularInline):
    model = History
    fk_name = "person"
    extra = 0
    fields = ("created_at", "fact", "host")


class HistoryInlineForHost(admin.TabularInline):
    model = History
    fk_name = "host"
    extra = 0
    fields = ("created_at", "fact", "person")


class HardwareInfoInline(admin.StackedInline):
    model = HardwareInfo
    extra = 0
    max_num = 1
    can_delete = False
    fields = (
        "manufacturer",
        "cpu",
        "ram",
        "motherboard",
        "storage_type",
        "storage_capacity",
        "comment",
    )


# ---------- Форма для промежуточной страницы ----------

class CopyHardwareForm(forms.Form):
    source = forms.ModelChoiceField(
        queryset=Host.objects.all(),
        label="Хост-источник",
        help_text="Скопировать аппаратную часть с этого хоста",
    )
    overwrite = forms.BooleanField(
        required=False,
        initial=True,
        label="Перезаписать существующую аппаратную часть",
        help_text="Если снять галку, хосты с уже заполненной аппараткой будут пропущены",
    )


# ---------- Админки ----------

@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("full_name", "position", "phone_work")
    search_fields = ("full_name", "position", "phone_work")
    inlines = [AccountInlineForPerson, SIMInlineForPerson, HistoryInlineForPerson]


@admin.register(Host)
class HostAdmin(admin.ModelAdmin):
    list_display = (
        "domain_name",
        "kind",
        "ip_address",
        "mac_address",
        "users_list",
    )
    list_display_links = ("domain_name",)
    list_filter = ("kind",)
    search_fields = (
        "description",
        "ip_address",
        "mac_address",
        "domain_name",
        "hardware__manufacturer",
        "hardware__cpu",
        "users__full_name",
    )
    filter_horizontal = ("users", "softwares")
    inlines = [
        HardwareInfoInline,
        AccountInlineForHost,
        SIMInlineForHost,
        HistoryInlineForHost,
    ]
    actions = ["copy_hardware_from"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("users")

    @admin.display(description="Пользователи")
    def users_list(self, obj):
        names = [u.full_name for u in obj.users.all()]
        if not names:
            return "—"
        return ", ".join(names)

    @admin.action(description="Скопировать аппаратную часть с другого хоста")
    def copy_hardware_from(self, request, queryset):
        if request.POST.get("post"):
            form = CopyHardwareForm(request.POST)
            if form.is_valid():
                source = form.cleaned_data["source"]
                overwrite = form.cleaned_data["overwrite"]

                src_hw = HardwareInfo.objects.filter(host=source).first()
                if src_hw is None:
                    self.message_user(
                        request,
                        f"У хоста-источника «{source}» аппаратная часть не заполнена — копировать нечего.",
                        messages.ERROR,
                    )
                    return HttpResponseRedirect(request.get_full_path())

                created = updated = skipped = 0

                for host in queryset.exclude(pk=source.pk):
                    existing = HardwareInfo.objects.filter(host=host).first()
                    if existing is not None and not overwrite:
                        skipped += 1
                        continue

                    if existing is not None:
                        existing.manufacturer = src_hw.manufacturer
                        existing.cpu = src_hw.cpu
                        existing.ram = src_hw.ram
                        existing.motherboard = src_hw.motherboard
                        existing.storage_type = src_hw.storage_type
                        existing.storage_capacity = src_hw.storage_capacity
                        existing.comment = src_hw.comment
                        existing.save()
                        updated += 1
                    else:
                        HardwareInfo.objects.create(
                            host=host,
                            manufacturer=src_hw.manufacturer,
                            cpu=src_hw.cpu,
                            ram=src_hw.ram,
                            motherboard=src_hw.motherboard,
                            storage_type=src_hw.storage_type,
                            storage_capacity=src_hw.storage_capacity,
                            comment=src_hw.comment,
                        )
                        created += 1

                self.message_user(
                    request,
                    f"Готово. Создано: {created}. Обновлено: {updated}. Пропущено: {skipped}.",
                    messages.SUCCESS,
                )
                return HttpResponseRedirect(request.get_full_path())
        else:
            form = CopyHardwareForm()

        context = {
            **self.admin_site.each_context(request),
            "title": "Копирование аппаратной части",
            "form": form,
            "queryset": queryset,
            "opts": self.model._meta,
            "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
        }
        return render(request, "admin/inventory/host/copy_hardware.html", context)


@admin.register(HardwareInfo)
class HardwareInfoAdmin(admin.ModelAdmin):
    list_display = (
        "host",
        "manufacturer",
        "cpu",
        "ram",
        "motherboard",
        "storage_type",
        "storage_capacity",
    )
    list_filter = ("storage_type",)
    search_fields = (
        "host__domain_name",
        "host__ip_address",
        "manufacturer",
        "cpu",
        "ram",
        "motherboard",
        "storage_capacity",
    )


@admin.register(Software)
class SoftwareAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "comment")
    search_fields = ("name", "version", "comment")
    ordering = ("name", "version")


class AccountAdminForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = "__all__"
        widgets = {
            "password": forms.TextInput(attrs={"size": "40"}),
        }


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    form = AccountAdminForm
    list_display = ("login", "person", "host", "comment")
    list_display_links = ("login",)
    list_filter = ("kind",)
    search_fields = ("login", "person__full_name")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.person and obj.host:
            obj.host.users.add(obj.person)


@admin.register(SIM)
class SIMAdmin(admin.ModelAdmin):
    list_display = ("full_number", "short_number", "icc", "apn", "person", "host")
    search_fields = ("full_number", "short_number", "icc", "apn")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.person and obj.host:
            obj.host.users.add(obj.person)


@admin.register(History)
class HistoryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "host", "person", "fact")
    list_filter = ("host", "person")
    date_hierarchy = "created_at"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.person and obj.host:
            obj.host.users.add(obj.person)
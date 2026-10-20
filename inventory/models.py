from urllib.parse import quote

from django.db import models
from django.utils import timezone


class Software(models.Model):
    """Программное обеспечение (в том числе операционная система)."""

    name = models.CharField("Название", max_length=255)
    version = models.CharField("Версия", max_length=100, blank=True)
    comment = models.TextField("Комментарий", blank=True)

    class Meta:
        verbose_name = "ПО"
        verbose_name_plural = "ПО"
        ordering = ["name", "version"]
        unique_together = [("name", "version")]

    def __str__(self):
        if self.version:
            return f"{self.name} {self.version}"
        return self.name


class Person(models.Model):
    """Человек как пользователь хостов."""
    full_name = models.CharField("ФИО", max_length=255)
    position = models.CharField("Должность", max_length=255, blank=True)
    description = models.TextField("Описание", blank=True)
    phone_work = models.CharField("Рабочий телефон", max_length=50, blank=True)
    comment = models.TextField("Комментарий", blank=True)

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class Host(models.Model):
    """Любое устройство в сети, которому присвоен IP-адрес."""

    KIND_PC = "pc"
    KIND_VPC = "vpc"
    KIND_MINIPC = "minipc"
    KIND_LAPTOP = "laptop"
    KIND_CAMERA = "camera"
    KIND_BRIDGE = "bridge"
    KIND_NVR = "nvr"
    KIND_PLC = "plc"
    KIND_ROUTER = "router"
    KIND_SWITCH = "switch"
    KIND_SERVER = "server"
    KIND_OTHER = "other"

    KIND_CHOICES = [
        (KIND_PC, "Настольный ПК"),
        (KIND_VPC, "Виртуальный ПК (Windows)"),
        (KIND_MINIPC, "Мини ПК"),
        (KIND_LAPTOP, "Ноутбук"),
        (KIND_CAMERA, "IP-камера"),
        (KIND_BRIDGE, "Беспроводной мост"),
        (KIND_NVR, "IP-видеорегистратор"),
        (KIND_PLC, "Промышленный контроллер"),
        (KIND_ROUTER, "Wi-Fi роутер"),
        (KIND_SWITCH, "Коммутатор"),
        (KIND_SERVER, "Сервер"),
        (KIND_OTHER, "Другое"),
    ]

    TEAMVIEWER_KINDS = {KIND_PC, KIND_VPC, KIND_MINIPC, KIND_LAPTOP, KIND_SERVER}
    DESKTOP_ACCESS_KINDS = {KIND_PC, KIND_VPC}
    WEB_UI_KINDS = {KIND_CAMERA, KIND_BRIDGE}
    SSID_KINDS = {KIND_BRIDGE, KIND_ROUTER}

    description = models.CharField("Описание", max_length=255, blank=True)
    kind = models.CharField("Вид", max_length=20, choices=KIND_CHOICES, default=KIND_OTHER)
    domain_name = models.CharField("Доменное имя", max_length=255, blank=True)
    mac_address = models.CharField("MAC-адрес", max_length=17, blank=True)
    ssid = models.CharField("SSID", max_length=64, blank=True)
    comment = models.TextField("Комментарий", blank=True)

    users = models.ManyToManyField(
        Person,
        related_name="hosts",
        blank=True,
        verbose_name="Пользователи",
    )
    softwares = models.ManyToManyField(
        Software,
        related_name="hosts",
        blank=True,
        verbose_name="ОС и ПО",
    )

    class Meta:
        verbose_name = "Хост"
        verbose_name_plural = "Хосты"
        ordering = ["domain_name"]

    def __str__(self):
        return self.domain_name or f"Хост #{self.pk}"

    @property
    def primary_ip(self):
        ips = list(self.ip_addresses.all())
        if not ips:
            return None
        for ip in ips:
            if ip.is_primary:
                return ip.address
        return ips[0].address

    @property
    def supports_teamviewer(self):
        return self.kind in self.TEAMVIEWER_KINDS

    @property
    def supports_ssid(self):
        """Активно ли поле SSID для этого вида хоста."""
        return self.kind in self.SSID_KINDS

    def _desktop_share_data(self):
        if self.kind not in self.DESKTOP_ACCESS_KINDS:
            return None, None
        if not self.domain_name:
            return None, None

        user = self.users.first()
        if not user:
            return None, None

        account = (
            user.accounts.filter(kind=Account.KIND_DOMAIN).first()
            or user.accounts.first()
        )
        if not account or not account.login:
            return None, None

        return self.domain_name, account.login

    @property
    def supports_desktop_share(self):
        domain, login = self._desktop_share_data()
        return domain is not None and login is not None

    @property
    def desktop_unc_path(self):
        domain, login = self._desktop_share_data()
        if domain is None or login is None:
            return None
        return (
            f"\\\\{domain}"
            f"\\C$\\Пользователи"
            f"\\{login}"
            f"\\Рабочий стол"
        )

    @property
    def supports_web_ui(self):
        return self.kind in self.WEB_UI_KINDS

    @property
    def web_ui_url(self):
        if not self.supports_web_ui:
            return None
        ip = self.primary_ip
        if not ip:
            return None
        return f"http://{ip}/"

    def get_web_ui_autologin_url(self, login: str, password: str) -> str:
        if not self.supports_web_ui:
            return None
        ip = self.primary_ip
        if not ip:
            return None

        if self.kind == self.KIND_CAMERA:
            return (
                f"http://{ip}/dispatch.asp"
                f"?user={quote(login)}"
                f"&pass={quote(password)}"
                f"&page=preview.asp"
            )

        return (
            f"http://{ip}/"
            f"?user={quote(login)}"
            f"&pass={quote(password)}"
        )


class IPAddress(models.Model):
    """IP-адрес, принадлежащий хосту. У хоста может быть несколько адресов."""

    host = models.ForeignKey(
        Host,
        on_delete=models.CASCADE,
        related_name="ip_addresses",
        verbose_name="Хост",
    )
    address = models.GenericIPAddressField("IP-адрес", unique=True)
    is_primary = models.BooleanField("Основной", default=False)
    comment = models.CharField("Комментарий", max_length=255, blank=True)

    class Meta:
        verbose_name = "IP-адрес"
        verbose_name_plural = "IP-адреса"
        ordering = ["-is_primary", "address"]

    def __str__(self):
        return self.address

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_primary:
            IPAddress.objects.filter(
                host=self.host, is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)


class HardwareInfo(models.Model):
    STORAGE_SSD = "ssd"
    STORAGE_HDD = "hdd"
    STORAGE_NVME = "nvme"
    STORAGE_EMMC = "emmc"
    STORAGE_OTHER = "other"

    STORAGE_CHOICES = [
        (STORAGE_SSD, "SSD"),
        (STORAGE_HDD, "HDD"),
        (STORAGE_NVME, "NVMe"),
        (STORAGE_EMMC, "eMMC"),
        (STORAGE_OTHER, "Другое"),
    ]

    host = models.OneToOneField(
        Host,
        on_delete=models.CASCADE,
        related_name="hardware",
        verbose_name="Хост",
    )
    manufacturer = models.CharField("Производитель", max_length=255, blank=True)
    cpu = models.CharField("Процессор", max_length=255, blank=True)
    ram = models.CharField("ОЗУ", max_length=255, blank=True)
    motherboard = models.CharField("Материнская плата", max_length=255, blank=True)
    storage_type = models.CharField(
        "Тип накопителя",
        max_length=20,
        choices=STORAGE_CHOICES,
        blank=True,
    )
    storage_capacity = models.CharField("Ёмкость накопителя", max_length=50, blank=True)
    comment = models.TextField("Комментарий", blank=True)

    class Meta:
        verbose_name = "Аппаратная часть"
        verbose_name_plural = "Аппаратная часть"

    def __str__(self):
        parts = [p for p in (self.manufacturer, self.cpu) if p]
        return " / ".join(parts) if parts else f"Хост #{self.host_id}"


class Account(models.Model):
    KIND_HOST = "host"
    KIND_TERMINAL = "terminal"
    KIND_CLOUD = "cloud"
    KIND_DOMAIN = "domain"
    KIND_EMAIL = "email"
    KIND_TRASSIR = "trassir"
    KIND_SCADA = "scada"
    KIND_OTHER = "other"

    KIND_CHOICES = [
        (KIND_HOST, "Хост"),
        (KIND_TERMINAL, "Терминал"),
        (KIND_CLOUD, "Облако"),
        (KIND_DOMAIN, "Домен"),
        (KIND_EMAIL, "Email"),
        (KIND_TRASSIR, "Видеосервер Trassir"),
        (KIND_SCADA, "SCADA"),
        (KIND_OTHER, "Другое"),
    ]

    kind = models.CharField("Вид", max_length=20, choices=KIND_CHOICES, default=KIND_OTHER)
    login = models.CharField("Логин", max_length=255)
    password = models.CharField("Пароль", max_length=255, blank=True)
    comment = models.TextField("Комментарий", blank=True)

    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        related_name="accounts",
        verbose_name="Пользователь",
    )
    host = models.ForeignKey(
        Host,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accounts",
        verbose_name="Хост",
    )

    class Meta:
        verbose_name = "Учётная запись"
        verbose_name_plural = "Учётные записи"

    def __str__(self):
        return f"{self.get_kind_display()}: {self.login}"


class SIM(models.Model):
    full_number = models.CharField("Абонентский номер", max_length=32)
    short_number = models.CharField("Короткий номер", max_length=16, blank=True)
    icc = models.CharField("ICC", max_length=32, unique=True)
    apn = models.CharField("APN", max_length=100, default="internet")
    comment = models.TextField("Комментарий", blank=True)

    person = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sims",
        verbose_name="Пользователь",
    )
    host = models.ForeignKey(
        Host,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sims",
        verbose_name="Хост",
    )

    class Meta:
        verbose_name = "SIM-карта"
        verbose_name_plural = "SIM-карты"

    def __str__(self):
        return f"{self.full_number} (ICC {self.icc})"


class History(models.Model):
    fact = models.TextField("Факт")
    created_at = models.DateTimeField("Дата и время", default=timezone.now)

    host = models.ForeignKey(
        Host,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="history",
        verbose_name="Хост",
    )
    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="history",
        verbose_name="Пользователь",
    )

    class Meta:
        verbose_name = "Запись истории"
        verbose_name_plural = "История"
        ordering = ["-created_at"]

    def __str__(self):
        target = self.host or self.person or "—"
        return f"{self.created_at:%Y-%m-%d %H:%M} — {target}"
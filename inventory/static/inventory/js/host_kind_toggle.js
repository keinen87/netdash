(function () {
    "use strict";

    // Виды хостов, для которых поле ssid должно быть активно
    var SSID_KINDS = ["bridge", "router"];

    function updateSsidVisibility() {
        var kindSelect = document.getElementById("id_kind");
        var ssidInput = document.getElementById("id_ssid");
        if (!kindSelect || !ssidInput) return;

        // Найти ближайший родительский .form-row — стандартный контейнер поля в админке
        var row = ssidInput.closest(".form-row");
        if (!row) return;

        var selected = kindSelect.value;
        var active = SSID_KINDS.indexOf(selected) !== -1;

        if (active) {
            row.style.display = "";
            ssidInput.disabled = false;
        } else {
            row.style.display = "none";
            // Отключаем поле, чтобы при сохранении значение не перезаписалось
            // (или, если хотите сохранение старых SSID при смене типа — уберите эту строку)
            ssidInput.disabled = true;
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        var kindSelect = document.getElementById("id_kind");
        if (!kindSelect) return;

        kindSelect.addEventListener("change", updateSsidVisibility);
        updateSsidVisibility(); // применить сразу при загрузке
    });
})();
(function () {
    "use strict";

    // Соответствие: ID поля → список видов хостов, при которых поле активно
    var FIELD_KINDS = {
        "id_ssid": ["bridge", "router"],
        "id_serial_number": ["nvr"]
    };

    function updateFieldVisibility(inputId, kinds) {
        var kindSelect = document.getElementById("id_kind");
        var input = document.getElementById(inputId);
        if (!kindSelect || !input) return;

        var row = input.closest(".form-row");
        if (!row) return;

        var active = kinds.indexOf(kindSelect.value) !== -1;
        // Скрываем визуально, но не отключаем — значение сохраняется при смене типа
        row.style.display = active ? "" : "none";
    }

    function updateAll() {
        Object.keys(FIELD_KINDS).forEach(function (inputId) {
            updateFieldVisibility(inputId, FIELD_KINDS[inputId]);
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        var kindSelect = document.getElementById("id_kind");
        if (!kindSelect) return;

        kindSelect.addEventListener("change", updateAll);
        updateAll();
    });
})();
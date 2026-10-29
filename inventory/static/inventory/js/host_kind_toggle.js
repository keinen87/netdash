(function () {
    "use strict";

    // Поле в админке → виды хостов, при которых поле активно
    var FIELD_KINDS = {
        "id_ssid": ["bridge", "router"],
        "id_serial_number": ["nvr"],
        "id_config_file": ["gateway"]
    };

    function updateFieldVisibility(inputId, kinds) {
        var kindSelect = document.getElementById("id_kind");
        var input = document.getElementById(inputId);
        if (!kindSelect || !input) return;

        var row = input.closest(".form-row");
        if (!row) return;

        var active = kinds.indexOf(kindSelect.value) !== -1;
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
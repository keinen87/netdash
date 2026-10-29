(function () {
    "use strict";

    // Поле (по id) → массив видов хостов, при которых поле активно
    var FIELD_KINDS = {
        "id_ssid": ["bridge", "router"],
        "id_serial_number": ["nvr"],
        "id_config_file": ["gateway"]
    };

    // Находит контейнер поля для скрытия — работает в разных версиях Django
    function findFieldContainer(input) {
        // Стандартный Django admin до 5.x
        var row = input.closest(".form-row");
        if (row) return row;

        // Django 5.x/6.x: иногда контейнер называется .fieldBox
        row = input.closest(".fieldBox");
        if (row) return row;

        // Универсальный fallback — идём вверх по DOM до div, содержащего label
        var node = input.parentElement;
        var depth = 0;
        while (node && node !== document.body && depth < 12) {
            if (node.tagName === "DIV" && node.querySelector("label")) {
                return node;
            }
            node = node.parentElement;
            depth++;
        }

        // Последний резерв — хотя бы скроем сам input и его ближайшего родителя
        return input.parentElement;
    }

    function updateFieldVisibility(inputId, kinds) {
        var kindSelect = document.getElementById("id_kind");
        var input = document.getElementById(inputId);
        if (!kindSelect || !input) {
            // Поле отсутствует на странице — это нормально (inline, другие формы)
            return;
        }

        var container = findFieldContainer(input);
        if (!container) return;

        var active = kinds.indexOf(kindSelect.value) !== -1;

        if (active) {
            container.style.display = "";
            container.style.visibility = "";
        } else {
            // display:none + visibility:hidden — на случай, если CSS форсит display
            container.style.display = "none";
            container.style.visibility = "hidden";
        }
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

        console.log("[host_kind_toggle] initialized. Fields:", Object.keys(FIELD_KINDS));
    });
})();
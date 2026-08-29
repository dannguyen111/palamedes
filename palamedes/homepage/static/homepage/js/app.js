/* ============================================================
   Palamedes — app.js

   Replaces every Bootstrap JS component the app used to depend
   on. No jQuery, no popper, no framework. Everything is wired
   by data-attribute and delegated from document, so markup
   rendered later still works.
   ============================================================ */

(function () {
    "use strict";

    /* --------------------------------------------------------
       Theme
       The <head> script has already stamped data-theme before
       first paint. This only handles the toggle.
       -------------------------------------------------------- */

    function currentTheme() {
        var explicit = document.documentElement.getAttribute("data-theme");
        if (explicit) return explicit;
        return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }

    function setTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        try {
            localStorage.setItem("palamedes-theme", theme);
        } catch (e) {
            /* private browsing — the toggle still works for this page */
        }
        document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
            btn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
            var label = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
            btn.setAttribute("aria-label", label);
            btn.setAttribute("title", label);
        });
    }

    function initTheme() {
        setTheme(currentTheme());
    }

    /* --------------------------------------------------------
       Dropdowns
       -------------------------------------------------------- */

    function closeAllDropdowns(except) {
        document.querySelectorAll("[data-dropdown-toggle][aria-expanded='true']").forEach(function (t) {
            if (t === except) return;
            t.setAttribute("aria-expanded", "false");
            var menu = document.getElementById(t.getAttribute("aria-controls"));
            if (menu) menu.hidden = true;
        });
    }

    function toggleDropdown(toggle) {
        var menu = document.getElementById(toggle.getAttribute("aria-controls"));
        if (!menu) return;
        var open = toggle.getAttribute("aria-expanded") === "true";
        closeAllDropdowns(toggle);
        toggle.setAttribute("aria-expanded", open ? "false" : "true");
        menu.hidden = open;
        if (!open) {
            var first = menu.querySelector("a, button");
            if (first) first.focus();
        }
    }

    /* --------------------------------------------------------
       Tabs
       -------------------------------------------------------- */

    function selectTab(tab) {
        var list = tab.closest("[role='tablist']");
        if (!list) return;

        list.querySelectorAll("[role='tab']").forEach(function (t) {
            var selected = t === tab;
            t.setAttribute("aria-selected", selected ? "true" : "false");
            t.setAttribute("tabindex", selected ? "0" : "-1");
            var panel = document.getElementById(t.getAttribute("aria-controls"));
            if (panel) panel.hidden = !selected;
        });
    }

    function initTabs() {
        document.querySelectorAll("[role='tablist']").forEach(function (list) {
            var tabs = Array.prototype.slice.call(list.querySelectorAll("[role='tab']"));
            if (!tabs.length) return;

            list.addEventListener("keydown", function (e) {
                var i = tabs.indexOf(document.activeElement);
                if (i === -1) return;
                var next = null;

                if (e.key === "ArrowRight") next = tabs[(i + 1) % tabs.length];
                else if (e.key === "ArrowLeft") next = tabs[(i - 1 + tabs.length) % tabs.length];
                else if (e.key === "Home") next = tabs[0];
                else if (e.key === "End") next = tabs[tabs.length - 1];

                if (next) {
                    e.preventDefault();
                    selectTab(next);
                    next.focus();
                }
            });
        });
    }

    /* --------------------------------------------------------
       Dialogs

       One dialog serves many triggers. The trigger carries the
       row's values as data-field-* and we write them into the
       matching [data-field] targets before opening. That is what
       lets the points log render one dialog instead of one per
       table row.
       -------------------------------------------------------- */

    function openDialog(trigger) {
        var dialog = document.getElementById(trigger.getAttribute("data-dialog-open"));
        if (!dialog) return;

        Object.keys(trigger.dataset).forEach(function (key) {
            if (key.indexOf("field") !== 0 || key === "field") return;
            // dataset key "fieldReason" -> field name "reason"
            var name = key.slice(5);
            name = name.charAt(0).toLowerCase() + name.slice(1);
            var value = trigger.dataset[key];

            dialog.querySelectorAll("[data-field='" + name + "']").forEach(function (target) {
                if ("value" in target && target.tagName !== "OPTION") target.value = value;
                else target.textContent = value;
            });
        });

        var action = trigger.getAttribute("data-dialog-action");
        if (action) {
            var form = dialog.querySelector("form");
            if (form) form.setAttribute("action", action);
        }

        if (typeof dialog.showModal === "function") dialog.showModal();
        else dialog.setAttribute("open", "");

        var focusTarget = dialog.querySelector("[data-autofocus], input:not([type='hidden']), textarea, select");
        if (focusTarget) focusTarget.focus();
    }

    function closeDialog(dialog) {
        if (!dialog) return;
        if (typeof dialog.close === "function") dialog.close();
        else dialog.removeAttribute("open");
    }

    /* --------------------------------------------------------
       Alerts + toasts
       -------------------------------------------------------- */

    function dismiss(el) {
        if (!el) return;
        el.style.transition = "opacity 120ms";
        el.style.opacity = "0";
        window.setTimeout(function () {
            el.remove();
        }, 120);
    }

    function toastRegion() {
        var region = document.getElementById("toasts");
        if (!region) {
            region = document.createElement("div");
            region.id = "toasts";
            region.className = "toasts";
            region.setAttribute("role", "status");
            region.setAttribute("aria-live", "polite");
            document.body.appendChild(region);
        }
        return region;
    }

    function toast(message, kind) {
        var region = toastRegion();
        var el = document.createElement("div");
        el.className = "alert alert--" + (kind || "info");

        var body = document.createElement("div");
        body.className = "alert__body";
        body.textContent = message;

        var close = document.createElement("button");
        close.type = "button";
        close.className = "alert__close";
        close.setAttribute("data-dismiss", "");
        close.setAttribute("aria-label", "Dismiss");
        close.textContent = "×";

        el.appendChild(body);
        el.appendChild(close);
        region.appendChild(el);

        window.setTimeout(function () {
            dismiss(el);
        }, 5000);
    }

    /* --------------------------------------------------------
       Bulk selection + mass email

       Previously ~65 lines copy-pasted verbatim into both
       directory.html and unpaid_directory.html.
       -------------------------------------------------------- */

    /* A selection is scoped to its own form or [data-select-scope], so the
       dues list and the member directory never see each other's boxes. */
    /* Falls back to body, not document — document has no getAttribute, and
       every caller reads data-select-noun off whatever comes back. */
    function scopeOf(el) {
        return el.closest("[data-select-scope]") || el.closest("form") || document.body;
    }

    function boxesIn(scope) {
        return Array.prototype.slice.call(
            scope.querySelectorAll("[data-selectable]:not(:disabled)")
        );
    }

    function syncScope(scope) {
        var boxes = boxesIn(scope);
        var chosen = boxes.filter(function (b) { return b.checked; });
        var count = chosen.length;
        var noun = scope.getAttribute("data-select-noun") || "item";

        var label = scope.querySelector("[data-bulk-count]");
        if (label) {
            label.textContent = count + " " + noun + (count === 1 ? "" : "s") + " selected";
        }

        var bar = scope.querySelector("[data-bulk-bar]");
        if (bar) bar.hidden = count === 0;

        scope.querySelectorAll("[data-bulk-action]").forEach(function (btn) {
            btn.disabled = count === 0;
        });

        var toggle = scope.querySelector("[data-select-all]");
        if (toggle) {
            toggle.textContent = count > 0 && count === boxes.length ? "Clear selection" : "Select all";
        }
    }

    function syncAllScopes() {
        var scopes = document.querySelectorAll("[data-select-scope], form");
        Array.prototype.forEach.call(scopes, function (s) {
            if (s.querySelector("[data-selectable]")) syncScope(s);
        });
    }

    function selectAll(toggle) {
        var scope = scopeOf(toggle);
        var boxes = boxesIn(scope);
        var allChecked = boxes.length > 0 && boxes.every(function (b) { return b.checked; });
        boxes.forEach(function (b) { b.checked = !allChecked; });
        syncScope(scope);
    }

    function massEmail(trigger) {
        var scope = scopeOf(trigger);
        var emails = boxesIn(scope)
            .filter(function (b) { return b.checked; })
            .map(function (b) { return b.getAttribute("data-email"); })
            .filter(Boolean);

        if (!emails.length) {
            toast("Select at least one member to email.", "warning");
            return;
        }

        var list = emails.join(",");

        function open() {
            window.location.href = "mailto:?bcc=" + encodeURIComponent(list);
        }

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(list).then(
                function () {
                    toast(emails.length + " addresses copied to your clipboard.", "success");
                    open();
                },
                open
            );
        } else {
            open();
        }
    }

    /* --------------------------------------------------------
       Delegated events
       -------------------------------------------------------- */

    document.addEventListener("click", function (e) {
        var el;

        if ((el = e.target.closest("[data-theme-toggle]"))) {
            e.preventDefault();
            setTheme(currentTheme() === "dark" ? "light" : "dark");
            return;
        }

        if ((el = e.target.closest("[data-dropdown-toggle]"))) {
            e.preventDefault();
            toggleDropdown(el);
            return;
        }

        if ((el = e.target.closest("[role='tab']"))) {
            e.preventDefault();
            selectTab(el);
            return;
        }

        if ((el = e.target.closest("[data-dialog-open]"))) {
            e.preventDefault();
            openDialog(el);
            return;
        }

        if ((el = e.target.closest("[data-dialog-close]"))) {
            e.preventDefault();
            closeDialog(el.closest("dialog"));
            return;
        }

        if ((el = e.target.closest("[data-dismiss]"))) {
            e.preventDefault();
            dismiss(el.closest(".alert"));
            return;
        }

        if ((el = e.target.closest("[data-select-all]"))) {
            e.preventDefault();
            selectAll(el);
            return;
        }

        if ((el = e.target.closest("[data-mass-email]"))) {
            e.preventDefault();
            massEmail(el);
            return;
        }

        // Click outside an open dropdown closes it.
        if (!e.target.closest(".dropdown")) closeAllDropdowns();
    });

    document.addEventListener("change", function (e) {
        if (e.target.matches && e.target.matches("[data-selectable]")) {
            syncScope(scopeOf(e.target));
        }
    });

    document.addEventListener("keydown", function (e) {
        if (e.key !== "Escape") return;

        var open = document.querySelector("[data-dropdown-toggle][aria-expanded='true']");
        if (open) {
            closeAllDropdowns();
            open.focus();
        }
    });

    /* Clicking the backdrop of a native dialog closes it. */
    document.addEventListener("click", function (e) {
        if (e.target.tagName !== "DIALOG") return;
        var box = e.target.getBoundingClientRect();
        var outside =
            e.clientX < box.left || e.clientX > box.right ||
            e.clientY < box.top || e.clientY > box.bottom;
        if (outside) closeDialog(e.target);
    });

    /* --------------------------------------------------------
       Boot
       -------------------------------------------------------- */

    function init() {
        initTheme();
        initTabs();
        syncAllScopes();

        // Django messages auto-dismiss, matching the toast behaviour.
        document.querySelectorAll("[data-autodismiss]").forEach(function (el) {
            window.setTimeout(function () { dismiss(el); }, 6000);
        });

        // Disable submit buttons on send so a slow POST can't be
        // double-submitted. Registration used to do this inline.
        document.querySelectorAll("form[data-guard]").forEach(function (form) {
            form.addEventListener("submit", function () {
                form.querySelectorAll("button[type='submit']").forEach(function (btn) {
                    btn.disabled = true;
                    if (btn.dataset.busyLabel) btn.textContent = btn.dataset.busyLabel;
                });
            });
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }

    window.Palamedes = { toast: toast };
})();

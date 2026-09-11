(function () {
  function overlay() {
    return document.getElementById("compose-overlay");
  }

  function setDisabled(root, disabled) {
    root.querySelectorAll("input, select, textarea, button[type=submit]").forEach(function (field) {
      field.disabled = disabled;
    });
  }

  function setKind(kind) {
    var root = overlay();
    if (!root) {
      return;
    }
    kind = kind === "event" ? "event" : "task";
    root.setAttribute("data-kind", kind);
    root.querySelectorAll("[data-compose-kind]").forEach(function (panel) {
      var on = panel.getAttribute("data-compose-kind") === kind;
      panel.hidden = !on;
      setDisabled(panel, !on);
    });
    root.querySelectorAll("[data-compose-tab]").forEach(function (tab) {
      var on = tab.getAttribute("data-compose-tab") === kind;
      tab.classList.toggle("compose-type-on", on);
      tab.setAttribute("aria-selected", on ? "true" : "false");
    });
    toggleAllDay();
  }

  function fill(id, value) {
    var el = document.getElementById(id);
    if (el) {
      el.value = value || "";
    }
  }

  function toggleAllDay() {
    var root = overlay();
    if (!root) {
      return;
    }
    var box = root.querySelector('input[name="all_day"]');
    var on = !!(box && box.checked);
    root.querySelectorAll("[data-compose-timed]").forEach(function (el) {
      el.hidden = on;
    });
  }

  function openCompose(detail) {
    var d = detail;
    if (typeof d === "string") {
      d = { kind: "task", status: d };
    }
    if (!d || typeof d !== "object") {
      d = {};
    }
    var root = overlay();
    if (!root) {
      return;
    }
    var kind = d.kind === "event" ? "event" : "task";
    var today = root.getAttribute("data-today") || "";
    var date = d.date || (kind === "event" ? today : "");
    var time = d.time || (kind === "event" ? "09:00" : "");
    setKind(kind);
    var status = document.getElementById("compose-status");
    if (status) {
      status.value = d.status || "todo";
    }
    fill("compose-due-date", date);
    fill("compose-due-time", time);
    fill("event-start-date", date || today);
    fill("event-end-date", d.endDate || date || today);
    fill("event-start-time", time || "09:00");
    fill("event-end-time", d.endTime || "");
    fill("compose-title", d.title || "");
    fill("event-title", d.title || "");
    fill("compose-description", "");
    fill("event-description", "");
    var allDay = root.querySelector('input[name="all_day"]');
    if (allDay) {
      allDay.checked = !!d.allDay;
    }
    toggleAllDay();
    root.classList.add("compose-open");
    root.setAttribute("aria-hidden", "false");
    var focusId = kind === "event" ? "event-title" : "compose-title";
    var focusEl = document.getElementById(focusId);
    if (focusEl) {
      focusEl.focus();
    }
  }

  function closeCompose() {
    var root = overlay();
    if (!root) {
      return;
    }
    root.classList.remove("compose-open");
    root.setAttribute("aria-hidden", "true");
  }

  window.agoraCompose = openCompose;
  window.agoraComposeClose = closeCompose;

  function mount() {
    var root = overlay();
    if (root && root.parentNode !== document.body) {
      document.body.appendChild(root);
    }
    (window.__agoraComposeQ || []).splice(0).forEach(openCompose);
  }

  document.addEventListener("click", function (event) {
    var root = overlay();
    if (!root || !root.classList.contains("compose-open")) {
      return;
    }
    var tab = event.target.closest("[data-compose-tab]");
    if (tab) {
      event.preventDefault();
      setKind(tab.getAttribute("data-compose-tab"));
      return;
    }
    if (event.target.closest("[data-compose-close]")) {
      event.preventDefault();
      closeCompose();
      return;
    }
    if (event.target.id === "compose-overlay") {
      closeCompose();
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closeCompose();
    }
  });

  document.addEventListener("change", function (event) {
    if (event.target && event.target.name === "all_day") {
      toggleAllDay();
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();

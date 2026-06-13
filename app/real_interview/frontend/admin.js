(function () {
  "use strict";

  function $(id) {
    return document.getElementById(id);
  }

  function showElement(el, visible) {
    if (!el) return;
    if (visible) {
      el.classList.remove("is-hidden");
      el.removeAttribute("hidden");
    } else {
      el.classList.add("is-hidden");
      el.setAttribute("hidden", "");
    }
  }

  function hideAllViews() {
    showElement($("view-admin-login"), false);
    showElement($("view-admin-denied"), false);
    showElement($("view-admin-dashboard"), false);
  }

  function setMessage(el, text, kind) {
    if (!el) return;
    el.textContent = text || "";
    el.classList.remove("is-error", "is-ok");
    if (kind === "error") el.classList.add("is-error");
    if (kind === "ok") el.classList.add("is-ok");
  }

  function apiGet(url) {
    return fetch(url, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    }).then(function (res) {
      return res.json().then(function (data) {
        return { ok: res.ok, status: res.status, data: data };
      });
    });
  }

  function apiJson(url, body) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    }).then(function (res) {
      return res.json().then(function (data) {
        return { ok: res.ok, status: res.status, data: data };
      });
    });
  }

  function formatDate(iso) {
    if (!iso) return "—";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString();
  }

  function statusLabel(status) {
    var map = {
      active: "In progress",
      paused: "Paused",
      completed: "Completed",
    };
    return map[status] || status || "—";
  }

  function renderMetrics(metrics) {
    var container = $("admin-metrics");
    if (!container || !metrics) return;
    container.textContent = "";

    var users = metrics.users || {};
    var interviews = metrics.interviews || {};

    var cards = [
      { label: "Total users", value: users.total },
      { label: "New today", value: users.new_today },
      { label: "New (7 days)", value: users.new_last_7_days },
      { label: "New (period)", value: users.new_in_period },
      { label: "Interviews total", value: interviews.total },
      { label: "In progress", value: interviews.active },
      { label: "Paused", value: interviews.paused },
      { label: "Completed", value: interviews.completed },
      { label: "Not started", value: interviews.not_started },
      { label: "Interviews (period)", value: interviews.in_period },
      { label: "Resumes uploaded", value: metrics.resumes_total },
      { label: "Job applications", value: metrics.job_applications_total },
    ];

    cards.forEach(function (item) {
      var card = document.createElement("div");
      card.className = "metric-card";
      var label = document.createElement("div");
      label.className = "metric-label";
      label.textContent = item.label;
      var value = document.createElement("div");
      value.className = "metric-value";
      value.textContent = item.value != null ? String(item.value) : "0";
      card.appendChild(label);
      card.appendChild(value);
      container.appendChild(card);
    });
  }

  function renderSignups(rows) {
    var tbody = $("admin-signups-body");
    if (!tbody) return;
    tbody.textContent = "";
    (rows || []).forEach(function (row) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        (row.email || "—") +
        "</td><td>" +
        formatDate(row.created_at) +
        "</td><td><code>" +
        (row.user_id || "—") +
        "</code></td>";
      tbody.appendChild(tr);
    });
    if (!rows || !rows.length) {
      var empty = document.createElement("tr");
      empty.innerHTML = '<td colspan="3" class="hint">No signups yet.</td>';
      tbody.appendChild(empty);
    }
  }

  function renderInterviews(rows) {
    var tbody = $("admin-interviews-body");
    if (!tbody) return;
    tbody.textContent = "";
    (rows || []).forEach(function (row) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        (row.candidate_email || row.candidate_id || "—") +
        "</td><td>" +
        (row.role_applied_for || "—") +
        "</td><td><span class=\"status-pill status-" +
        (row.interview_status || "active") +
        "\">" +
        statusLabel(row.interview_status) +
        "</span></td><td>" +
        (row.message_count != null ? row.message_count : "0") +
        "</td><td>" +
        formatDate(row.interview_date) +
        "</td>";
      tbody.appendChild(tr);
    });
    if (!rows || !rows.length) {
      var empty = document.createElement("tr");
      empty.innerHTML = '<td colspan="5" class="hint">No interviews yet.</td>';
      tbody.appendChild(empty);
    }
  }

  function loadDashboard() {
    var days = ($("admin-period-days") && $("admin-period-days").value) || "30";
    var msg = $("admin-dash-message");
    setMessage(msg, "Loading…", "ok");

    return apiGet("/api/admin/dashboard?days=" + encodeURIComponent(days) + "&limit=50").then(function (r) {
      if (!r.ok) {
        setMessage(msg, r.data.error || "Could not load dashboard.", "error");
        return;
      }
      setMessage(msg, "", "");
      var generated = $("admin-generated-at");
      if (generated) {
        generated.textContent = "Updated " + formatDate(r.data.generated_at);
      }
      renderMetrics(r.data.metrics);
      renderSignups(r.data.recent_signups);
      renderInterviews(r.data.recent_interviews);
    });
  }

  function showDashboard(email) {
    hideAllViews();
    showElement($("view-admin-dashboard"), true);
    var emailEl = $("admin-user-email");
    if (emailEl) emailEl.textContent = email || "";
    loadDashboard();
  }

  function showDenied(email) {
    hideAllViews();
    showElement($("view-admin-denied"), true);
    var emailEl = $("admin-denied-email");
    if (emailEl) emailEl.textContent = email || "";
  }

  function showLogin() {
    hideAllViews();
    showElement($("view-admin-login"), true);
  }

  function signOut() {
    return apiJson("/api/users/logout", {}).finally(function () {
      showLogin();
    });
  }

  function checkAccess() {
    return apiGet("/api/users/me").then(function (me) {
      if (!me.ok || !me.data.user_id) {
        showLogin();
        return;
      }
      return apiGet("/api/admin/access").then(function (access) {
        if (access.ok && access.data.is_admin) {
          showDashboard(access.data.email || me.data.email);
        } else {
          showDenied(me.data.email || access.data.email);
        }
      });
    });
  }

  function wireLogin() {
    var form = $("form-admin-login");
    if (!form) return;
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var fd = new FormData(form);
      var email = (fd.get("email") || "").toString().trim();
      var password = (fd.get("password") || "").toString();
      var msg = $("admin-login-message");
      setMessage(msg, "", "");

      apiJson("/api/users/login", { email: email, password: password })
        .then(function (r) {
          if (!r.ok) {
            setMessage(msg, r.data.error || "Log in failed.", "error");
            return;
          }
          checkAccess();
        })
        .catch(function () {
          setMessage(msg, "Network error. Try again.", "error");
        });
    });
  }

  function boot() {
    wireLogin();
    var refresh = $("btn-admin-refresh");
    if (refresh) {
      refresh.addEventListener("click", function () {
        loadDashboard();
      });
    }
    var period = $("admin-period-days");
    if (period) {
      period.addEventListener("change", function () {
        loadDashboard();
      });
    }
    var signOutBtn = $("btn-admin-sign-out");
    if (signOutBtn) signOutBtn.addEventListener("click", signOut);
    var signOutDenied = $("btn-admin-sign-out-denied");
    if (signOutDenied) signOutDenied.addEventListener("click", signOut);

    checkAccess().catch(function () {
      showLogin();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();

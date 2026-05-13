(function () {
  "use strict";

  var STORAGE_KEY = "ri_user_id";

  function $(id) {
    return document.getElementById(id);
  }

  function getStoredUserId() {
    try {
      return sessionStorage.getItem(STORAGE_KEY) || "";
    } catch (e) {
      return "";
    }
  }

  function setStoredUserId(id) {
    try {
      if (id) sessionStorage.setItem(STORAGE_KEY, id);
      else sessionStorage.removeItem(STORAGE_KEY);
    } catch (e) {
      /* ignore */
    }
  }

  function showAuthView() {
    $("view-auth").classList.remove("is-hidden");
    $("view-auth").removeAttribute("hidden");
    $("view-upload").classList.add("is-hidden");
    $("view-upload").setAttribute("hidden", "");
    $("upload-result").classList.add("is-hidden");
    $("upload-result").textContent = "";
  }

  function showUploadView(userId) {
    $("view-auth").classList.add("is-hidden");
    $("view-auth").setAttribute("hidden", "");
    $("view-upload").classList.remove("is-hidden");
    $("view-upload").removeAttribute("hidden");
    $("display-user-id").textContent = userId;
    clearMessage($("auth-message"));
    clearMessage($("upload-message"));
  }

  function clearMessage(el) {
    el.textContent = "";
    el.classList.remove("is-error", "is-ok");
  }

  function setMessage(el, text, kind) {
    el.textContent = text || "";
    el.classList.remove("is-error", "is-ok");
    if (kind === "error") el.classList.add("is-error");
    if (kind === "ok") el.classList.add("is-ok");
  }

  function apiJson(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    }).then(function (res) {
      return res.json().then(function (data) {
        return { ok: res.ok, status: res.status, data: data };
      });
    });
  }

  function initTabs() {
    var tabs = document.querySelectorAll(".tab");
    var panelSignup = $("panel-signup");
    var panelLogin = $("panel-login");

    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        var name = tab.getAttribute("data-tab");
        tabs.forEach(function (t) {
          var active = t === tab;
          t.classList.toggle("is-active", active);
          t.setAttribute("aria-selected", active ? "true" : "false");
        });
        if (name === "signup") {
          panelSignup.classList.remove("is-hidden");
          panelSignup.removeAttribute("hidden");
          panelLogin.classList.add("is-hidden");
          panelLogin.setAttribute("hidden", "");
        } else {
          panelLogin.classList.remove("is-hidden");
          panelLogin.removeAttribute("hidden");
          panelSignup.classList.add("is-hidden");
          panelSignup.setAttribute("hidden", "");
        }
        clearMessage($("auth-message"));
      });
    });
  }

  function wireSignup() {
    $("form-signup").addEventListener("submit", function (ev) {
      ev.preventDefault();
      var fd = new FormData(ev.target);
      var email = (fd.get("email") || "").toString().trim();
      var password = (fd.get("password") || "").toString();
      var confirm_password = (fd.get("confirm_password") || "").toString();
      var msg = $("auth-message");
      clearMessage(msg);

      apiJson("/api/users", { email: email, password: password, confirm_password: confirm_password })
        .then(function (r) {
          if (r.ok && r.data.user_id) {
            setStoredUserId(r.data.user_id);
            setMessage(msg, r.data.message || "Account created.", "ok");
            showUploadView(r.data.user_id);
          } else {
            var err = r.data.error || r.data.message || "Sign up failed.";
            setMessage(msg, err, "error");
          }
        })
        .catch(function () {
          setMessage(msg, "Network error. Try again.", "error");
        });
    });
  }

  function wireLogin() {
    $("form-login").addEventListener("submit", function (ev) {
      ev.preventDefault();
      var fd = new FormData(ev.target);
      var email = (fd.get("email") || "").toString().trim();
      var password = (fd.get("password") || "").toString();
      var msg = $("auth-message");
      clearMessage(msg);

      apiJson("/api/users/login", { email: email, password: password })
        .then(function (r) {
          if (r.ok && r.data.user_id) {
            setStoredUserId(r.data.user_id);
            setMessage(msg, r.data.message || "Signed in.", "ok");
            showUploadView(r.data.user_id);
          } else {
            var err = r.data.error || "Log in failed.";
            setMessage(msg, err, "error");
          }
        })
        .catch(function () {
          setMessage(msg, "Network error. Try again.", "error");
        });
    });
  }

  function wireUpload() {
    $("form-upload").addEventListener("submit", function (ev) {
      ev.preventDefault();
      var userId = getStoredUserId();
      var msg = $("upload-message");
      var out = $("upload-result");
      clearMessage(msg);
      out.classList.add("is-hidden");
      out.textContent = "";

      if (!userId) {
        setMessage(msg, "Session missing. Please sign in again.", "error");
        showAuthView();
        return;
      }

      var input = ev.target.querySelector('input[type="file"]');
      if (!input || !input.files || !input.files[0]) {
        setMessage(msg, "Choose a PDF file.", "error");
        return;
      }

      var fd = new FormData();
      fd.append("userid", userId);
      fd.append("resume", input.files[0], input.files[0].name);

      var btn = ev.target.querySelector('button[type="submit"]');
      btn.disabled = true;

      fetch("/api/resumes", { method: "POST", body: fd })
        .then(function (res) {
          return res.json().then(function (data) {
            return { ok: res.ok, status: res.status, data: data };
          });
        })
        .then(function (r) {
          if (r.ok) {
            setMessage(msg, r.data.message || "Upload complete.", "ok");
            out.textContent = JSON.stringify(r.data, null, 2);
            out.classList.remove("is-hidden");
            ev.target.reset();
          } else {
            setMessage(msg, r.data.error || "Upload failed.", "error");
          }
        })
        .catch(function () {
          setMessage(msg, "Network error. Try again.", "error");
        })
        .finally(function () {
          btn.disabled = false;
        });
    });
  }

  function wireSignOut() {
    $("btn-sign-out").addEventListener("click", function () {
      setStoredUserId("");
      showAuthView();
    });
  }

  function boot() {
    initTabs();
    wireSignup();
    wireLogin();
    wireUpload();
    wireSignOut();

    var uid = getStoredUserId();
    if (uid) showUploadView(uid);
    else showAuthView();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();

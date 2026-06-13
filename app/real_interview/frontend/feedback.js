(function () {
  "use strict";

  function $(id) {
    return document.getElementById(id);
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

  function prefillSignedInEmail() {
    apiGet("/api/users/me").then(function (r) {
      if (!r.ok || !r.data || !r.data.email) return;
      var input = document.querySelector('#form-feedback input[name="contact_email"]');
      if (input && !input.value) input.value = r.data.email;
    });
  }

  var form = $("form-feedback");
  if (form) {
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var msgEl = $("feedback-message");
      setMessage(msgEl, "", null);

      var fd = new FormData(form);
      var message = (fd.get("message") || "").toString().trim();
      var contactEmail = (fd.get("contact_email") || "").toString().trim();
      var category = (fd.get("category") || "general").toString().trim();

      if (message.length < 10) {
        setMessage(msgEl, "Please write at least 10 characters.", "error");
        return;
      }

      var btn = form.querySelector('button[type="submit"]');
      if (btn) btn.disabled = true;

      apiJson("/api/feedback", {
        message: message,
        contact_email: contactEmail,
        category: category,
      })
        .then(function (r) {
          if (r.ok) {
            setMessage(msgEl, r.data.message || "Thank you — your feedback was sent.", "ok");
            form.reset();
            prefillSignedInEmail();
            return;
          }
          if (r.status === 429) {
            setMessage(msgEl, "Too many submissions. Please try again later.", "error");
            return;
          }
          if (r.status === 503) {
            setMessage(msgEl, "Feedback is temporarily unavailable. Please try again later.", "error");
            return;
          }
          setMessage(msgEl, (r.data && r.data.error) || "Could not send feedback.", "error");
        })
        .catch(function () {
          setMessage(msgEl, "Network error. Please try again.", "error");
        })
        .finally(function () {
          if (btn) btn.disabled = false;
        });
    });
  }

  prefillSignedInEmail();
})();

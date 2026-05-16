(function () {
  "use strict";

  var STORAGE_KEY_USER_ID = "ri_user_id";
  var STORAGE_KEY_EMAIL = "ri_user_email";
  var STORAGE_KEY_RESUME_ID = "ri_resume_id";
  var STORAGE_KEY_RESUME_PARSED = "ri_resume_parsed";
  var JOB_MODE_LINK = "link";
  var JOB_MODE_DESCRIPTION = "description";

  function $(id) {
    return document.getElementById(id);
  }

  function getStoredUserId() {
    try {
      return sessionStorage.getItem(STORAGE_KEY_USER_ID) || "";
    } catch (e) {
      return "";
    }
  }

  function getStoredUserEmail() {
    try {
      return sessionStorage.getItem(STORAGE_KEY_EMAIL) || "";
    } catch (e) {
      return "";
    }
  }

  function setStoredSession(userId, email) {
    try {
      if (userId) sessionStorage.setItem(STORAGE_KEY_USER_ID, userId);
      else sessionStorage.removeItem(STORAGE_KEY_USER_ID);
      if (email) sessionStorage.setItem(STORAGE_KEY_EMAIL, email);
      else sessionStorage.removeItem(STORAGE_KEY_EMAIL);
      if (!userId) clearStoredResume();
    } catch (e) {
      /* ignore */
    }
  }

  function getStoredResumeId() {
    try {
      return sessionStorage.getItem(STORAGE_KEY_RESUME_ID) || "";
    } catch (e) {
      return "";
    }
  }

  function clearStoredResume() {
    try {
      sessionStorage.removeItem(STORAGE_KEY_RESUME_ID);
      sessionStorage.removeItem(STORAGE_KEY_RESUME_PARSED);
    } catch (e) {
      /* ignore */
    }
  }

  function setStoredResume(resumeId, parsedData) {
    try {
      if (resumeId) sessionStorage.setItem(STORAGE_KEY_RESUME_ID, resumeId);
      else sessionStorage.removeItem(STORAGE_KEY_RESUME_ID);
      if (parsedData) {
        sessionStorage.setItem(STORAGE_KEY_RESUME_PARSED, JSON.stringify(parsedData));
      } else {
        sessionStorage.removeItem(STORAGE_KEY_RESUME_PARSED);
      }
    } catch (e) {
      /* ignore */
    }
  }

  function formatResumeDate(isoString) {
    if (!isoString) return "";
    var d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleString();
  }

  function apiGet(url) {
    return fetch(url, { headers: { Accept: "application/json" } }).then(function (res) {
      return res.json().then(function (data) {
        return { ok: res.ok, status: res.status, data: data };
      });
    });
  }

  function hideView(viewId) {
    var el = $(viewId);
    if (!el) return;
    el.classList.add("is-hidden");
    el.setAttribute("hidden", "");
  }

  function showView(viewId) {
    var el = $(viewId);
    if (!el) return;
    el.classList.remove("is-hidden");
    el.removeAttribute("hidden");
  }

  function setSignedInEmail(email) {
    var value = email || "";
    $("display-user-email").textContent = value;
    var jobDisplay = $("display-user-email-job");
    if (jobDisplay) jobDisplay.textContent = value;
  }

  function showAuthView() {
    hideView("view-upload");
    hideView("view-job-application");
    showView("view-auth");
    clearMessage($("upload-message"));
    clearMessage($("job-message"));
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

  function applySelectedResumeToUi(parsedData, resumeId) {
    var wrap = $("resume-selected-wrap");
    var textarea = $("resume-parsed-display");
    var continueBtn = $("btn-continue-job");
    if (textarea) {
      textarea.value = JSON.stringify(parsedData || {}, null, 2);
    }
    showElement(wrap, true);
    showElement(continueBtn, true);
    if (resumeId) {
      var rows = document.querySelectorAll("#resume-table-body tr");
      rows.forEach(function (row) {
        row.classList.toggle("is-selected", row.getAttribute("data-resume-id") === resumeId);
      });
    }
  }

  function restoreResumeSelectionFromSession() {
    var resumeId = getStoredResumeId();
    if (!resumeId) return;
    try {
      var raw = sessionStorage.getItem(STORAGE_KEY_RESUME_PARSED);
      if (raw) {
        applySelectedResumeToUi(JSON.parse(raw), resumeId);
      }
    } catch (e) {
      /* ignore */
    }
  }

  function showUploadView(email) {
    hideView("view-auth");
    hideView("view-job-application");
    showView("view-upload");
    setSignedInEmail(email);
    clearMessage($("auth-message"));
    clearMessage($("upload-message"));
    restoreResumeSelectionFromSession();
  }

  function showJobApplicationView(email) {
    hideView("view-auth");
    hideView("view-upload");
    showView("view-job-application");
    setSignedInEmail(email);
    clearMessage($("auth-message"));
    clearMessage($("upload-message"));
    clearMessage($("job-message"));
    var out = $("job-result");
    if (out) {
      out.classList.add("is-hidden");
      out.textContent = "";
    }
  }

  function clearMessage(el) {
    if (!el) return;
    el.textContent = "";
    el.classList.remove("is-error", "is-ok");
  }

  function setMessage(el, text, kind) {
    if (!el) return;
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
    var tabs = document.querySelectorAll(".tab:not(.job-mode-tab)");
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

  function getActiveJobInputMode() {
    var active = document.querySelector(".job-mode-tab.is-active");
    return active ? active.getAttribute("data-job-mode") : JOB_MODE_LINK;
  }

  function setJobInputMode(mode) {
    var tabs = document.querySelectorAll(".job-mode-tab");
    var panelLink = $("panel-job-link");
    var panelDescription = $("panel-job-description");
    var linkInput = document.querySelector('#panel-job-link input[name="application_link"]');
    var descInput = document.querySelector('#panel-job-description textarea[name="job_description_text"]');
    var useDescription = mode === JOB_MODE_DESCRIPTION;

    tabs.forEach(function (tab) {
      var tabMode = tab.getAttribute("data-job-mode");
      var active = tabMode === mode;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });

    if (useDescription) {
      panelLink.classList.add("is-hidden");
      panelLink.setAttribute("hidden", "");
      panelDescription.classList.remove("is-hidden");
      panelDescription.removeAttribute("hidden");
      if (linkInput) linkInput.removeAttribute("required");
      if (descInput) descInput.setAttribute("required", "");
    } else {
      panelDescription.classList.add("is-hidden");
      panelDescription.setAttribute("hidden", "");
      panelLink.classList.remove("is-hidden");
      panelLink.removeAttribute("hidden");
      if (descInput) descInput.removeAttribute("required");
      if (linkInput) linkInput.setAttribute("required", "");
    }
  }

  function initJobInputTabs() {
    var tabs = document.querySelectorAll(".job-mode-tab");

    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        setJobInputMode(tab.getAttribute("data-job-mode"));
        clearMessage($("job-message"));
      });
    });

    setJobInputMode(JOB_MODE_LINK);
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
            var displayEmail = r.data.email || email;
            setStoredSession(r.data.user_id, displayEmail);
            setMessage(msg, r.data.message || "Account created.", "ok");
            showUploadView(displayEmail);
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
            var displayEmail = r.data.email || email;
            setStoredSession(r.data.user_id, displayEmail);
            setMessage(msg, r.data.message || "Signed in.", "ok");
            showUploadView(displayEmail);
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
      clearMessage(msg);

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
            var saved = r.data.resume;
            if (saved && saved._id) {
              setStoredResume(saved._id, saved.parsed_data || {});
            }
            ev.target.reset();
            showJobApplicationView(getStoredUserEmail());
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

  function wireJobApplication() {
    $("form-job-application").addEventListener("submit", function (ev) {
      ev.preventDefault();
      var customerId = getStoredUserId();
      var msg = $("job-message");
      var out = $("job-result");
      clearMessage(msg);
      if (out) {
        out.classList.add("is-hidden");
        out.textContent = "";
      }

      if (!customerId) {
        setMessage(msg, "Session missing. Please sign in again.", "error");
        showAuthView();
        return;
      }

      var fd = new FormData(ev.target);
      var mode = getActiveJobInputMode();
      var body = {
        customer_id: customerId,
        input_mode: mode,
      };

      if (mode === JOB_MODE_LINK) {
        body.application_link = (fd.get("application_link") || "").toString().trim();
        if (!body.application_link) {
          setMessage(msg, "Enter a job application link.", "error");
          return;
        }
      } else {
        body.job_description_text = (fd.get("job_description_text") || "").toString().trim();
        if (!body.job_description_text) {
          setMessage(msg, "Paste a job description.", "error");
          return;
        }
      }

      var btn = ev.target.querySelector('button[type="submit"]');
      btn.disabled = true;

      apiJson("/api/job-applications", body)
        .then(function (r) {
          if (r.ok) {
            setMessage(msg, r.data.message || "Job application saved.", "ok");
            if (out) {
              out.textContent = JSON.stringify(r.data, null, 2);
              out.classList.remove("is-hidden");
            }
            ev.target.reset();
          } else {
            setMessage(msg, r.data.error || "Could not save job application.", "error");
            if (
              r.data.suggest_input_mode === JOB_MODE_DESCRIPTION ||
              r.data.error_code === "job_url_blocked"
            ) {
              setJobInputMode(JOB_MODE_DESCRIPTION);
              var descInput = document.querySelector(
                '#panel-job-description textarea[name="job_description_text"]'
              );
              if (descInput) descInput.focus();
            }
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

  function loadResumeDetail(userId, resumeId, msgEl) {
    return apiGet(
      "/api/resumes/" + encodeURIComponent(resumeId) + "?userid=" + encodeURIComponent(userId)
    ).then(function (r) {
      if (!r.ok || !r.data.resume) {
        setMessage(msgEl, r.data.error || "Could not load resume.", "error");
        return;
      }
      var resume = r.data.resume;
      setStoredResume(resume.resume_id, resume.parsed_data);
      applySelectedResumeToUi(resume.parsed_data, resume.resume_id);
      setMessage(msgEl, "Resume selected. It will be used until you sign out.", "ok");
    });
  }

  function renderResumeTable(resumes, userId, msgEl) {
    var wrap = $("resume-list-wrap");
    var tbody = $("resume-table-body");
    if (!tbody) return;
    tbody.textContent = "";

    resumes.forEach(function (item) {
      var tr = document.createElement("tr");
      tr.setAttribute("data-resume-id", item.resume_id);

      var tdDate = document.createElement("td");
      tdDate.textContent = formatResumeDate(item.uploaded_ts);

      var tdResume = document.createElement("td");
      var link = document.createElement("button");
      link.type = "button";
      link.className = "resume-link";
      link.textContent = item.label || "Resume";
      link.addEventListener("click", function () {
        loadResumeDetail(userId, item.resume_id, msgEl);
      });
      tdResume.appendChild(link);

      tr.appendChild(tdDate);
      tr.appendChild(tdResume);
      tbody.appendChild(tr);
    });

    showElement(wrap, resumes.length > 1);
  }

  function wireFetchResume() {
    var btn = $("btn-fetch-resume");
    if (!btn) return;

    btn.addEventListener("click", function () {
      var userId = getStoredUserId();
      var msg = $("upload-message");
      clearMessage(msg);
      showElement($("resume-list-wrap"), false);
      showElement($("resume-selected-wrap"), false);
      showElement($("btn-continue-job"), false);

      if (!userId) {
        setMessage(msg, "Session missing. Please sign in again.", "error");
        showAuthView();
        return;
      }

      btn.disabled = true;
      apiGet("/api/resumes?userid=" + encodeURIComponent(userId))
        .then(function (r) {
          if (!r.ok) {
            setMessage(msg, r.data.error || "Could not fetch resumes.", "error");
            return;
          }
          var resumes = r.data.resumes || [];
          if (resumes.length === 0) {
            setMessage(msg, "No saved resumes found. Upload a PDF first.", "error");
            return;
          }
          if (resumes.length === 1) {
            return loadResumeDetail(userId, resumes[0].resume_id, msg);
          }
          renderResumeTable(resumes, userId, msg);
          setMessage(msg, "Select a resume from the list.", "ok");
        })
        .catch(function () {
          setMessage(msg, "Network error. Try again.", "error");
        })
        .finally(function () {
          btn.disabled = false;
        });
    });
  }

  function wireContinueToJob() {
    var btn = $("btn-continue-job");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var msg = $("upload-message");
      if (!getStoredResumeId()) {
        setMessage(msg, "Fetch and select a resume first.", "error");
        return;
      }
      showJobApplicationView(getStoredUserEmail());
    });
  }

  function wireSignOut() {
    function signOut() {
      setStoredSession("", "");
      clearStoredResume();
      showElement($("resume-list-wrap"), false);
      showElement($("resume-selected-wrap"), false);
      showElement($("btn-continue-job"), false);
      var tbody = $("resume-table-body");
      if (tbody) tbody.textContent = "";
      var textarea = $("resume-parsed-display");
      if (textarea) textarea.value = "";
      showAuthView();
    }
    $("btn-sign-out").addEventListener("click", signOut);
    var jobBtn = $("btn-sign-out-job");
    if (jobBtn) jobBtn.addEventListener("click", signOut);
  }

  function boot() {
    initTabs();
    initJobInputTabs();
    wireSignup();
    wireLogin();
    wireUpload();
    wireFetchResume();
    wireContinueToJob();
    wireJobApplication();
    wireSignOut();

    var uid = getStoredUserId();
    if (uid) showUploadView(getStoredUserEmail());
    else showAuthView();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();

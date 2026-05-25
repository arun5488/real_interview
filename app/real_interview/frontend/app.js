(function () {
  "use strict";

  var STORAGE_KEY_USER_ID = "ri_user_id";
  var STORAGE_KEY_EMAIL = "ri_user_email";
  var STORAGE_KEY_RESUME_ID = "ri_resume_id";
  var STORAGE_KEY_RESUME_PARSED = "ri_resume_parsed";
  var STORAGE_KEY_JOB_APPLICATION_ID = "ri_job_application_id";
  var STORAGE_KEY_INTERVIEW_SESSION = "ri_interview_session";
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

  function getStoredJobApplicationId() {
    try {
      return sessionStorage.getItem(STORAGE_KEY_JOB_APPLICATION_ID) || "";
    } catch (e) {
      return "";
    }
  }

  function setStoredJobApplicationId(id) {
    try {
      if (id) sessionStorage.setItem(STORAGE_KEY_JOB_APPLICATION_ID, id);
      else sessionStorage.removeItem(STORAGE_KEY_JOB_APPLICATION_ID);
    } catch (e) {
      /* ignore */
    }
  }

  function getStoredInterviewSession() {
    try {
      return sessionStorage.getItem(STORAGE_KEY_INTERVIEW_SESSION) || "";
    } catch (e) {
      return "";
    }
  }

  function setStoredInterviewSession(sessionId) {
    try {
      if (sessionId) sessionStorage.setItem(STORAGE_KEY_INTERVIEW_SESSION, sessionId);
      else sessionStorage.removeItem(STORAGE_KEY_INTERVIEW_SESSION);
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
    var chatDisplay = $("display-user-email-chat");
    if (chatDisplay) chatDisplay.textContent = value;
  }

  function formatInterviewerMessageContent(content, panelPlan) {
    if (!content || typeof content !== "string") return content || "";
    var selected = (panelPlan && panelPlan.selected_interviewers) || [];
    var out = content;
    selected.forEach(function (type, i) {
      var code = "I" + (i + 1);
      var escaped = type.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      var patterns = [
        new RegExp("^\\[" + escaped + "[ _]?interviewer\\]:\\s*", "i"),
        new RegExp("^\\[" + escaped + "\\]:\\s*", "i"),
      ];
      patterns.forEach(function (re) {
        if (re.test(out)) {
          out = out.replace(re, "[" + code + "]: ");
        }
      });
    });
    out = out.replace(/^\[(positive|negative|objective)[ _]?interviewer\]:/i, function (match, type) {
      var idx = selected.indexOf(type.toLowerCase());
      return "[" + (idx >= 0 ? "I" + (idx + 1) : "I1") + "]:";
    });
    return out;
  }

  function renderChatMessages(messages, panelPlan) {
    var container = $("chat-messages");
    if (!container) return;
    container.textContent = "";
    (messages || []).forEach(function (m) {
      var div = document.createElement("div");
      div.className = "chat-bubble " + (m.role === "user" ? "user" : "assistant");
      var text = m.content || "";
      if (m.role === "assistant") {
        text = formatInterviewerMessageContent(text, panelPlan);
      }
      div.textContent = text;
      container.appendChild(div);
    });
    container.scrollTop = container.scrollHeight;
  }

  function setInterviewPausedUi(paused) {
    var form = $("form-chat");
    var input = $("chat-input");
    var btnPause = $("btn-pause-interview");
    var btnResume = $("btn-resume-interview");
    var btnAdvance = $("btn-advance-interviewer");
    var btnEnd = $("btn-end-interview");
    var sendBtn = form ? form.querySelector('button[type="submit"]') : null;

    showElement(btnPause, !paused);
    showElement(btnResume, paused);
    showElement(btnAdvance, !paused);
    showElement(btnEnd, !paused);
    showElement(form, !paused);
    if (input) {
      input.disabled = paused;
      if (!paused) input.focus();
    }
    if (sendBtn) sendBtn.disabled = paused;
  }

  function applyInterviewStateToUi(state) {
    if (!state) return;
    var sessionEl = $("display-session-id");
    if (sessionEl) sessionEl.textContent = state.session_id || getStoredInterviewSession() || "";
    var preview = $("interview-context-preview");
    if (preview) {
      preview.textContent = JSON.stringify(
        {
          first_impression: state.first_impression,
          panel_plan: state.panel_plan,
          running_summary: state.running_summary,
        },
        null,
        2
      );
    }
    renderChatMessages(state.messages || [], state.panel_plan);
    var feedback = state.candidate_post_interview_feedback;
    var wrap = $("interview-feedback-wrap");
    var fbEl = $("interview-feedback");
    if (feedback && wrap && fbEl) {
      fbEl.textContent = JSON.stringify(feedback, null, 2);
      showElement(wrap, true);
      showElement($("form-chat"), false);
      showElement($("btn-advance-interviewer"), false);
      showElement($("btn-end-interview"), false);
      showElement($("btn-pause-interview"), false);
      showElement($("btn-resume-interview"), false);
      setInterviewPausedUi(false);
    } else {
      var paused = state.interview_status === "paused";
      setInterviewPausedUi(paused);
      if (paused) {
        setMessage($("chat-message"), "Interview paused. Click Resume when you are ready to continue.", "ok");
      }
    }
  }

  function showInterviewChatView(email, sessionId) {
    hideView("view-auth");
    hideView("view-upload");
    hideView("view-job-application");
    showView("view-interview-chat");
    setSignedInEmail(email);
    if (sessionId) {
      setStoredInterviewSession(sessionId);
      var sessionEl = $("display-session-id");
      if (sessionEl) sessionEl.textContent = sessionId;
    }
    clearMessage($("chat-message"));
  }

  function showAuthView() {
    hideView("view-upload");
    hideView("view-job-application");
    hideView("view-interview-chat");
    showView("view-auth");
    showAuthPanel("signup");
    clearMessage($("auth-message"));
    clearMessage($("upload-message"));
    clearMessage($("job-message"));
    clearMessage($("chat-message"));
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

  function apiPut(url, body) {
    return fetch(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    }).then(function (res) {
      return res.json().then(function (data) {
        return { ok: res.ok, status: res.status, data: data };
      });
    });
  }

  function apiDelete(url, body) {
    return fetch(url, {
      method: "DELETE",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    }).then(function (res) {
      return res.json().then(function (data) {
        return { ok: res.ok, status: res.status, data: data };
      });
    });
  }

  function showAuthPanel(panelName) {
    var panelSignup = $("panel-signup");
    var panelLogin = $("panel-login");
    var panelReset = $("panel-reset-password");
    var panelDelete = $("panel-delete-account");
    var tabs = document.querySelectorAll(".tab:not(.job-mode-tab)");

    showElement(panelSignup, panelName === "signup");
    showElement(panelLogin, panelName === "login");
    showElement(panelReset, panelName === "reset");
    showElement(panelDelete, panelName === "delete");

    tabs.forEach(function (tab) {
      var name = tab.getAttribute("data-tab");
      var active = panelName === "signup" || panelName === "login" ? name === panelName : false;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
  }

  function initTabs() {
    var tabs = document.querySelectorAll(".tab:not(.job-mode-tab)");

    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        var name = tab.getAttribute("data-tab");
        showAuthPanel(name === "login" ? "login" : "signup");
        clearMessage($("auth-message"));
      });
    });
  }

  function wireDeleteAccount() {
    var linkDelete = $("link-delete-account");
    var linkBack = $("link-back-from-delete");
    var form = $("form-delete-account");

    if (linkDelete) {
      linkDelete.addEventListener("click", function () {
        var loginEmail = "";
        var loginInput = document.querySelector('#form-login input[name="email"]');
        if (loginInput) loginEmail = loginInput.value.trim();
        showAuthPanel("delete");
        clearMessage($("auth-message"));
        var deleteEmail = document.querySelector('#form-delete-account input[name="email"]');
        if (deleteEmail && loginEmail) deleteEmail.value = loginEmail;
      });
    }

    if (linkBack) {
      linkBack.addEventListener("click", function () {
        showAuthPanel("login");
        clearMessage($("auth-message"));
      });
    }

    if (!form) return;

    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var fd = new FormData(ev.target);
      var email = (fd.get("email") || "").toString().trim();
      var password = (fd.get("password") || "").toString();
      var confirmed = fd.get("confirm_delete") === "on";
      var msg = $("auth-message");
      clearMessage(msg);

      if (!email) {
        setMessage(msg, "Enter your account email.", "error");
        return;
      }
      if (!confirmed) {
        setMessage(msg, "Confirm that you understand this action is permanent.", "error");
        return;
      }

      var btn = ev.target.querySelector('button[type="submit"]');
      btn.disabled = true;

      apiDelete("/api/users", { email: email, password: password })
        .then(function (r) {
          if (r.ok) {
            setStoredSession("", "");
            clearStoredResume();
            setStoredJobApplicationId("");
            setStoredInterviewSession("");
            form.reset();
            setMessage(msg, r.data.message || "Account deleted.", "ok");
            showAuthPanel("signup");
          } else {
            setMessage(msg, r.data.error || "Could not delete account.", "error");
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

  function wireResetPassword() {
    var linkReset = $("link-reset-password");
    var linkBack = $("link-back-to-login");
    var form = $("form-reset-password");

    if (linkReset) {
      linkReset.addEventListener("click", function () {
        var loginEmail = "";
        var loginInput = document.querySelector('#form-login input[name="email"]');
        if (loginInput) loginEmail = loginInput.value.trim();
        showAuthPanel("reset");
        clearMessage($("auth-message"));
        var resetEmail = document.querySelector('#form-reset-password input[name="email"]');
        if (resetEmail && loginEmail) resetEmail.value = loginEmail;
      });
    }

    if (linkBack) {
      linkBack.addEventListener("click", function () {
        showAuthPanel("login");
        clearMessage($("auth-message"));
      });
    }

    if (!form) return;

    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var fd = new FormData(ev.target);
      var email = (fd.get("email") || "").toString().trim();
      var new_password = (fd.get("new_password") || "").toString();
      var confirm_new_password = (fd.get("confirm_new_password") || "").toString();
      var msg = $("auth-message");
      clearMessage(msg);

      if (!email) {
        setMessage(msg, "Enter your account email.", "error");
        return;
      }
      if (new_password !== confirm_new_password) {
        setMessage(msg, "New passwords do not match.", "error");
        return;
      }

      var btn = ev.target.querySelector('button[type="submit"]');
      btn.disabled = true;

      apiPut("/api/users/password", {
        email: email,
        new_password: new_password,
        confirm_new_password: confirm_new_password,
      })
        .then(function (r) {
          if (r.ok) {
            setMessage(msg, r.data.message || "Password changed. You can log in now.", "ok");
            form.reset();
            var loginInput = document.querySelector('#form-login input[name="email"]');
            if (loginInput) loginInput.value = email;
            showAuthPanel("login");
          } else {
            setMessage(msg, r.data.error || "Could not reset password.", "error");
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
            if (r.data.job_application_id) {
              setStoredJobApplicationId(r.data.job_application_id);
              showElement($("btn-start-interview"), true);
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

  function startInterviewSession() {
    var customerId = getStoredUserId();
    var resumeId = getStoredResumeId();
    var jobAppId = getStoredJobApplicationId();
    var msg = $("job-message") || $("chat-message");

    if (!customerId || !resumeId || !jobAppId) {
      setMessage(msg, "Resume and job application are required before starting the interview.", "error");
      return Promise.resolve();
    }

    setMessage(msg, "Starting interview…", "ok");
    return apiJson("/api/interview/start", {
      customer_id: customerId,
      resume_id: resumeId,
      job_application_id: jobAppId,
    }).then(function (r) {
      if (r.ok && r.data.session_id) {
        setStoredInterviewSession(r.data.session_id);
        showInterviewChatView(getStoredUserEmail(), r.data.session_id);
        applyInterviewStateToUi(r.data.state);
        setMessage($("chat-message"), r.data.message || "Interview ready. Respond to the interviewer below.", "ok");
      } else if (r.status === 409 && r.data.interview_status === "paused" && r.data.session_id) {
        setStoredInterviewSession(r.data.session_id);
        showInterviewChatView(getStoredUserEmail(), r.data.session_id);
        if (r.data.state) applyInterviewStateToUi(r.data.state);
        else setInterviewPausedUi(true);
        setMessage($("chat-message"), r.data.error || "Interview is paused. Click Resume to continue.", "ok");
      } else {
        setMessage(msg, r.data.error || "Could not start interview.", "error");
      }
    });
  }

  function wireInterviewChat() {
    var form = $("form-chat");
    if (form) {
      form.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var sessionId = getStoredInterviewSession();
        var input = $("chat-input");
        var msg = $("chat-message");
        var text = input ? input.value.trim() : "";
        if (!sessionId) {
          setMessage(msg, "Session missing. Start the interview again.", "error");
          return;
        }
        if (!text) return;

        setMessage(msg, "", "");
        var btn = form.querySelector('button[type="submit"]');
        btn.disabled = true;

        apiJson("/api/interview/message", { session_id: sessionId, message: text })
          .then(function (r) {
            if (r.ok) {
              input.value = "";
              applyInterviewStateToUi(r.data.state);
            } else {
              setMessage(msg, r.data.error || "Message failed.", "error");
            }
          })
          .catch(function () {
            setMessage(msg, "Network error. Try again.", "error");
          })
          .finally(function () {
            btn.disabled = false;
            if (input) input.focus();
          });
      });
    }

    var btnEnd = $("btn-end-interview");
    if (btnEnd) {
      btnEnd.addEventListener("click", function () {
        var sessionId = getStoredInterviewSession();
        var msg = $("chat-message");
        if (!sessionId) {
          setMessage(msg, "Session missing.", "error");
          return;
        }
        btnEnd.disabled = true;
        apiJson("/api/interview/complete", { session_id: sessionId })
          .then(function (r) {
            if (r.ok) {
              applyInterviewStateToUi(r.data.state);
              setMessage(msg, r.data.message || "Interview complete.", "ok");
            } else {
              setMessage(msg, r.data.error || "Could not complete interview.", "error");
            }
          })
          .finally(function () {
            btnEnd.disabled = false;
          });
      });
    }

    var btnPause = $("btn-pause-interview");
    if (btnPause) {
      btnPause.addEventListener("click", function () {
        var sessionId = getStoredInterviewSession();
        var msg = $("chat-message");
        if (!sessionId) {
          setMessage(msg, "Session missing.", "error");
          return;
        }
        btnPause.disabled = true;
        apiJson("/api/interview/pause", { session_id: sessionId })
          .then(function (r) {
            if (r.ok) {
              applyInterviewStateToUi(r.data.state);
              setMessage(msg, r.data.message || "Interview paused.", "ok");
            } else {
              setMessage(msg, r.data.error || "Could not pause interview.", "error");
            }
          })
          .finally(function () {
            btnPause.disabled = false;
          });
      });
    }

    var btnResume = $("btn-resume-interview");
    if (btnResume) {
      btnResume.addEventListener("click", function () {
        var sessionId = getStoredInterviewSession();
        var msg = $("chat-message");
        if (!sessionId) {
          setMessage(msg, "Session missing.", "error");
          return;
        }
        btnResume.disabled = true;
        apiJson("/api/interview/resume", { session_id: sessionId })
          .then(function (r) {
            if (r.ok) {
              applyInterviewStateToUi(r.data.state);
              setMessage(msg, r.data.message || "Interview resumed.", "ok");
            } else {
              setMessage(msg, r.data.error || "Could not resume interview.", "error");
            }
          })
          .finally(function () {
            btnResume.disabled = false;
          });
      });
    }

    var btnAdvance = $("btn-advance-interviewer");
    if (btnAdvance) {
      btnAdvance.addEventListener("click", function () {
        var sessionId = getStoredInterviewSession();
        var msg = $("chat-message");
        if (!sessionId) return;
        btnAdvance.disabled = true;
        apiJson("/api/interview/advance", { session_id: sessionId })
          .then(function (r) {
            if (r.ok) {
              applyInterviewStateToUi(r.data.state);
              setMessage(msg, r.data.message || "Next interviewer.", "ok");
            } else {
              setMessage(msg, r.data.error || "Advance failed.", "error");
            }
          })
          .finally(function () {
            btnAdvance.disabled = false;
          });
      });
    }
  }

  function wireStartInterview() {
    var btn = $("btn-start-interview");
    if (btn) {
      btn.addEventListener("click", function () {
        startInterviewSession();
      });
    }
  }

  function restoreInterviewChatIfNeeded() {
    var sessionId = getStoredInterviewSession();
    if (!sessionId || !getStoredUserId()) return;

    apiGet("/api/interview/state?session_id=" + encodeURIComponent(sessionId)).then(function (r) {
      if (!r.ok) return;
      var state = r.data.state;
      var record = r.data.record;
      if (!state && record) {
        state = {
          session_id: sessionId,
          messages: record.messages || [],
          running_summary: record.interview_summary || "",
          interview_status: record.interview_status || "active",
          candidate_post_interview_feedback: record.interview_feedback,
        };
      }
      if (state || record) {
        showInterviewChatView(getStoredUserEmail(), sessionId);
        if (state) applyInterviewStateToUi(state);
        else if (record && record.interview_status === "paused") {
          setInterviewPausedUi(true);
          setMessage($("chat-message"), "Interview paused. Click Resume to continue.", "ok");
        }
      }
    });
  }

  function wireSignOut() {
    function signOut() {
      setStoredSession("", "");
      clearStoredResume();
      setStoredJobApplicationId("");
      setStoredInterviewSession("");
      showElement($("resume-list-wrap"), false);
      showElement($("resume-selected-wrap"), false);
      showElement($("btn-continue-job"), false);
      showElement($("btn-start-interview"), false);
      showElement($("interview-feedback-wrap"), false);
      showElement($("form-chat"), true);
      var tbody = $("resume-table-body");
      if (tbody) tbody.textContent = "";
      var textarea = $("resume-parsed-display");
      if (textarea) textarea.value = "";
      var chatBox = $("chat-messages");
      if (chatBox) chatBox.textContent = "";
      showAuthView();
    }
    $("btn-sign-out").addEventListener("click", signOut);
    var jobBtn = $("btn-sign-out-job");
    if (jobBtn) jobBtn.addEventListener("click", signOut);
    var chatBtn = $("btn-sign-out-chat");
    if (chatBtn) chatBtn.addEventListener("click", signOut);
  }

  function boot() {
    initTabs();
    initJobInputTabs();
    wireSignup();
    wireLogin();
    wireResetPassword();
    wireDeleteAccount();
    wireUpload();
    wireFetchResume();
    wireContinueToJob();
    wireJobApplication();
    wireStartInterview();
    wireInterviewChat();
    wireSignOut();

    var uid = getStoredUserId();
    if (uid) {
      if (getStoredInterviewSession()) {
        restoreInterviewChatIfNeeded();
      } else {
        showUploadView(getStoredUserEmail());
      }
    } else {
      showAuthView();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();

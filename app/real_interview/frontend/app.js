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

  function isSignedIn() {
    return !!getStoredUserId();
  }

  function fetchCredentials() {
    return "same-origin";
  }

  function authHeaders(extra) {
    return extra || {};
  }

  function formatApiError(data, fallback) {
    if (!data) return fallback;
    if (data.error === "too many requests" && data.retry_after_seconds) {
      return "Too many attempts. Try again in " + data.retry_after_seconds + " seconds.";
    }
    return data.error || data.message || fallback;
  }

  function handleUnauthorized() {
    setStoredSession("", "");
    clearStoredResume();
    setStoredJobApplicationId("");
    setStoredInterviewSession("");
    showAuthView();
  }

  function restoreSessionFromServer() {
    return apiGet("/api/users/me").then(function (r) {
      if (r.ok && r.data.user_id) {
        setStoredSession(r.data.user_id, r.data.email || "");
        return true;
      }
      handleUnauthorized();
      return false;
    });
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

  var pendingResumableInterview = null;

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
    return fetch(url, {
      credentials: fetchCredentials(),
      headers: authHeaders({ Accept: "application/json" }),
    }).then(function (res) {
      return res.json().then(function (data) {
        if (res.status === 401) handleUnauthorized();
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
    var profileDisplay = $("display-user-email-profile");
    if (profileDisplay) profileDisplay.textContent = value;
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
    var btnEnd = $("btn-end-interview");
    var sendBtn = form ? form.querySelector('button[type="submit"]') : null;

    showElement(btnPause, !paused);
    showElement(btnResume, paused);
    showElement(btnEnd, !paused);
    showElement(form, !paused);
    if (input) {
      input.disabled = paused;
      if (!paused) input.focus();
    }
    if (sendBtn) sendBtn.disabled = paused;
  }

  function formatReportDecision(decision) {
    var value = (decision || "").toString().trim().toLowerCase();
    if (value === "selected") return "Selected";
    if (value === "not_selected") return "Not selected";
    if (value === "hold") return "Hold";
    return decision || "—";
  }

  function createReportSection(title, content, options) {
    options = options || {};
    var section = document.createElement("section");
    section.className = "interview-report-section";

    var heading = document.createElement("h4");
    heading.textContent = title;
    section.appendChild(heading);

    if (options.list && content && content.length) {
      var list = document.createElement("ul");
      content.forEach(function (item) {
        var li = document.createElement("li");
        li.textContent = item;
        list.appendChild(li);
      });
      section.appendChild(list);
      return section;
    }

    var body = document.createElement("p");
    if (options.decision) {
      body.className = "interview-report-decision";
    }
    body.textContent = content || "—";
    section.appendChild(body);
    return section;
  }

  function renderInterviewReport(state) {
    var container = $("interview-report");
    if (!container) return;

    container.textContent = "";
    var feedback = state.candidate_post_interview_feedback || {};
    var summary = state.running_summary || "";

    var meta = document.createElement("div");
    meta.className = "interview-report-meta";
    var metaBits = [];
    if (state.job_role) metaBits.push("Role: " + state.job_role);
    if (state.session_id) metaBits.push("Session: " + state.session_id);
    meta.textContent = metaBits.join(" · ");
    if (meta.textContent) container.appendChild(meta);

    if (summary) container.appendChild(createReportSection("Interview summary", summary));
    if (feedback.overall_assessment) {
      container.appendChild(createReportSection("Overall assessment", feedback.overall_assessment));
    }
    if (feedback.strengths && feedback.strengths.length) {
      container.appendChild(createReportSection("Strengths", feedback.strengths, { list: true }));
    }
    if (feedback.areas_to_improve && feedback.areas_to_improve.length) {
      container.appendChild(createReportSection("Areas to improve", feedback.areas_to_improve, { list: true }));
    }
    if (feedback.recommendation) {
      container.appendChild(createReportSection("Recommendation", feedback.recommendation));
    }
    if (feedback.interview_decision) {
      container.appendChild(
        createReportSection(
          "Interview decision",
          formatReportDecision(feedback.interview_decision),
          { decision: true }
        )
      );
    }
    if (feedback.detailed_feedback) {
      container.appendChild(createReportSection("Detailed feedback", feedback.detailed_feedback));
    }
  }

  function createDownloadIconButton(ariaLabel, onClick) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "download-icon-btn";
    btn.setAttribute("aria-label", ariaLabel);
    btn.setAttribute("title", ariaLabel);
    btn.innerHTML =
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>' +
      '<polyline points="7 10 12 15 17 10"/>' +
      '<line x1="12" y1="15" x2="12" y2="3"/>' +
      "</svg>";
    btn.addEventListener("click", onClick);
    return btn;
  }

  function downloadInterviewReportPdf(sessionId, msgEl) {
    if (!sessionId) {
      if (msgEl) setMessage(msgEl, "Session missing.", "error");
      return Promise.resolve();
    }
    return fetch(
      "/api/interview/report/download?session_id=" + encodeURIComponent(sessionId),
      {
        credentials: fetchCredentials(),
        headers: authHeaders(),
      }
    )
      .then(function (res) {
        if (res.status === 401) {
          handleUnauthorized();
          return null;
        }
        if (!res.ok) {
          return res.json().then(function (data) {
            if (msgEl) setMessage(msgEl, (data && data.error) || "Could not download report.", "error");
            return null;
          });
        }
        var disposition = res.headers.get("Content-Disposition") || "";
        var match = disposition.match(/filename=\"?([^\";]+)\"?/i);
        var filename = (match && match[1]) || "interview-report.pdf";
        return res.blob().then(function (blob) {
          return { blob: blob, filename: filename };
        });
      })
      .then(function (payload) {
        if (!payload) return;
        var url = URL.createObjectURL(payload.blob);
        var anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = payload.filename;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
        if (msgEl) setMessage(msgEl, "Report downloaded.", "ok");
      })
      .catch(function () {
        if (msgEl) setMessage(msgEl, "Network error. Try again.", "error");
      });
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
    if (feedback && wrap) {
      renderInterviewReport(state);
      showElement(wrap, true);
      showElement($("btn-download-interview-report"), true);
      showElement($("btn-back-profile-after-interview"), true);
      showElement($("form-chat"), false);
      showElement($("btn-end-interview"), false);
      showElement($("btn-pause-interview"), false);
      showElement($("btn-resume-interview"), false);
      setInterviewPausedUi(false);
    } else {
      showElement($("btn-back-profile-after-interview"), false);
      showElement($("btn-download-interview-report"), false);
      var paused = state.interview_status === "paused";
      setInterviewPausedUi(paused);
      var chatMsg = $("chat-message");
      if (paused) {
        setMessage(chatMsg, "Interview paused. Click Resume when you are ready to continue.", "ok");
      } else if (state.interview_phase === "awaiting_candidate_questions") {
        setMessage(
          chatMsg,
          "The panel is ready for your questions. Reply with your question, or say you have none to finish.",
          "ok"
        );
      } else if (state.interview_phase === "candidate_qa") {
        var left = Math.max(0, 2 - (state.candidate_qa_turns || 0));
        setMessage(
          chatMsg,
          left > 0
            ? "You may ask the panel up to " + left + " more question(s), or say you have none to finish."
            : "Wrapping up the interview…",
          "ok"
        );
      } else if (chatMsg && chatMsg.classList.contains("is-ok") && chatMsg.textContent.indexOf("panel") !== -1) {
        setMessage(chatMsg, "", null);
      }
    }
  }

  function showInterviewChatView(email, sessionId) {
    hideView("view-auth");
    hideView("view-profile");
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
    hideView("view-profile");
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

  function showProfileView(email) {
    hideView("view-auth");
    hideView("view-upload");
    hideView("view-job-application");
    hideView("view-interview-chat");
    showView("view-profile");
    setSignedInEmail(email);
    clearMessage($("profile-message"));
    loadProfileData();
  }

  function showUploadView(email) {
    hideView("view-auth");
    hideView("view-profile");
    hideView("view-job-application");
    hideView("view-interview-chat");
    showView("view-upload");
    setSignedInEmail(email);
    clearMessage($("auth-message"));
    clearMessage($("upload-message"));
    restoreResumeSelectionFromSession();
    refreshPausedInterviewBanners();
  }

  function showJobApplicationView(email) {
    hideView("view-auth");
    hideView("view-profile");
    hideView("view-upload");
    hideView("view-interview-chat");
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
      credentials: fetchCredentials(),
      headers: authHeaders({ "Content-Type": "application/json", Accept: "application/json" }),
      body: JSON.stringify(body),
    }).then(function (res) {
      return res.json().then(function (data) {
        if (res.status === 401) handleUnauthorized();
        return { ok: res.ok, status: res.status, data: data };
      });
    });
  }

  function apiPut(url, body) {
    return fetch(url, {
      method: "PUT",
      credentials: fetchCredentials(),
      headers: authHeaders({ "Content-Type": "application/json", Accept: "application/json" }),
      body: JSON.stringify(body),
    }).then(function (res) {
      return res.json().then(function (data) {
        if (res.status === 401) handleUnauthorized();
        return { ok: res.ok, status: res.status, data: data };
      });
    });
  }

  function apiDelete(url, body) {
    return fetch(url, {
      method: "DELETE",
      credentials: fetchCredentials(),
      headers: authHeaders({ "Content-Type": "application/json", Accept: "application/json" }),
      body: JSON.stringify(body),
    }).then(function (res) {
      return res.json().then(function (data) {
        if (res.status === 401) handleUnauthorized();
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
        if (deleteEmail) {
          deleteEmail.value = getStoredUserEmail() || loginEmail || "";
        }
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
        setMessage(msg, "Email is required.", "error");
        return;
      }
      if (!password) {
        setMessage(msg, "Password is required.", "error");
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
            if (r.status === 429) {
            setMessage(msg, formatApiError(r.data, "Too many attempts. Try again later."), "error");
            return;
          }
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
      var current_password = (fd.get("current_password") || "").toString();
      var new_password = (fd.get("new_password") || "").toString();
      var confirm_new_password = (fd.get("confirm_new_password") || "").toString();
      var msg = $("auth-message");
      clearMessage(msg);

      if (!isSignedIn()) {
        setMessage(msg, "Sign in first to change your password.", "error");
        return;
      }
      if (new_password !== confirm_new_password) {
        setMessage(msg, "New passwords do not match.", "error");
        return;
      }

      var btn = ev.target.querySelector('button[type="submit"]');
      btn.disabled = true;

      apiPut("/api/users/password", {
        current_password: current_password,
        new_password: new_password,
        confirm_new_password: confirm_new_password,
      })
        .then(function (r) {
          if (r.ok) {
            handleUnauthorized();
            setMessage(msg, (r.data.message || "Password changed.") + " Please log in again.", "ok");
            form.reset();
            showAuthPanel("login");
          } else {
            setMessage(msg, formatApiError(r.data, "Could not change password."), "error");
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

  function storeInterviewContext(summary) {
    if (!summary) return;
    if (summary.session_id) setStoredInterviewSession(summary.session_id);
    if (summary.job_application_id) setStoredJobApplicationId(summary.job_application_id);
    if (summary.resume_id) {
      try {
        sessionStorage.setItem(STORAGE_KEY_RESUME_ID, summary.resume_id);
      } catch (e) {
        /* ignore */
      }
    }
  }

  function pickLatestPausedInterview(interviews) {
    var paused = (interviews || []).filter(function (item) {
      return item.interview_status === "paused";
    });
    if (!paused.length) return null;
    paused.sort(function (a, b) {
      var left = new Date(a.paused_at || a.interview_date || 0).getTime();
      var right = new Date(b.paused_at || b.interview_date || 0).getTime();
      return right - left;
    });
    return paused[0];
  }

  function pickResumableInterview(interviews) {
    var latestPaused = pickLatestPausedInterview(interviews);
    if (latestPaused) return latestPaused;
    if (!interviews || !interviews.length) return null;
    return interviews[0];
  }

  function hidePausedInterviewBanners() {
    pendingResumableInterview = null;
    showElement($("paused-interview-banner-upload"), false);
    showElement($("paused-interview-banner-job"), false);
  }

  function showPausedInterviewBanners(interviews, pick) {
    if (!pick) {
      hidePausedInterviewBanners();
      return;
    }
    pendingResumableInterview = pick;
    var statusText = pick.interview_status === "paused" ? "paused" : "in-progress";
    var roleText = pick.role_applied_for || "your saved application";
    ["upload", "job"].forEach(function (suffix) {
      var banner = $("paused-interview-banner-" + suffix);
      var statusEl = $("paused-interview-status-" + suffix);
      var roleEl = $("paused-interview-role-" + suffix);
      if (statusEl) statusEl.textContent = statusText;
      if (roleEl) roleEl.textContent = roleText;
      showElement(banner, true);
    });
  }

  function restoreInterviewChatFromSessionId(sessionId) {
    if (!sessionId || !isSignedIn()) return Promise.resolve(false);

    return apiGet("/api/interview/state?session_id=" + encodeURIComponent(sessionId)).then(function (r) {
      if (!r.ok) return false;
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
      if (!state && !record) return false;

      setStoredInterviewSession(sessionId);
      if (record) storeInterviewContext(record);
      showInterviewChatView(getStoredUserEmail(), sessionId);
      if (state) applyInterviewStateToUi(state);
      else if (record && record.interview_status === "paused") {
        setInterviewPausedUi(true);
        setMessage($("chat-message"), "Interview paused. Click Resume to continue.", "ok");
      }
      return true;
    });
  }

  function continuePendingInterview() {
    if (!pendingResumableInterview || !pendingResumableInterview.session_id) return Promise.resolve(false);
    storeInterviewContext(pendingResumableInterview);
    return restoreInterviewChatFromSessionId(pendingResumableInterview.session_id);
  }

  function refreshPausedInterviewBanners() {
    return apiGet("/api/interview/sessions").then(function (r) {
      if (!r.ok || !r.data.interviews || !r.data.interviews.length) {
        hidePausedInterviewBanners();
        return;
      }
      var pick = pickResumableInterview(r.data.interviews);
      showPausedInterviewBanners(r.data.interviews, pick);
    });
  }

  function discoverResumableInterview() {
    return refreshPausedInterviewBanners().then(function () {
      return false;
    });
  }

  function afterAuthSuccess(email) {
    showProfileView(email);
  }

  function wireContinuePausedInterview() {
    var btnUpload = $("btn-continue-paused-upload");
    var btnJob = $("btn-continue-paused-job");
    function onContinue() {
      continuePendingInterview();
    }
    if (btnUpload) btnUpload.addEventListener("click", onContinue);
    if (btnJob) btnJob.addEventListener("click", onContinue);
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
            afterAuthSuccess(displayEmail);
          } else {
            setMessage(msg, formatApiError(r.data, "Sign up failed."), "error");
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
            afterAuthSuccess(displayEmail);
          } else {
            setMessage(msg, formatApiError(r.data, "Log in failed."), "error");
          }
        })
        .catch(function () {
          setMessage(msg, "Network error. Try again.", "error");
        });
    });
  }

  function renderProfileResumeTable(resumes) {
    var wrap = $("profile-resume-list-wrap");
    var tbody = $("profile-resume-table-body");
    var emptyMsg = $("profile-resume-empty");
    var table = $("profile-resume-table");
    if (!tbody) return;
    tbody.textContent = "";

    var list = resumes || [];
    if (list.length === 0) {
      showElement(wrap, true);
      showElement(table, false);
      showElement(emptyMsg, true);
      return;
    }

    showElement(wrap, true);
    showElement(table, true);
    showElement(emptyMsg, false);

    list.forEach(function (item) {
      var tr = document.createElement("tr");
      var canDownload = item.downloadable !== false && item.resume_id;

      var tdDate = document.createElement("td");
      tdDate.textContent = formatResumeDate(item.uploaded_ts);

      var tdLabel = document.createElement("td");
      tdLabel.textContent = item.label || "Resume";

      var tdDownload = document.createElement("td");
      if (canDownload) {
        var dl = document.createElement("button");
        dl.type = "button";
        dl.className = "btn link report-download-link";
        dl.textContent = "Download saved resume";
        dl.addEventListener("click", function () {
          downloadResumeFile(item.resume_id, item.label);
        });
        tdDownload.appendChild(dl);
      } else {
        tdDownload.textContent = "Not available";
      }

      tr.appendChild(tdDate);
      tr.appendChild(tdLabel);
      tr.appendChild(tdDownload);
      tbody.appendChild(tr);
    });
  }

  function downloadResumeFile(resumeId, label) {
    var msg = $("profile-message");
    fetch("/api/resumes/" + encodeURIComponent(resumeId) + "/download", {
      credentials: fetchCredentials(),
      headers: authHeaders(),
    })
      .then(function (res) {
        if (res.status === 401) {
          handleUnauthorized();
          return null;
        }
        if (!res.ok) {
          return res.json().then(function (data) {
            setMessage(msg, (data && data.error) || "Download failed.", "error");
            return null;
          });
        }
        var disposition = res.headers.get("Content-Disposition") || "";
        var match = disposition.match(/filename=\"?([^\";]+)\"?/i);
        var filename = (match && match[1]) || label || "resume";
        return res.blob().then(function (blob) {
          return { blob: blob, filename: filename };
        });
      })
      .then(function (payload) {
        if (!payload) return;
        var url = URL.createObjectURL(payload.blob);
        var anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = payload.filename;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
        setMessage(msg, "Resume downloaded.", "ok");
      })
      .catch(function () {
        setMessage(msg, "Network error. Try again.", "error");
      });
  }

  function loadProfileResumes() {
    return apiGet("/api/resumes").then(function (r) {
      if (!r.ok) {
        var msg = $("profile-message");
        if (msg) setMessage(msg, (r.data && r.data.error) || "Could not load resumes.", "error");
        return;
      }
      renderProfileResumeTable(r.data.resumes || []);
    });
  }

  function setProfileInterviewStatActive(kind) {
    var completed = $("link-profile-completed");
    var paused = $("link-profile-paused");
    if (completed) completed.classList.toggle("is-active", kind === "completed");
    if (paused) paused.classList.toggle("is-active", kind === "paused");
  }

  function renderProfileInterviewsTable(kind, interviews) {
    var wrap = $("profile-interviews-wrap");
    var heading = $("profile-interviews-heading");
    var tbody = $("profile-interviews-body");
    var table = $("profile-interviews-table");
    if (!tbody) return;
    tbody.textContent = "";

    if (table) {
      table.classList.toggle("profile-interviews-paused", kind === "paused");
    }

    if (heading) {
      heading.textContent = kind === "paused" ? "Paused interviews" : "Completed interviews";
    }

    (interviews || []).forEach(function (item) {
      var tr = document.createElement("tr");

      function addCell(text) {
        var td = document.createElement("td");
        td.textContent = text || "—";
        tr.appendChild(td);
      }

      addCell(item.role_applied_for || "—");
      addCell(formatResumeDate(item.interview_date));
      addCell(item.interview_status === "paused" ? formatResumeDate(item.paused_at) : "—");
      addCell(item.interview_status || "—");
      addCell(String(item.message_count != null ? item.message_count : "—"));

      var tdReport = document.createElement("td");
      tdReport.className = "profile-interviews-report-col";
      if (kind === "completed" && item.session_id) {
        tdReport.appendChild(
          createDownloadIconButton("Download summary report", function () {
            downloadInterviewReportPdf(item.session_id, $("profile-message"));
          })
        );
      } else {
        tdReport.textContent = "—";
      }
      tr.appendChild(tdReport);

      tbody.appendChild(tr);
    });

    showElement(wrap, true);
    setProfileInterviewStatActive(kind);
  }

  function loadProfileInterviewTable(kind) {
    var msg = $("profile-message");
    return apiGet("/api/users/profile/interviews?status=" + encodeURIComponent(kind)).then(function (r) {
      if (!r.ok) {
        setMessage(msg, r.data.error || "Could not load interviews.", "error");
        return;
      }
      renderProfileInterviewsTable(kind, r.data.interviews || []);
      if (!(r.data.interviews || []).length) {
        setMessage(msg, "No " + kind + " interviews yet.", "ok");
      } else {
        clearMessage(msg);
      }
    });
  }

  function renderProfileInterviewSettings(settings) {
    var block = settings && settings.max_questions_per_interviewer;
    if (!block) return;

    var defaultEl = $("profile-max-questions-default");
    var input = $("profile-max-questions-input");
    var effectiveEl = $("profile-max-questions-effective");
    var minimum = block.minimum != null ? block.minimum : 4;

    if (defaultEl) defaultEl.textContent = String(block.default != null ? block.default : 8);
    if (input) {
      input.min = String(minimum);
      input.value =
        block.override != null && block.override !== ""
          ? String(block.override)
          : String(block.default != null ? block.default : 8);
    }
    if (effectiveEl) {
      var effective = block.effective != null ? block.effective : block.default;
      if (block.override != null && block.override !== "") {
        effectiveEl.textContent = "Currently using your preference: " + effective + " questions per interviewer.";
      } else {
        effectiveEl.textContent = "Currently using the app default: " + effective + " questions per interviewer.";
      }
    }
  }

  function loadProfileData() {
    var completedEl = $("profile-count-completed");
    var pausedEl = $("profile-count-paused");
    apiGet("/api/users/profile").then(function (r) {
      if (!r.ok) return;
      if (r.data.interview_counts) {
        if (completedEl) completedEl.textContent = String(r.data.interview_counts.completed || 0);
        if (pausedEl) pausedEl.textContent = String(r.data.interview_counts.paused || 0);
      }
      if (r.data.interview_settings) {
        renderProfileInterviewSettings(r.data.interview_settings);
      }
    });
    loadProfileResumes();
  }

  function resumeLatestPausedInterview() {
    var msg = $("profile-message");
    clearMessage(msg);
    apiGet("/api/interview/sessions").then(function (r) {
      if (!r.ok) {
        setMessage(msg, r.data.error || "Could not load interviews.", "error");
        return;
      }
      var pick = pickLatestPausedInterview(r.data.interviews);
      if (!pick || !pick.session_id) {
        setMessage(msg, "No paused interviews to resume.", "error");
        return;
      }
      storeInterviewContext(pick);
      restoreInterviewChatFromSessionId(pick.session_id);
    });
  }

  function wireProfile() {
    var startBtn = $("btn-profile-start-interview");
    if (startBtn) {
      startBtn.addEventListener("click", function () {
        showUploadView(getStoredUserEmail());
      });
    }

    var resumeBtn = $("btn-profile-resume-interview");
    if (resumeBtn) {
      resumeBtn.addEventListener("click", resumeLatestPausedInterview);
    }

    var completedLink = $("link-profile-completed");
    if (completedLink) {
      completedLink.addEventListener("click", function () {
        loadProfileInterviewTable("completed");
      });
    }

    var pausedLink = $("link-profile-paused");
    if (pausedLink) {
      pausedLink.addEventListener("click", function () {
        loadProfileInterviewTable("paused");
      });
    }

    var profileUpload = $("form-profile-upload");
    if (profileUpload) {
      profileUpload.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var msg = $("profile-message");
        clearMessage(msg);

        if (!isSignedIn()) {
          setMessage(msg, "Session missing. Please sign in again.", "error");
          handleUnauthorized();
          return;
        }

        var input = ev.target.querySelector('input[type="file"]');
        if (!input || !input.files || !input.files[0]) {
          setMessage(msg, "Choose a PDF, DOC, or DOCX file.", "error");
          return;
        }
        var fileName = (input.files[0].name || "").toLowerCase();
        if (!/\.(pdf|doc|docx)$/.test(fileName)) {
          setMessage(msg, "Only PDF, DOC, and DOCX files are supported.", "error");
          return;
        }

        var fd = new FormData();
        fd.append("resume", input.files[0], input.files[0].name);
        var btn = ev.target.querySelector('button[type="submit"]');
        btn.disabled = true;

        fetch("/api/resumes", {
          method: "POST",
          credentials: fetchCredentials(),
          headers: authHeaders(),
          body: fd,
        })
          .then(function (res) {
            return res.json().then(function (data) {
              return { ok: res.ok, status: res.status, data: data };
            });
          })
          .then(function (r) {
            if (r.status === 401) {
              handleUnauthorized();
              return;
            }
            if (r.ok) {
              ev.target.reset();
              setMessage(msg, r.data.message || "Resume uploaded.", "ok");
              loadProfileResumes();
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

    var settingsForm = $("form-profile-interview-settings");
    if (settingsForm) {
      settingsForm.addEventListener("submit", function (ev) {
        ev.preventDefault();
        var msg = $("profile-message");
        clearMessage(msg);

        if (!isSignedIn()) {
          setMessage(msg, "Session missing. Please sign in again.", "error");
          handleUnauthorized();
          return;
        }

        var input = $("profile-max-questions-input");
        var raw = input ? String(input.value || "").trim() : "";
        var parsed = parseInt(raw, 10);
        var minimum = input && input.min ? parseInt(input.min, 10) : 4;
        if (!raw || isNaN(parsed) || parsed < minimum) {
          setMessage(msg, "Enter at least " + minimum + " questions per interviewer.", "error");
          return;
        }

        var btn = settingsForm.querySelector('button[type="submit"]');
        if (btn) btn.disabled = true;
        apiPut("/api/users/profile/interview-settings", {
          max_questions_per_interviewer: parsed,
        })
          .then(function (r) {
            if (!r.ok) {
              setMessage(msg, r.data.error || "Could not save interview setting.", "error");
              return;
            }
            if (r.data.interview_settings) {
              renderProfileInterviewSettings(r.data.interview_settings);
            }
            setMessage(msg, r.data.message || "Interview setting saved.", "ok");
          })
          .catch(function () {
            setMessage(msg, "Network error. Try again.", "error");
          })
          .finally(function () {
            if (btn) btn.disabled = false;
          });
      });
    }

    var resetSettingsBtn = $("btn-profile-max-questions-reset");
    if (resetSettingsBtn) {
      resetSettingsBtn.addEventListener("click", function () {
        var msg = $("profile-message");
        clearMessage(msg);

        if (!isSignedIn()) {
          setMessage(msg, "Session missing. Please sign in again.", "error");
          handleUnauthorized();
          return;
        }

        resetSettingsBtn.disabled = true;
        apiPut("/api/users/profile/interview-settings", {
          max_questions_per_interviewer: null,
        })
          .then(function (r) {
            if (!r.ok) {
              setMessage(msg, r.data.error || "Could not reset interview setting.", "error");
              return;
            }
            if (r.data.interview_settings) {
              renderProfileInterviewSettings(r.data.interview_settings);
            }
            setMessage(msg, r.data.message || "Using app default.", "ok");
          })
          .catch(function () {
            setMessage(msg, "Network error. Try again.", "error");
          })
          .finally(function () {
            resetSettingsBtn.disabled = false;
          });
      });
    }

    function backToProfile() {
      showProfileView(getStoredUserEmail());
    }

    function backToProfileAfterInterview() {
      setStoredInterviewSession("");
      hidePausedInterviewBanners();
      backToProfile();
    }
    var backUpload = $("btn-back-profile-upload");
    if (backUpload) backUpload.addEventListener("click", backToProfile);
    var backJob = $("btn-back-profile-job");
    if (backJob) backJob.addEventListener("click", backToProfile);
    var backChat = $("btn-back-profile-chat");
    if (backChat) backChat.addEventListener("click", backToProfile);
    var backAfterInterview = $("btn-back-profile-after-interview");
    if (backAfterInterview) backAfterInterview.addEventListener("click", backToProfileAfterInterview);
  }

  function wireUpload() {
    $("form-upload").addEventListener("submit", function (ev) {
      ev.preventDefault();
      var msg = $("upload-message");
      clearMessage(msg);

      if (!isSignedIn()) {
        setMessage(msg, "Session missing. Please sign in again.", "error");
        handleUnauthorized();
        return;
      }

      var input = ev.target.querySelector('input[type="file"]');
      if (!input || !input.files || !input.files[0]) {
        setMessage(msg, "Choose a PDF, DOC, or DOCX file.", "error");
        return;
      }
      var fileName = (input.files[0].name || "").toLowerCase();
      if (!/\.(pdf|doc|docx)$/.test(fileName)) {
        setMessage(msg, "Only PDF, DOC, and DOCX files are supported.", "error");
        return;
      }

      var fd = new FormData();
      fd.append("resume", input.files[0], input.files[0].name);

      var btn = ev.target.querySelector('button[type="submit"]');
      btn.disabled = true;

      fetch("/api/resumes", {
        method: "POST",
        credentials: fetchCredentials(),
        headers: authHeaders(),
        body: fd,
      })
        .then(function (res) {
          return res.json().then(function (data) {
            return { ok: res.ok, status: res.status, data: data };
          });
        })
        .then(function (r) {
          if (r.status === 401) {
            handleUnauthorized();
            return;
          }
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
      var msg = $("job-message");
      var out = $("job-result");
      clearMessage(msg);
      if (out) {
        out.classList.add("is-hidden");
        out.textContent = "";
      }

      if (!isSignedIn()) {
        setMessage(msg, "Session missing. Please sign in again.", "error");
        handleUnauthorized();
        return;
      }

      var fd = new FormData(ev.target);
      var mode = getActiveJobInputMode();
      var body = {
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

  function loadResumeDetail(resumeId, msgEl) {
    return apiGet("/api/resumes/" + encodeURIComponent(resumeId)).then(function (r) {
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

  function renderResumeTable(resumes, msgEl) {
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
        loadResumeDetail(item.resume_id, msgEl);
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
      var msg = $("upload-message");
      clearMessage(msg);
      showElement($("resume-list-wrap"), false);
      showElement($("resume-selected-wrap"), false);
      showElement($("btn-continue-job"), false);

      if (!isSignedIn()) {
        setMessage(msg, "Session missing. Please sign in again.", "error");
        handleUnauthorized();
        return;
      }

      btn.disabled = true;
      apiGet("/api/resumes")
        .then(function (r) {
          if (!r.ok) {
            setMessage(msg, r.data.error || "Could not fetch resumes.", "error");
            return;
          }
          var resumes = r.data.resumes || [];
          if (resumes.length === 0) {
            setMessage(msg, "No saved resumes found. Upload a resume first.", "error");
            return;
          }
          if (resumes.length === 1) {
            return loadResumeDetail(resumes[0].resume_id, msg);
          }
          renderResumeTable(resumes, msg);
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
    var resumeId = getStoredResumeId();
    var jobAppId = getStoredJobApplicationId();
    var msg = $("job-message") || $("chat-message");

    if (!isSignedIn() || !resumeId || !jobAppId) {
      setMessage(msg, "Resume and job application are required before starting the interview.", "error");
      return Promise.resolve();
    }

    setMessage(msg, "Starting interview…", "ok");
    return apiJson("/api/interview/start", {
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

    var btnDownloadReport = $("btn-download-interview-report");
    if (btnDownloadReport) {
      btnDownloadReport.addEventListener("click", function () {
        downloadInterviewReportPdf(getStoredInterviewSession(), $("chat-message"));
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
    if (!sessionId || !isSignedIn()) return;
    restoreInterviewChatFromSessionId(sessionId);
  }

  function wireSignOut() {
    function signOut() {
      showElement($("resume-list-wrap"), false);
      showElement($("resume-selected-wrap"), false);
      showElement($("btn-continue-job"), false);
      showElement($("btn-start-interview"), false);
      showElement($("interview-feedback-wrap"), false);
      showElement($("btn-back-profile-after-interview"), false);
      showElement($("btn-download-interview-report"), false);
      var reportEl = $("interview-report");
      if (reportEl) reportEl.textContent = "";
      showElement($("form-chat"), true);
      var tbody = $("resume-table-body");
      if (tbody) tbody.textContent = "";
      var textarea = $("resume-parsed-display");
      if (textarea) textarea.value = "";
      var chatBox = $("chat-messages");
      if (chatBox) chatBox.textContent = "";
      hidePausedInterviewBanners();
      apiJson("/api/users/logout", {}).finally(function () {
        handleUnauthorized();
      });
    }
    $("btn-sign-out").addEventListener("click", signOut);
    var profileBtn = $("btn-sign-out-profile");
    if (profileBtn) profileBtn.addEventListener("click", signOut);
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
    wireProfile();
    wireUpload();
    wireFetchResume();
    wireContinueToJob();
    wireJobApplication();
    wireStartInterview();
    wireInterviewChat();
    wireContinuePausedInterview();
    wireSignOut();

    restoreSessionFromServer().then(function (ok) {
      if (!ok) {
        showAuthView();
        return;
      }
      afterAuthSuccess(getStoredUserEmail());
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();

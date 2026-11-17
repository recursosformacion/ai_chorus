(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const MSG_LANG = (navigator.language || "es").slice(0, 2);
  const MSG_TEXT = {
    es: {
      eyebrow: "COMUNICADOS", title: "Mensajes del grupo", unread: "{n} sin leer",
      group: "Grupo", new: "Nuevo mensaje", to: "Para", people: "Personas",
      subject: "Asunto", body: "Mensaje", send: "Enviar",
      emptyTitle: "Sin grupo para comunicados",
      emptyText: "Cuando formes parte de un grupo podrás escribir a su administración, a todo el coro o a personas concretas.",
      scope_group: "Todo el grupo", scope_managers: "Administración del grupo",
      scope_users: "Una o varias personas", noMessages: "Todavía no hay mensajes en este grupo.",
      markRead: "Marcar como leído", sent: "Mensaje enviado.", choose: "Elige al menos una persona.",
      adminShort: "admin.", sending: "Enviando…",
    },
    en: {
      eyebrow: "MESSAGES", title: "Group messages", unread: "{n} unread",
      group: "Group", new: "New message", to: "To", people: "People",
      subject: "Subject", body: "Message", send: "Send",
      emptyTitle: "No group for messages",
      emptyText: "Once you belong to a group you can write to its managers, the whole choir or specific people.",
      scope_group: "Whole group", scope_managers: "Group managers",
      scope_users: "One or more people", noMessages: "There are no messages in this group yet.",
      markRead: "Mark as read", sent: "Message sent.", choose: "Choose at least one person.",
      adminShort: "manager", sending: "Sending…",
    },
    ca: {
      eyebrow: "COMUNICATS", title: "Missatges del grup", unread: "{n} sense llegir",
      group: "Grup", new: "Nou missatge", to: "Per a", people: "Persones",
      subject: "Assumpte", body: "Missatge", send: "Enviar",
      emptyTitle: "Sense grup per a comunicats",
      emptyText: "Quan formis part d'un grup podràs escriure a la seva administració, a tot el cor o a persones concretes.",
      scope_group: "Tot el grup", scope_managers: "Administració del grup",
      scope_users: "Una o diverses persones", noMessages: "Encara no hi ha missatges en aquest grup.",
      markRead: "Marcar com a llegit", sent: "Missatge enviat.", choose: "Tria almenys una persona.",
      adminShort: "admin.", sending: "Enviant…",
    },
    fr: {
      eyebrow: "MESSAGES", title: "Messages du groupe", unread: "{n} non lus",
      group: "Groupe", new: "Nouveau message", to: "À", people: "Personnes",
      subject: "Objet", body: "Message", send: "Envoyer",
      emptyTitle: "Aucun groupe pour les messages",
      emptyText: "Quand vous ferez partie d'un groupe, vous pourrez écrire à ses responsables, à tout le chœur ou à des personnes précises.",
      scope_group: "Tout le groupe", scope_managers: "Responsables du groupe",
      scope_users: "Une ou plusieurs personnes", noMessages: "Il n'y a pas encore de messages dans ce groupe.",
      markRead: "Marquer comme lu", sent: "Message envoyé.", choose: "Choisissez au moins une personne.",
      adminShort: "resp.", sending: "Envoi…",
    },
    de: {
      eyebrow: "MITTEILUNGEN", title: "Gruppennachrichten", unread: "{n} ungelesen",
      group: "Gruppe", new: "Neue Nachricht", to: "An", people: "Personen",
      subject: "Betreff", body: "Nachricht", send: "Senden",
      emptyTitle: "Keine Gruppe für Mitteilungen",
      emptyText: "Sobald du zu einer Gruppe gehörst, kannst du deren Leitung, dem ganzen Chor oder einzelnen Personen schreiben.",
      scope_group: "Ganze Gruppe", scope_managers: "Gruppenleitung",
      scope_users: "Eine oder mehrere Personen", noMessages: "In dieser Gruppe gibt es noch keine Nachrichten.",
      markRead: "Als gelesen markieren", sent: "Nachricht gesendet.", choose: "Wähle mindestens eine Person.",
      adminShort: "Leitung", sending: "Senden…",
    },
  };
  const msgT = (key) => (MSG_TEXT[MSG_LANG] || MSG_TEXT.es)[key] || MSG_TEXT.es[key] || key;
  function applyMessageI18n() {
    document.querySelectorAll("[data-msg]").forEach((el) => {
      if (el.id === "msg-unread") return;
      el.textContent = msgT(el.dataset.msg);
    });
  }
  let accessToken = null;
  let currentDraft = null;
  let lastResults = [];

  function showMessage(id, message, kind = "") {
    const el = $(id);
    el.textContent = message || "";
    el.className = "message" + (kind ? " " + kind : "");
  }
  function setBusy(button, busy, label) {
    if (!button.dataset.label) button.dataset.label = button.textContent;
    button.disabled = busy;
    button.textContent = busy ? label : button.dataset.label;
  }
  async function request(path, options = {}, retry = true) {
    const headers = new Headers(options.headers || {});
    if (accessToken) headers.set("Authorization", "Bearer " + accessToken);
    if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
    let response = await fetch(path, {...options, headers, credentials:"same-origin"});
    if (response.status === 401 && retry && path !== "/api/v1/auth/refresh" && path !== "/api/v1/auth/login") {
      const refreshed = await refreshSession();
      if (refreshed) return request(path, options, false);
    }
    if (!response.ok) {
      let detail = "Error " + response.status;
      try { const body = await response.json(); detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || body); } catch (_) {}
      throw new Error(detail);
    }
    if (response.status === 204) return null;
    return response.json();
  }
  async function downloadBlob(path, fallbackName) {
    const headers = new Headers();
    if (accessToken) headers.set("Authorization", "Bearer " + accessToken);
    const response = await fetch(path, {headers, credentials: "same-origin"});
    if (!response.ok) throw new Error("No se pudo descargar el fichero");
    const disposition = response.headers.get("content-disposition") || "";
    const match = /filename\*?=(?:UTF-8'')?"?([^";]+)/i.exec(disposition);
    const name = match ? decodeURIComponent(match[1]) : fallbackName;
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = name;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }
  async function refreshSession() {
    try {
      const response = await fetch("/api/v1/auth/refresh", {method:"POST", credentials:"same-origin"});
      if (!response.ok) { accessToken = null; return false; }
      const data = await response.json();
      accessToken = data.access_token;
      if (data.onboarding && data.onboarding.required) throw new Error("Tu cuenta necesita completar el alta de OSAP antes de utilizar Chorus.");
      return true;
    } catch (error) {
      accessToken = null;
      if (error.message) showMessage("login-error", error.message, "error");
      return false;
    }
  }
  function showWorkspace(profileLabel) {
    $("login-view").classList.add("hidden");
    $("workspace-view").classList.remove("hidden");
    $("logout-button").classList.remove("hidden");
    $("app-nav").classList.remove("hidden");
    $("inbox-button").classList.remove("hidden");
    void refreshUnread();
    $("account-label").textContent = profileLabel || "Sesión iniciada";
    const rawName = String(profileLabel || "").split("@")[0].replace(/[._-]+/g, " ").trim();
    const displayName = rawName ? rawName.charAt(0).toUpperCase() + rawName.slice(1) : "músico";
    if ($("dash-name")) $("dash-name").textContent = displayName;
    refreshLibrary().catch(()=>{});
    loadAgenda().catch(()=>{});
  }
  function showLogin() {
    $("workspace-view").classList.add("hidden");
    $("login-view").classList.remove("hidden");
    $("logout-button").classList.add("hidden");
    $("app-nav").classList.add("hidden");
    $("account-label").textContent = "";
  }
  async function refreshLibrary(query) {
    const path = query
      ? "/api/v1/library?q=" + encodeURIComponent(query)
      : "/api/v1/library";
    const data = await request(path);
    renderLibrary(data || {});
  }
  let agendaState = { groups: [], entities: [], events: [], can_create_group: false };

  function kindLabel(kind) {
    return { rehearsal: "Ensayo", concert: "Actuación", note: "Nota" }[kind] || kind;
  }

  function formatDateOnly(value) {
    try {
      return new Intl.DateTimeFormat("es-ES", {
        day: "2-digit", month: "2-digit", year: "numeric",
      }).format(new Date(value));
    } catch (_) {
      return value || "";
    }
  }

  function formatEventDate(value) {
    try {
      return new Intl.DateTimeFormat("es-ES", {
        day: "2-digit", month: "2-digit", year: "numeric",
        hour: "2-digit", minute: "2-digit",
      }).format(new Date(value));
    } catch (_) {
      return value || "";
    }
  }

  async function loadAgenda() {
    agendaState = await request("/api/v1/agenda");
    renderAgenda();
    await loadMessages();
  }

  function renderGroupCard() {
    const groups = agendaState.groups || [];
    const content = $("dash-group-content");
    const empty = $("dash-group-empty");
    if (groups.length) {
      const group = groups[0];
      content.classList.remove("hidden");
      empty.classList.add("hidden");
      content.replaceChildren();
      const identity = document.createElement("div");
      identity.className = "group-identity";
      const mark = document.createElement("span");
      mark.className = "group-mark";
      mark.textContent = (group.name || "G").slice(0, 2).toUpperCase();
      const box = document.createElement("div");
      const title = document.createElement("h2");
      title.textContent = group.name;
      const subtitle = document.createElement("p");
      subtitle.className = "muted";
      subtitle.textContent = (group.role === "manager" ? "Responsable" : "Miembro")
        + (groups.length > 1 ? ` · ${groups.length} grupos` : "");
      box.append(title, subtitle);
      identity.append(mark, box);
      content.append(identity);
      if (group.join_code) {
        const code = document.createElement("p");
        code.className = "dash-group-code";
        code.append("Código para invitar: ");
        const strong = document.createElement("strong");
        strong.textContent = group.join_code;
        code.append(strong);
        content.append(code);
      }
      const menu = document.createElement("div");
      menu.className = "dash-group-menu";
      const menuTitle = document.createElement("p");
      menuTitle.className = "muted";
      menuTitle.textContent = "Mis grupos";
      menu.append(menuTitle);
      groups.forEach((item) => {
        const row = document.createElement("div");
        row.className = "dash-group-row";
        const name = document.createElement("span");
        name.textContent = item.name;
        row.append(name);
        if (item.can_manage) {
          const badge = document.createElement("span");
          badge.className = "badge badge-gold";
          badge.textContent = item.role === "manager" ? "Administro" : "Gestiono";
          row.append(badge);
        }
        const button = document.createElement("button");
        button.type = "button";
        button.className = "button button-outline button-small";
        button.textContent = item.can_manage ? "Gestionar" : "Abrir";
        button.addEventListener("click", () => {
          if (item.can_manage) {
            void openGroupAdmin(item);
            return;
          }
          messageState.groupId = item.id;
          $("msg-group").value = item.id;
          document.getElementById("dashboard-comunicados").scrollIntoView({
            behavior: "smooth",
            block: "start",
          });
          void loadMessages();
        });
        row.append(button);
        const messages = document.createElement("button");
        messages.type = "button";
        messages.className = "button button-outline button-small";
        messages.textContent = "Mensajes";
        messages.addEventListener("click", () => {
          messageState.groupId = item.id;
          void openInbox(true);
          const select = $("msg-group");
          if (!Array.from(select.options).some((option) => option.value === item.id)) {
            select.append(new Option(item.name, item.id));
          }
          select.value = item.id;
          $("msg-form").classList.remove("hidden");
          void loadMessages();
        });
        row.append(messages);
        menu.append(row);
      });
      content.append(menu);
      return;
    }
    content.classList.add("hidden");
    empty.classList.remove("hidden");
    const form = $("dash-group-form");
    form.classList.toggle(
      "hidden", !(agendaState.can_create_group && (agendaState.entities || []).length),
    );
    const select = $("dash-group-entity");
    select.replaceChildren(new Option("— Elegir entidad —", ""));
    (agendaState.entities || []).forEach((entity) => {
      select.append(new Option(`${entity.name} (${entity.kind})`, entity.id));
    });
  }

  function renderEvent(event, primary) {
    const card = document.createElement("article");
    card.className = "dash-event" + (primary ? " dash-event-primary" : "");
    const head = document.createElement("div");
    head.className = "dash-event-head";
    const left = document.createElement("div");
    const title = document.createElement("h3");
    title.textContent = event.title;
    const meta = document.createElement("p");
    meta.className = "dash-event-meta";
    meta.textContent = [
      formatEventDate(event.starts_at), event.location, event.group_name,
    ].filter(Boolean).join(" · ");
    left.append(title, meta);
    const kind = document.createElement("span");
    kind.className = "dash-event-kind " + event.kind;
    kind.textContent = kindLabel(event.kind);
    head.append(left, kind);
    card.append(head);
    if (event.notes) {
      const notes = document.createElement("p");
      notes.className = "dash-event-notes";
      notes.textContent = event.notes;
      card.append(notes);
    }
    if (event.rsvp_required) {
      const row = document.createElement("div");
      row.className = "rsvp-buttons";
      [["yes", "Asisto"], ["no", "No asisto"]].forEach(([status, text]) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "rsvp" + (event.my_rsvp === status ? " selected" : "");
        button.textContent = text;
        button.addEventListener("click", () => { void setRsvp(event.id, status, button); });
        row.append(button);
      });
      const state = document.createElement("span");
      state.className = "rsvp-status";
      if (event.my_rsvp === "yes") {
        state.textContent = event.my_rsvp_updated_at
          ? `Confirmado el ${formatDateOnly(event.my_rsvp_updated_at)}`
          : "Confirmado";
      } else if (event.my_rsvp === "no") {
        state.textContent = "No asistiré";
      } else {
        state.textContent = "Pendiente de confirmación";
      }
      row.append(state);
      card.append(row);
    }
    return card;
  }

  function renderAgenda() {
    const events = agendaState.events || [];
    const content = $("dash-next-content");
    const empty = $("dash-next-empty");
    const badge = $("dash-event-badge");
    if (events.length) {
      content.classList.remove("hidden");
      empty.classList.add("hidden");
      badge.textContent = `${events.length} ${events.length === 1 ? "evento" : "eventos"}`;
      badge.className = "badge " + (events[0].my_rsvp ? "badge-green" : "badge-gold");
      content.replaceChildren();
      events.forEach((event, index) => content.append(renderEvent(event, index === 0)));
    } else {
      content.classList.add("hidden");
      content.replaceChildren();
      empty.classList.remove("hidden");
      badge.textContent = "Sin agenda";
      badge.className = "badge badge-muted";
    }
    const manageable = (agendaState.groups || []).filter((group) => group.can_manage);
    $("dash-event-admin").classList.remove("hidden");
    const scopeSelect = $("dash-event-scope");
    Array.from(scopeSelect.options).forEach((option) => {
      if (option.value !== "personal") option.disabled = manageable.length === 0;
    });
    if (!manageable.length) scopeSelect.value = "personal";
    const select = $("dash-event-group");
    select.replaceChildren();
    manageable.forEach((group) => select.append(new Option(group.name, group.id)));
    renderGroupCard();
  }

  let messageState = { groupId: "", messages: [], people: [], catalog: { admin: [], musical: [], section: [] } };

  function messageScopeLabel(scope) {
    return msgT("scope_" + scope) || scope;
  }

  function renderMessageGroups() {
    const groups = agendaState.groups || [];
    const content = $("msg-content");
    const empty = $("msg-empty");
    content.classList.toggle("hidden", groups.length === 0);
    empty.classList.toggle("hidden", groups.length > 0);
    const select = $("msg-group");
    const previous = messageState.groupId || select.value;
    select.replaceChildren();
    groups.forEach((group) => select.append(new Option(group.name, group.id)));
    if (!groups.length) {
      messageState = { groupId: "", messages: [] };
      return;
    }
    const exists = groups.some((group) => group.id === previous);
    select.value = exists ? previous : groups[0].id;
    messageState.groupId = select.value;
  }

  async function loadMessages() {
    renderMessageGroups();
    if (!messageState.groupId) return;
    try {
      const rows = await request(
        `/api/v1/groups/${encodeURIComponent(messageState.groupId)}/messages`,
      );
      messageState.messages = Array.isArray(rows) ? rows : [];
      renderMessages();
      await Promise.all([loadMessagePeople(), loadMessageCatalog()]);
    } catch (error) {
      showMessage("msg-message", error.message, "error");
    }
  }

  function renderMessages() {
    const list = $("msg-list");
    list.replaceChildren();
    const rows = messageState.messages || [];
    const unread = rows.filter((row) => !row.is_sender && !row.my_read_at).length;
    const badge = $("msg-unread");
    badge.textContent = msgT("unread").replace("{n}", String(unread));
    badge.className = "badge " + (unread ? "badge-gold" : "badge-muted");
    if (!rows.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = msgT("noMessages");
      list.append(empty);
      return;
    }
    rows.forEach((row) => {
      const article = document.createElement("article");
      article.className = "dash-message" + (row.my_read_at || row.is_sender ? "" : " unread");
      const head = document.createElement("div");
      head.className = "dash-message-head";
      const title = document.createElement("h3");
      title.textContent = row.subject;
      const meta = document.createElement("span");
      meta.className = "badge badge-muted";
      meta.textContent = messageScopeLabel(row.scope);
      head.append(title, meta);
      const info = document.createElement("p");
      info.className = "dash-event-meta";
      info.textContent = `${row.sender_name} · ${formatEventDate(row.created_at)}`;
      const body = document.createElement("p");
      body.className = "dash-message-body";
      body.textContent = row.body;
      article.append(head, info, body);
      if (!row.is_sender && !row.my_read_at) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "button button-quiet button-small";
        button.textContent = msgT("markRead");
        button.addEventListener("click", () => {
          void markMessageRead(row.id, button);
        });
        article.append(button);
      }
      list.append(article);
    });
  }

  function renderRecipients() {
    const select = $("msg-recipients");
    select.replaceChildren();
    const term = ($("msg-people-search").value || "").toLowerCase();
    const admin = $("msg-filter-admin").value;
    const musical = $("msg-filter-musical").value;
    const section = $("msg-filter-section").value;
    messageState.people
      .filter((member) => !term || String(member.name || "").toLowerCase().includes(term))
      .filter((member) => !admin || member.admin_role_id === admin)
      .filter((member) => !musical || member.musical_role_id === musical)
      .filter((member) => !section || member.section_id === section)
      .forEach((member) => {
        const label = `${member.name}${member.role === "manager" ? " (" + msgT("adminShort") + ")" : ""}`;
        select.append(new Option(label, member.user_sub));
      });
  }

  async function loadMessagePeople() {
    if (!messageState.groupId) return;
    try {
      const rows = await request(
        `/api/v1/groups/${encodeURIComponent(messageState.groupId)}/members`,
      );
      messageState.people = Array.isArray(rows) ? rows : [];
      renderRecipients();
    } catch (_) {
      messageState.people = [];
    }
  }

  async function loadMessageCatalog() {
    if (!messageState.groupId) return;
    try {
      const data = await request(
        `/api/v1/groups/${encodeURIComponent(messageState.groupId)}/catalog`,
      );
      messageState.catalog = data || { admin: [], musical: [], section: [] };
      const filters = [
        ["admin", "msg-filter-admin", "Cargo"],
        ["musical", "msg-filter-musical", "Rol musical"],
        ["section", "msg-filter-section", "Sección"],
      ];
      for (const [scope, id, empty] of filters) {
        const select = $(id);
        select.replaceChildren(new Option(empty, ""));
        (messageState.catalog[scope] || []).forEach((item) => {
          select.append(new Option(item.name, item.id || ""));
        });
      }
    } catch (_) {
      /* sin catálogo */
    }
  }

  async function sendMessage(event) {
    event.preventDefault();
    if (!messageState.groupId) return;
    const scope = $("msg-scope").value;
    const recipients = Array.from($("msg-recipients").selectedOptions).map(
      (option) => option.value,
    );
    if (scope === "users" && !recipients.length) {
      showMessage("msg-message", msgT("choose"), "error");
      return;
    }
    const button = event.submitter || $("msg-form").querySelector("button[type=submit]");
    setBusy(button, true, msgT("sending"));
    try {
      await request(`/api/v1/groups/${encodeURIComponent(messageState.groupId)}/messages`, {
        method: "POST",
        body: JSON.stringify({
          scope,
          subject: $("msg-subject").value.trim(),
          body: $("msg-body").value.trim(),
          recipient_subs: recipients,
        }),
      });
      $("msg-subject").value = "";
      $("msg-body").value = "";
      $("msg-form").classList.add("hidden");
      showMessage("msg-message", msgT("sent"), "success");
      await loadMessages();
    } catch (error) {
      showMessage("msg-message", error.message, "error");
    } finally {
      setBusy(button, false);
    }
  }

  async function markMessageRead(messageId, button) {
    setBusy(button, true, "Guardando…");
    try {
      await request(`/api/v1/messages/${encodeURIComponent(messageId)}/read`, {
        method: "POST",
      });
      await loadMessages();
    } catch (error) {
      showMessage("msg-message", error.message, "error");
    } finally {
      setBusy(button, false);
    }
  }

  let inboxCurrent = null;

  async function refreshUnread() {
    try {
      const data = await request("/api/v1/messages/unread-count");
      const count = Number(data.count || 0);
      $("inbox-count").textContent = String(count);
      $("inbox-button").classList.toggle("badge-gold", count > 0);
    } catch (_) {
      /* silencioso */
    }
  }

  async function openInbox() {
    $("inbox-modal").classList.remove("hidden");
    $("inbox-detail").classList.add("hidden");
    $("inbox-list").classList.remove("hidden");
    try {
      const rows = await request("/api/v1/messages/inbox");
      const list = $("inbox-list");
      list.replaceChildren();
      if (!rows.length) {
        const p = document.createElement("p");
        p.className = "muted";
        p.textContent = "No tienes mensajes.";
        list.append(p);
        return;
      }
      rows.forEach((row) => {
        const item = document.createElement("div");
        item.className = "inbox-item" + (row.my_read_at || row.is_sender ? "" : " unread");
        const left = document.createElement("div");
        const subject = document.createElement("strong");
        subject.textContent = `${row.subject} · ${row.group_name}`;
        const meta = document.createElement("p");
        meta.className = "muted";
        meta.textContent = row.created_at;
        left.append(subject, meta);
        item.append(left);
        item.addEventListener("click", () => void openInboxMessage(row.id));
        list.append(item);
      });
    } catch (error) {
      showMessage("inbox-message", error.message, "error");
    }
  }

  async function openInboxMessage(messageId) {
    try {
      const row = await request(`/api/v1/messages/${encodeURIComponent(messageId)}`);
      inboxCurrent = row;
      $("inbox-list").classList.add("hidden");
      $("inbox-detail").classList.remove("hidden");
      $("inbox-subject").textContent = `${row.subject} · ${row.group_name}`;
      $("inbox-meta").textContent = `${row.sender_sub} · ${row.created_at}`;
      $("inbox-body").textContent = row.body;
      $("inbox-reply-body").value = "";
      await request(`/api/v1/messages/${encodeURIComponent(messageId)}/read`, { method: "POST" });
      await refreshUnread();
    } catch (error) {
      showMessage("inbox-message", error.message, "error");
    }
  }

  async function sendInboxReply(event) {
    event.preventDefault();
    if (!inboxCurrent) return;
    const text = $("inbox-reply-body").value.trim();
    if (!text) return;
    try {
      await request(`/api/v1/messages/${encodeURIComponent(inboxCurrent.id)}/reply`, {
        method: "POST",
        body: JSON.stringify({ body: text }),
      });
      $("inbox-reply-body").value = "";
      showMessage("inbox-message", "Respuesta enviada.", "success");
      await openInbox();
    } catch (error) {
      showMessage("inbox-message", error.message, "error");
    }
  }
  let groupAdminState = { group: null, catalog: { admin: [], musical: [], section: [] }, members: [] };

  function _options(items, selected, empty) {
    const fragment = document.createDocumentFragment();
    fragment.append(new Option(empty, ""));
    (items || []).forEach((item) => {
      fragment.append(new Option(item.name, item.id || "", false, item.id === selected));
    });
    return fragment;
  }

  async function openGroupAdmin(item) {
    groupAdminState.group = item;
    $("group-admin-modal").classList.remove("hidden");
    $("ga-title").textContent = item.name;
    $("ga-name").value = item.name;
    $("ga-timezone").value = item.timezone || "Europe/Madrid";
    try {
      const [catalog, members] = await Promise.all([
        request(`/api/v1/groups/${encodeURIComponent(item.id)}/catalog`).catch(() => ({
          admin: [], musical: [], section: [],
        })),
        request(`/api/v1/groups/${encodeURIComponent(item.id)}/members`),
      ]);
      groupAdminState.catalog = catalog || { admin: [], musical: [], section: [] };
      groupAdminState.members = Array.isArray(members) ? members : [];
      renderGroupMembers();
    } catch (error) {
      showMessage("ga-message", error.message, "error");
    }
  }

  function renderGroupMembers() {
    const container = $("ga-members");
    container.replaceChildren();
    const catalog = groupAdminState.catalog;
    groupAdminState.members.forEach((member) => {
      const row = document.createElement("div");
      row.className = "ga-member";
      const name = document.createElement("strong");
      name.textContent = member.name || member.user_sub;
      const role = document.createElement("select");
      role.append(new Option("Miembro", "member", false, member.role === "member"));
      role.append(new Option("Gestor", "manager", false, member.role === "manager"));
      const admin = document.createElement("select");
      admin.append(_options(catalog.admin, member.admin_role_id, "Cargo"));
      const musical = document.createElement("select");
      musical.append(_options(catalog.musical, member.musical_role_id, "Rol musical"));
      const section = document.createElement("select");
      section.append(_options(catalog.section, member.section_id, "Sección"));
      const save = document.createElement("button");
      save.type = "button";
      save.className = "button button-primary button-small";
      save.textContent = "Guardar";
      save.addEventListener("click", async () => {
        try {
          await request(
            `/api/v1/groups/${encodeURIComponent(groupAdminState.group.id)}/members/${encodeURIComponent(member.user_sub)}`,
            {
              method: "PATCH",
              body: JSON.stringify({
                role: role.value,
                admin_role_id: admin.value || null,
                musical_role_id: musical.value || null,
                section_id: section.value || null,
              }),
            },
          );
          showMessage("ga-message", "Miembro actualizado.", "success");
          await openGroupAdmin(groupAdminState.group);
        } catch (error) {
          showMessage("ga-message", error.message, "error");
        }
      });
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "button button-quiet button-small";
      remove.textContent = "Quitar";
      remove.addEventListener("click", async () => {
        if (!confirm(`¿Dar de baja a ${member.name || member.user_sub}?`)) return;
        try {
          await request(
            `/api/v1/groups/${encodeURIComponent(groupAdminState.group.id)}/members/${encodeURIComponent(member.user_sub)}`,
            { method: "DELETE" },
          );
          await openGroupAdmin(groupAdminState.group);
        } catch (error) {
          showMessage("ga-message", error.message, "error");
        }
      });
      row.append(name, role, admin, musical, section, save, remove);
      container.append(row);
    });
  }

  async function saveGroupData(event) {
    event.preventDefault();
    if (!groupAdminState.group) return;
    try {
      await request(`/api/v1/groups/${encodeURIComponent(groupAdminState.group.id)}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: $("ga-name").value.trim(),
          timezone: $("ga-timezone").value.trim(),
        }),
      });
      showMessage("ga-message", "Datos del grupo guardados.", "success");
      await loadAgenda();
    } catch (error) {
      showMessage("ga-message", error.message, "error");
    }
  }
  async function setRsvp(eventId, status, button) {
    setBusy(button, true, "Guardando…");
    try {
      await request(`/api/v1/events/${encodeURIComponent(eventId)}/rsvp`, {
        method: "POST",
        body: JSON.stringify({ status }),
      });
      await loadAgenda();
      showMessage(
        "dash-event-message",
        status === "yes" ? "Asistencia confirmada." : "Ausencia registrada.",
        "success",
      );
    } catch (error) {
      showMessage("dash-event-message", error.message, "error");
      setBusy(button, false);
    }
  }

  function renderLibrary(data) {
    const items = data.items || [];
    const collections = data.collections || [];
    $("library-summary").textContent = items.length + " elementos · " + collections.length + " colecciones";
    if ($("dash-library-count")) $("dash-library-count").textContent = items.length;
    if ($("dash-collections-count")) $("dash-collections-count").textContent = collections.length;
    if ($("dash-library-summary")) {
      $("dash-library-summary").textContent = items.length + " elementos · " + collections.length + " colecciones";
    }
    const dashRecent = $("dash-recent");
    if (dashRecent) {
      dashRecent.replaceChildren();
      if (!items.length) {
        const empty = document.createElement("li");
        empty.className = "muted";
        empty.textContent = "Aún no has guardado obras.";
        dashRecent.append(empty);
      } else {
        items.slice(0, 3).forEach((item) => {
          const li = document.createElement("li");
          const cover = document.createElement("span");
          cover.className = "mini-cover";
          cover.setAttribute("aria-hidden", "true");
          cover.textContent = "♫";
          const info = document.createElement("div");
          const title = document.createElement("strong");
          title.textContent = item.title || "Sin título";
          const meta = document.createElement("span");
          meta.className = "muted";
          meta.textContent = item.kind === "local_work"
            ? "Obra propia"
            : [item.provider, item.external_work_id].filter(Boolean).join(" · ") || "Referencia OSAP";
          info.append(title, meta);
          li.append(cover, info);
          dashRecent.append(li);
        });
      }
    }
    const list = $("library-items");
    list.replaceChildren();
    if (!items.length) {
      const empty = document.createElement("li");
      empty.className = "muted";
      empty.textContent = "Aún no has guardado obras ni referencias.";
      list.append(empty);
      return;
    }
    items.forEach((item) => {
      const li = document.createElement("li");
      li.className = "library-item";
      const info = document.createElement("div");
      info.className = "library-info";
      const title = document.createElement("strong");
      title.textContent = item.title || "Sin título";
      const meta = document.createElement("span");
      meta.className = "muted";
      meta.textContent = item.kind === "local_work"
        ? "Obra propia"
        : [item.provider, item.external_work_id, item.external_resource_id]
          .filter(Boolean).join(" · ") || "Referencia OSAP";
      info.append(title, meta);

      const actions = document.createElement("div");
      actions.className = "library-actions";
      const canOpen = item.kind !== "osap_reference" || Boolean(item.external_resource_id);
      const open = document.createElement("button");
      open.type = "button";
      open.className = "button button-outline";
      open.textContent = "Abrir en MuseEncore";
      open.disabled = !canOpen;
      open.addEventListener("click", () => {
        void openLibraryItem(item, open);
      });
      const download = document.createElement("button");
      download.type = "button";
      download.className = "button button-quiet";
      download.textContent = "Descargar";
      download.title = "Descargar para abrir con MuseScore";
      download.disabled = !canOpen;
      download.addEventListener("click", () => {
        void downloadLibraryItem(item);
      });
      actions.append(open, download);
      if (collections.length) {
        const select = document.createElement("select");
        select.className = "library-select";
        select.title = "Colección de destino";
        collections.forEach((collection) => {
          const option = document.createElement("option");
          option.value = collection.id;
          option.textContent = collection.name;
          select.append(option);
        });
        const add = document.createElement("button");
        add.type = "button";
        add.className = "button button-quiet";
        add.textContent = "Añadir a colección";
        add.addEventListener("click", () => {
          void addToCollection(select.value, item.id, add);
        });
        actions.append(select, add);
      }
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "button button-quiet";
      remove.textContent = "Quitar";
      remove.addEventListener("click", () => {
        void removeLibraryItem(item.id, remove);
      });
      actions.append(remove);

      li.append(info, actions);
      list.append(li);
    });
  }
  async function removeLibraryItem(itemId, button) {
    setBusy(button, true, "Quitando…");
    try {
      await request("/api/v1/library/" + encodeURIComponent(itemId), {method: "DELETE"});
      await refreshLibrary($("library-query").value.trim());
      showMessage("library-message", "Elemento quitado de la biblioteca.", "success");
    } catch (error) {
      showMessage("library-message", error.message, "error");
    } finally {
      setBusy(button, false);
    }
  }
  async function addToCollection(collectionId, itemId, button) {
    if (!collectionId) return;
    setBusy(button, true, "Añadiendo…");
    try {
      await request(
        "/api/v1/collections/" + encodeURIComponent(collectionId) + "/items",
        {method: "POST", body: JSON.stringify({library_item_id: itemId})},
      );
      showMessage("library-message", "Añadido a la colección.", "success");
    } catch (error) {
      showMessage("library-message", error.message, "error");
    } finally {
      setBusy(button, false);
    }
  }
  async function downloadDraftSource() {
    if (!currentDraft) return;
    try {
      await downloadBlob(
        "/api/v1/drafts/" + encodeURIComponent(currentDraft.id) + "/source-file",
        "chorus-source.mxl",
      );
      showMessage(
        "draft-message",
        "Descargado. Ábrelo con MuseScore; al terminar, exporta .mxl y súbelo aquí.",
        "success",
      );
    } catch (error) {
      showMessage("draft-message", error.message, "error");
    }
  }
  async function openLibraryItem(item, button) {
    setBusy(button, true, "Preparando…");
    try {
      const draft = await request(
        "/api/v1/library/" + encodeURIComponent(item.id) + "/draft",
        {method: "POST"},
      );
      currentDraft = draft;
      const editor = await request(
        "/api/v1/drafts/" + encodeURIComponent(draft.id) + "/editor",
      );
      const title = item.title || "";
      window.open(
        "/editor.html?v=0.8.0&src=" + encodeURIComponent(editor.editor_url)
          + "&title=" + encodeURIComponent(title),
        "_blank", "noopener",
      );
    } catch (error) {
      showMessage("library-message", error.message, "error");
    } finally {
      setBusy(button, false);
    }
  }
  async function downloadLibraryItem(item) {
    try {
      await downloadBlob(
        "/api/v1/library/" + encodeURIComponent(item.id) + "/download",
        (item.title || "obra") + ".mxl",
      );
      showMessage("library-message", "Descargado para abrir con MuseScore.", "success");
    } catch (error) {
      showMessage("library-message", error.message, "error");
    }
  }
  function openDraftModal(title) {
    $("modal-draft-title").textContent = title || "Tu partitura";
    $("draft-modal").classList.remove("hidden");
  }
  function closeDraftModal() {
    $("draft-modal").classList.add("hidden");
  }
  async function saveReference(work, rep, button, title) {
    const workId = String(work.work_id || work.id || "");
    if (!workId) {
      showMessage("search-message", "OSAP no devolvió un identificador de obra.", "error");
      return;
    }
    setBusy(button, true, "Guardando…");
    try {
      await request("/api/v1/library/references", {method:"POST",body:JSON.stringify({
        provider: String(rep.provider || "osap").toLowerCase(),
        work_id: workId,
        representation_id: rep.id != null ? String(rep.id) : null,
        title: title || work.title || "Obra de OSAP",
        subtitle: work.composer || null
      })});
      showMessage("search-message", "Referencia guardada en tu biblioteca.", "success");
      await refreshLibrary();
    } catch (error) {
      showMessage("search-message", error.message, "error");
    } finally {
      setBusy(button, false);
    }
  }
  async function startOidc() {
    showMessage("login-error", "");
    try {
      const data = await request("/api/v1/auth/oidc/start", {}, false);
      if (!data || !data.authorize_url) throw new Error("El acceso con OSAP no está configurado.");
      const popup = window.open(
        data.authorize_url, "chorus-oidc",
        "width=480,height=640,menubar=no,toolbar=no,status=no,resizable=yes,scrollbars=yes",
      );
      if (!popup) throw new Error("Permite las ventanas emergentes para entrar con OSAP.");
    } catch (error) {
      showMessage("login-error", error.message, "error");
    }
  }
  async function completeHandoff(token, refreshToken) {
    try {
      const data = await request("/api/v1/auth/handoff", {
        method: "POST",
        body: JSON.stringify({ access_token: token, refresh_token: refreshToken || null }),
      }, false);
      accessToken = data.access_token;
      if (data.onboarding && data.onboarding.required) {
        showMessage("login-error", "Completa primero el alta de tu cuenta OSAP.", "error");
        return;
      }
      showWorkspace(data.nickname || data.email || data.user_id);
    } catch (error) {
      accessToken = null;
      showMessage("login-error", error.message || "No se pudo iniciar la sesión desde OSAP.", "error");
    }
  }

  async function completeOidc(accessTokenValue) {
    accessToken = accessTokenValue;
    try {
      const profile = await request("/api/v1/auth/me", {}, false);
      if (profile.onboarding && profile.onboarding.required) {
        showMessage("login-error", "Completa primero el alta de tu cuenta OSAP.", "error");
        return;
      }
      showWorkspace(profile.nickname || profile.email || profile.user_id);
    } catch (error) {
      accessToken = null;
      showMessage("login-error", error.message, "error");
    }
  }
  window.addEventListener("message", (event) => {
    if (event.origin !== location.origin) return;
    const data = event.data || {};
    if (data.type === "chorus-oidc" && data.access_token) {
      void completeOidc(data.access_token);
    } else if (data.type === "chorus-oidc-error") {
      showMessage("login-error", data.message || "No se pudo completar el acceso.", "error");
    } else if (data.type === "chorus:score" && currentDraft && data.draftId === currentDraft.id) {
      const blob = new Blob([data.data], {type: "application/vnd.recordare.musicxml"});
      const file = new File([blob], data.fileName || "partitura.mxl", {type: blob.type});
      void uploadMxl(file);
    }
  });
  async function login(email, password) {
    const data = await request("/api/v1/auth/login", {method:"POST",body:JSON.stringify({email,password})}, false);
    accessToken = data.access_token;
    if (data.onboarding && data.onboarding.required) {
      throw new Error("Tu cuenta necesita completar el alta de OSAP antes de utilizar Chorus.");
    }
    showWorkspace(email);
    try {
      const profile = await request("/api/v1/auth/me", {}, false);
      showWorkspace(profile.nickname || profile.email || email);
    } catch (_) {
      // La etiqueta inicial (email) sigue siendo válida si /auth/me no responde.
    }
  }
  function unwrap(doc) {
    return doc && doc.success === true && Object.prototype.hasOwnProperty.call(doc,"data") ? doc.data : doc;
  }
  function formatLabel(fmt) {
    const f = String(fmt || "").toLowerCase();
    if (/mxl|musicxml|xml/.test(f)) return "MusicXML";
    if (f === "pdf") return "PDF";
    if (/midi|mid/.test(f)) return "MIDI";
    if (/mscz|mscx/.test(f)) return "MuseScore";
    if (f === "sib") return "Sibelius";
    if (f === "mus") return "Finale";
    if (/mp3|wav|ogg|audio/.test(f)) return "Audio";
    return fmt || "Archivo";
  }
  function uniqueRepresentations(reps) {
    const seen = new Set();
    const out = [];
    for (const rep of reps) {
      const meta = rep.metadata || {};
      const key = rep.id || rep.url
        || [rep.provider, rep.format, meta.resource_id, meta.source_rep_id].join("|");
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(rep);
    }
    return out;
  }
  function representationTitle(rep, work) {
    const meta = rep.metadata || {};
    return meta.representation_title || rep.title || work.title || "Sin título";
  }
  function representationPeople(rep, work) {
    const meta = rep.metadata || {};
    return [...new Set(
      [work.composer, meta.composer, meta.editor, meta.arranger, meta.translator]
        .filter(Boolean)
    )];
  }
  function representationType(rep) {
    const meta = rep.metadata || {};
    return [formatLabel(rep.format), meta.instrumentation, meta.voicing]
      .filter(Boolean).join(" · ");
  }
  function renderResults(doc) {
    const data = unwrap(doc);
    const results = Array.isArray(data) ? data : (data && (data.results || data.items)) || [];
    lastResults = results;
    const list = $("results-list");
    list.replaceChildren();
    $("result-count").textContent = (data && data.total != null ? data.total : results.length) + " resultados";
    if (!results.length) {
      list.textContent = "No se han encontrado resultados para esta búsqueda.";
      return;
    }
    results.forEach((item) => {
      const work = item.work || item;
      const reps = item.representations && item.representations.length ? item.representations : (item.representation ? [item.representation] : []);
      const components = uniqueRepresentations(reps);
      const providers = [...new Set(components.map((rep) => String(rep.provider || "origen")))];
      const card = document.createElement("article");
      card.className = "result-card";

      const head = document.createElement("div");
      head.className = "result-head";
      const info = document.createElement("div");
      const title = document.createElement("h3");
      title.textContent = work.title || "Obra sin título";
      const meta = document.createElement("div");
      meta.className = "result-meta";
      meta.textContent = [work.composer, work.catalogue,
        components.length ? components.length + " componentes · " + providers.join(", ") : "sin componentes"]
        .filter(Boolean).join(" · ");
      info.append(title, meta);

      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "button button-outline result-toggle";
      toggle.disabled = !components.length;
      toggle.textContent = "Ver componentes (" + components.length + ")";

      const details = document.createElement("div");
      details.className = "result-details hidden";
      const componentList = document.createElement("div");
      componentList.className = "component-list";
      components.forEach((rep) => {
        const repMeta = rep.metadata || {};
        const row = document.createElement("div");
        row.className = "component-row";
        const main = document.createElement("div");
        main.className = "component-main";
        const name = document.createElement("strong");
        name.textContent = representationTitle(rep, work);
        const peopleValues = representationPeople(rep, work);
        const metaLine = document.createElement("span");
        metaLine.className = "component-meta component-line";
        const appendPart = (node) => {
          if (metaLine.childNodes.length) metaLine.append(" · ");
          metaLine.append(node);
        };
        if (peopleValues.length) appendPart(peopleValues.join(", "));
        const typeText = representationType(rep);
        if (typeText) appendPart(typeText);
        const license = document.createElement("span");
        const licenseLabel = repMeta.license || "Licencia no indicada";
        license.append("Licencia: ");
        if (repMeta.license_url) {
          const link = document.createElement("a");
          link.href = repMeta.license_url;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = licenseLabel;
          license.append(link);
        } else {
          license.append(licenseLabel);
        }
        if (repMeta.license_conflict) license.append(" ⚠");
        appendPart(license);
        appendPart(rep.provider || "origen");
        if (repMeta.source_url) {
          const pageLink = document.createElement("a");
          pageLink.href = repMeta.source_url;
          pageLink.target = "_blank";
          pageLink.rel = "noopener noreferrer";
          pageLink.textContent = "Página de la obra";
          appendPart(pageLink);
        }
        if (repMeta.resource_id) appendPart("rec " + repMeta.resource_id);
        if (repMeta.source_rep_id) appendPart("orig " + repMeta.source_rep_id);
        main.append(name, metaLine);

        const actions = document.createElement("div");
        actions.className = "component-actions";
        const supported = /mxl|musicxml|\.xml|midi|\.mid|mscz|mscx|capella|\.capx|\.gp|\.gpx/.test(
          String(rep.format || "").toLowerCase(),
        );
        const use = document.createElement("button");
        use.type = "button";
        use.className = "button button-outline";
        use.textContent = "Usar";
        use.disabled = rep.available === false || !supported;
        use.title = use.disabled
          ? "Formato no descargable o no compatible con el editor"
          : "Crear borrador desde este componente";
        use.addEventListener("click", () => startFromOsap(work, rep, use));
        const save = document.createElement("button");
        save.type = "button";
        save.className = "button button-quiet";
        save.textContent = "Guardar";
        save.title = "Guardar esta referencia en tu biblioteca";
        save.addEventListener("click", () => saveReference(work, rep, save, representationTitle(rep, work)));
        actions.append(use, save);

        row.append(main, actions);
        componentList.append(row);
      });
      if (!components.length) {
        const note = document.createElement("span");
        note.className = "result-meta";
        note.textContent = "No hay representaciones disponibles.";
        componentList.append(note);
      }
      details.append(componentList);

      toggle.addEventListener("click", () => {
        const open = details.classList.contains("hidden");
        details.classList.toggle("hidden", !open);
        card.classList.toggle("open", open);
        toggle.textContent = open
          ? "Ocultar componentes"
          : "Ver componentes (" + components.length + ")";
      });

      head.append(info, toggle);
      card.append(head, details);
      list.append(card);
    });
  }
  async function waitForCatalogSearch(initial) {
    let data = unwrap(initial);
    if (!data || typeof data !== "object" || !data.search_id) return initial;
    if (data.status === "done") return initial;
    if (data.status === "error") throw new Error(data.error || data.message || "OSAP no pudo completar la búsqueda.");
    if (data.status !== "running") return initial;

    const searchId = String(data.search_id);
    for (let attempt = 0; attempt < 120; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
      const response = await request("/api/v1/catalog/searches/" + encodeURIComponent(searchId));
      data = unwrap(response);
      if (data && data.status === "done") return response;
      if (data && data.status === "error") {
        throw new Error(data.error || data.message || "OSAP no pudo completar la búsqueda.");
      }
      if (!data || data.status !== "running") return response;
      const progress = Number.isFinite(Number(data.progress)) ? Math.max(0, Math.min(100, Number(data.progress))) : null;
      showMessage("search-message", progress === null
        ? "OSAP está realizando la búsqueda…"
        : "OSAP está realizando la búsqueda… " + progress + "%");
    }
    throw new Error("La búsqueda de OSAP sigue en curso. Vuelve a consultar en unos instantes.");
  }
  async function searchCatalog(query, button) {
    setBusy(button,true,"Buscando…");
    showMessage("search-message","Consultando el catálogo OSAP…");
    $("results-section").classList.remove("hidden");
    $("results-list").replaceChildren();
    try {
      const initial = await request("/api/v1/catalog/searches",{method:"POST",body:JSON.stringify({query,limit:20,page:1})});
      const data = await waitForCatalogSearch(initial);
      renderResults(data);
      showMessage("search-message","Búsqueda completada.","success");
    } catch (error) { showMessage("search-message",error.message,"error"); }
    finally { setBusy(button,false); }
  }
  async function createDraft(title) {
    return request("/api/v1/drafts",{method:"POST",body:JSON.stringify({title:title || null,resource_type:"score"})});
  }
  async function startFromOsap(work, rep, button) {
    setBusy(button,true,"Preparando…");
    try {
      const draft = await createDraft(work.title || null);
      currentDraft = await request("/api/v1/drafts/" + encodeURIComponent(draft.id) + "/source",{
        method:"POST",body:JSON.stringify({work_id:String(work.work_id),representation_id:String(rep.id)})
      });
      currentDraft.id = draft.id;
      showDraft(work.title || "Obra de OSAP","Original: " + (rep.provider || "OSAP") + " · " + (rep.format || "formato no indicado"));
      showMessage("draft-message","Original preparado. Ábrelo en MuseEncore; el original de OSAP no se modifica.");
      openDraftModal(work.title || "Obra de OSAP");
    } catch (error) { showMessage("search-message",error.message,"error"); }
    finally { setBusy(button,false); }
  }
  function showDraft(title, description) {
    $("draft-title").textContent = title;
    $("draft-description").textContent = description || "Partitura nueva";
    $("draft-state").textContent = "En edición";
    $("draft-section").classList.remove("hidden");
  }
  async function openEditor() {
    if (!currentDraft) return;
    try {
      const data = await request("/api/v1/drafts/" + encodeURIComponent(currentDraft.id) + "/editor");
      const title = $("draft-title").textContent || "";
      const wrapper = "/editor.html?v=0.8.0&src=" + encodeURIComponent(data.editor_url)
        + "&title=" + encodeURIComponent(title)
        + "&draft_id=" + encodeURIComponent(currentDraft.id);
      window.open(wrapper,"_blank");
    } catch (error) { showMessage("draft-message",error.message,"error"); }
  }
  async function uploadMxl(file) {
    if (!currentDraft || !file) return;
    showMessage("draft-message","Validando y guardando la partitura…");
    const form = new FormData(); form.append("file",file);
    try {
      const data = await request("/api/v1/drafts/" + encodeURIComponent(currentDraft.id) + "/files",{method:"POST",body:form});
      $("draft-state").textContent = "Guardado";
      showMessage("draft-message","Partitura guardada. Work: " + data.work_id + " · Resource: " + data.resource_id + " · File: " + data.file_id,"success");
      refreshLibrary().catch(()=>{});
    } catch (error) { showMessage("draft-message",error.message,"error"); }
    $("mxl-file").value = "";
  }

  $("oidc-login").addEventListener("click",()=>{void startOidc();});
  $("login-form").addEventListener("submit",async (event)=>{
    event.preventDefault(); const button=event.submitter; setBusy(button,true,"Entrando…"); showMessage("login-error","");
    try { await login($("email").value.trim(),$("password").value); }
    catch(error){accessToken=null;showMessage("login-error",error.message,"error");}
    finally{setBusy(button,false);}
  });
  $("search-form").addEventListener("submit",(event)=>{event.preventDefault();searchCatalog($("search-query").value.trim(),event.submitter);});
  $("dash-search-form").addEventListener("submit",(event)=>{
    event.preventDefault();
    const query=$("dash-query").value.trim();
    if(!query){$("dash-query").focus();return;}
    $("search-query").value=query;
    $("search-form").requestSubmit();
    $("results-section").scrollIntoView({behavior:"smooth",block:"start"});
  });
  $("dash-notify").addEventListener("click",()=>{
    const message=$("dash-message");
    message.textContent="Aviso registrado. Cuando el grupo esté activo, el responsable lo verá en Chorus.";
    message.className="message success";
  });
  $("dash-group-form").addEventListener("submit",async (event)=>{
    event.preventDefault();
    const button=event.submitter; setBusy(button,true,"Creando…");
    try {
      await request("/api/v1/groups",{method:"POST",body:JSON.stringify({
        entity_id:$("dash-group-entity").value,
        name:$("dash-group-name").value.trim(),
      })});
      $("dash-group-name").value="";
      showMessage("dash-group-message","Grupo creado.","success");
      await loadAgenda();
    } catch(error) { showMessage("dash-group-message",error.message,"error"); }
    finally { setBusy(button,false); }
  });
  $("dash-join-form").addEventListener("submit",async (event)=>{
    event.preventDefault();
    const button=event.submitter; setBusy(button,true,"Uniendo…");
    try {
      await request("/api/v1/groups/join",{method:"POST",body:JSON.stringify({
        code:$("dash-join-code").value.trim(),
      })});
      $("dash-join-code").value="";
      showMessage("dash-group-message","Ya formas parte del grupo.","success");
      await loadAgenda();
    } catch(error) { showMessage("dash-group-message",error.message,"error"); }
    finally { setBusy(button,false); }
  });
  $("dash-add-event").addEventListener("click",()=>{
    $("dash-event-form").classList.toggle("hidden");
  });
  async function loadEventTargets() {
    const groupId = $("dash-event-group").value;
    if (!groupId) return;
    try {
      const [catalog, members] = await Promise.all([
        request(`/api/v1/groups/${encodeURIComponent(groupId)}/catalog`).catch(() => ({ section: [] })),
        request(`/api/v1/groups/${encodeURIComponent(groupId)}/members`).catch(() => []),
      ]);
      const sections = $("dash-event-section");
      sections.replaceChildren(new Option("Toda la sección", ""));
      (catalog.section || []).forEach((item) => sections.append(new Option(item.name, item.id || "")));
      const users = $("dash-event-users");
      users.replaceChildren();
      (members || []).forEach((member) => users.append(new Option(member.name, member.user_sub)));
    } catch (_) {
      /* sin destinos */
    }
  }

  function syncEventScope() {
    const scope = $("dash-event-scope").value;
    $("dash-event-group-wrap").classList.toggle("hidden", scope === "personal");
    $("dash-event-section-wrap").classList.toggle("hidden", scope !== "section");
    $("dash-event-users-wrap").classList.toggle("hidden", scope !== "users");
    if (scope !== "personal") void loadEventTargets();
  }

  $("dash-event-scope").addEventListener("change", syncEventScope);
  $("dash-event-group").addEventListener("change", () => { void loadEventTargets(); });
  syncEventScope();

  $("dash-event-form").addEventListener("submit",async (event)=>{
    event.preventDefault();
    const button=event.submitter; setBusy(button,true,"Guardando…");
    try {
      const startsAt=new Date($("dash-event-start").value);
      if (Number.isNaN(startsAt.getTime())) throw new Error("Fecha inválida");
      await request("/api/v1/events",{method:"POST",body:JSON.stringify({
        group_id: $("dash-event-scope").value === "personal" ? null : $("dash-event-group").value,
        scope: $("dash-event-scope").value,
        section_id: $("dash-event-section").value || null,
        recipient_subs: Array.from($("dash-event-users").selectedOptions).map((option) => option.value),
        kind:$("dash-event-kind").value,
        title:$("dash-event-title").value.trim(),
        starts_at:startsAt.toISOString(),
        location:$("dash-event-location").value.trim() || null,
      })});
      $("dash-event-form").reset();
      $("dash-event-form").classList.add("hidden");
      showMessage("dash-event-message","Evento creado.","success");
      await loadAgenda();
    } catch(error) { showMessage("dash-event-message",error.message,"error"); }
    finally { setBusy(button,false); }
  });
  const _msgContent = $("msg-content");
  if (_msgContent) {
    $("inbox-compose").appendChild(_msgContent);
    _msgContent.classList.add("hidden");
  }

  $("inbox-button").addEventListener("click",()=>{void openInbox(false);});
  $("inbox-close").addEventListener("click",()=>{$("inbox-modal").classList.add("hidden");});
  $("inbox-expand").addEventListener("click",()=>{
    const panel = document.querySelector(".inbox-panel");
    panel.classList.toggle("expanded");
    $("inbox-expand").textContent = panel.classList.contains("expanded") ? "Reducir" : "Ampliar";
  });
  $("inbox-reply").addEventListener("submit",(event)=>{void sendInboxReply(event);});
  $("ga-close").addEventListener("click",()=>{$("group-admin-modal").classList.add("hidden");});
  $("ga-edit-form").addEventListener("submit",(event)=>{void saveGroupData(event);});

  $("msg-new").addEventListener("click",()=>{
    $("msg-form").classList.toggle("hidden");
    $("msg-scope").value="group";
    $("msg-people-wrap").classList.add("hidden");
    $("msg-subject").focus();
  });
  $("msg-group").addEventListener("change",()=>{
    messageState.groupId=$("msg-group").value;
    $("msg-form").classList.add("hidden");
    void loadMessages();
  });
  $("msg-scope").addEventListener("change",()=>{
    const people = $("msg-scope").value === "users";
    $("msg-people-wrap").classList.toggle("hidden", !people);
    $("msg-filters").classList.toggle("hidden", !people);
  });
  ["msg-people-search", "msg-filter-admin", "msg-filter-musical", "msg-filter-section"].forEach((id) => {
    $(id).addEventListener("input", renderRecipients);
    $(id).addEventListener("change", renderRecipients);
  });
  $("msg-form").addEventListener("submit",(event)=>{void sendMessage(event);});
  applyMessageI18n();

  $("new-draft-button").addEventListener("click",async()=>{
    const button=$("new-draft-button");setBusy(button,true,"Creando borrador…");
    try {currentDraft=await createDraft($("new-title").value.trim() || null);showDraft($("new-title").value.trim() || "Nueva partitura","Borrador privado · partitura creada desde cero");showMessage("draft-message","Borrador creado. Abre MuseEncore para escribir y exporta el resultado como .mxl.");$("draft-section").scrollIntoView({behavior:"smooth",block:"center"});}
    catch(error){showMessage("draft-message",error.message,"error");}
    finally{setBusy(button,false);}
  });
  $("open-editor-button").addEventListener("click",openEditor);
  $("download-draft-button").addEventListener("click",()=>{void downloadDraftSource();});
  $("modal-close").addEventListener("click",closeDraftModal);
  $("draft-modal").addEventListener("click",(event)=>{if(event.target===$("draft-modal"))closeDraftModal();});
  $("modal-open-editor").addEventListener("click",()=>{closeDraftModal();void openEditor();});
  $("modal-download").addEventListener("click",()=>{void downloadDraftSource();});
  $("modal-file").addEventListener("change",(event)=>{const file=event.target.files&&event.target.files[0];if(file){closeDraftModal();void uploadMxl(file);}});
  $("library-refresh").addEventListener("click",()=>{refreshLibrary($("library-query").value.trim()).catch((error)=>showMessage("library-message",error.message,"error"));});
  let libraryTimer = null;
  $("library-query").addEventListener("input",()=>{
    clearTimeout(libraryTimer);
    libraryTimer = setTimeout(()=>{refreshLibrary($("library-query").value.trim()).catch(()=>{});},300);
  });
  $("library-search-osap").addEventListener("click",()=>{
    const query=$("search-query");
    query.focus();
    query.scrollIntoView({behavior:"smooth",block:"center"});
  });
  $("mxl-file").addEventListener("change",(event)=>uploadMxl(event.target.files[0]));
  $("logout-button").addEventListener("click",async()=>{
    try{if(accessToken)await request("/api/v1/auth/logout",{method:"POST"},false);}catch(_){}
    accessToken=null;currentDraft=null;showLogin();
  });
  const query = new URLSearchParams(location.search);
  const handoffToken = query.get("token");
  const handoffRefresh = query.get("refresh_token") || "";
  const hashToken = new URLSearchParams(location.hash.replace(/^#/, "")).get("access_token");
  if (handoffToken) {
    history.replaceState(null, "", location.pathname + location.hash);
    void completeHandoff(handoffToken, handoffRefresh);
  } else if (hashToken) {
    history.replaceState(null, "", location.pathname + location.search);
    void completeOidc(hashToken);
  } else {
    refreshSession().then(async(ok)=>{
      if(!ok)return;
      try{const profile=await request("/api/v1/auth/me",{},false);if(profile.onboarding && profile.onboarding.required){showMessage("login-error","Completa primero el alta de tu cuenta OSAP.","error");return;}showWorkspace(profile.nickname || profile.email || profile.user_id);}
      catch(_){accessToken=null;}
    });
  }
})();


















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
  let profileAvatarUrl = null;
  let profileAvatarInitials = "M";

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
  function paintAvatar(el, initials, url) {
    if (!el) return;
    el.classList.toggle("has-image", Boolean(url));
    el.textContent = url ? "" : initials;
    el.style.backgroundImage = url ? `url("${url}")` : "";
  }
  function showWorkspace(profileLabel, profile) {
    $("login-view").classList.add("hidden");
    $("workspace-view").classList.remove("hidden");
    $("logout-button").classList.remove("hidden");
    $("app-nav").classList.remove("hidden");
    $("inbox-button").classList.remove("hidden");
    void refreshUnread();
    void loadMaterialTree();
    void loadMaterialGroups();
    const rawName = String(profileLabel || "").split("@")[0].replace(/[._-]+/g, " ").trim();
    const displayName = rawName ? rawName.charAt(0).toUpperCase() + rawName.slice(1) : "músico";
    const parts = rawName.split(/\s+/).filter(Boolean);
    const initials = parts.length > 1
      ? `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
      : (parts[0] || "M").slice(0, 2).toUpperCase();
    profileAvatarUrl = profile && profile.avatar_url ? profile.avatar_url : null;
    profileAvatarInitials = initials;
    const avatar = document.createElement("span");
    avatar.className = "account-avatar";
    paintAvatar(avatar, initials, profileAvatarUrl);
    $("account-label").replaceChildren(avatar, document.createTextNode(displayName));
    if ($("dash-name")) $("dash-name").textContent = displayName;
    if ($("dash-avatar")) paintAvatar($("dash-avatar"), initials, profileAvatarUrl);
    if ($("profile-avatar-preview")) paintAvatar($("profile-avatar-preview"), initials, profileAvatarUrl);
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
  let activeGroupId = "";
  let groupPickerOpen = false;

  function activeGroup() {
    return (agendaState.groups || []).find((group) => group.id === activeGroupId) || null;
  }

  function updateActiveGroupUi() {
    const button = $("active-group-button");
    if (!button) return;
    const group = activeGroup();
    button.classList.toggle("hidden", !group);
    $("articles-button")?.classList.toggle("hidden", !group);
    if (group) button.textContent = group.name;
  }

  function openGroupPicker() {
    const list = $("group-picker-list");
    if (!list) return;
    groupPickerOpen = true;
    list.replaceChildren();
    (agendaState.groups || []).forEach((group) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "group-picker-card" + (group.id === activeGroupId ? " active" : "");
      const mark = document.createElement("span");
      mark.className = "group-mark";
      mark.textContent = (group.name || "G").slice(0, 2).toUpperCase();
      const copy = document.createElement("span");
      const name = document.createElement("strong");
      name.textContent = group.name;
      const role = document.createElement("small");
      role.textContent = group.role === "manager" ? "Responsable" : "Miembro";
      copy.append(name, role);
      button.append(mark, copy);
      button.addEventListener("click", () => {
        setActiveGroup(group.id);
        $("group-picker-modal").classList.add("hidden");
        groupPickerOpen = false;
      });
      list.append(button);
    });
    $("group-picker-modal").classList.remove("hidden");
  }

  function setActiveGroup(groupId, reloadMessages = true) {
    activeGroupId = groupId;
    if (!agendaFilter || !["all", "personal"].includes(agendaFilter)) {
      if (!(agendaState.groups || []).some((group) => group.id === agendaFilter)) {
        agendaFilter = groupId;
      }
    }
    updateActiveGroupUi();
    renderAgenda();
    renderGroupCard();
    if (messageState.groupId !== groupId) {
      messageState.groupId = groupId;
      if (reloadMessages) void loadMessages();
    }
    const agendaModal = $("agenda-modal");
    if (agendaModal && !agendaModal.classList.contains("hidden")) {
      renderAgendaFilters();
      renderAgendaCalendar();
    }
  }

  function ensureActiveGroup() {
    const groups = agendaState.groups || [];
    if (!groups.length) {
      activeGroupId = "";
      updateActiveGroupUi();
      $("group-picker-modal")?.classList.add("hidden");
      return;
    }
    const stored = groups.find((group) => group.id === activeGroupId);
    if (stored) {
      updateActiveGroupUi();
      if (!agendaFilter) agendaFilter = stored.id;
      return;
    }
    if (groups.length === 1) {
      setActiveGroup(groups[0].id, false);
      return;
    }
    if (!groupPickerOpen) openGroupPicker();
  }

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
    ensureActiveGroup();
    renderAgenda();
    const agendaModal = $("agenda-modal");
    if (agendaModal && !agendaModal.classList.contains("hidden")) {
      renderAgendaFilters();
      renderAgendaCalendar();
    }
    void loadMaterialGroups();
    await loadMessages();
  }

  function renderGroupCard() {
    const groups = agendaState.groups || [];
    const content = $("dash-group-content");
    const empty = $("dash-group-empty");
    if (groups.length) {
      const group = groups.find((item) => item.id === activeGroupId) || groups[0];
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

  let articlesState = {items: [], current: null};

  function articleStatusLabel(status) {
    return {draft: "Borrador", pending: "Pendiente", published: "Publicado", withdrawn: "Retirado"}[status] || status;
  }

  function renderArticlesList() {
    const list = $("articles-list");
    if (!list) return;
    list.replaceChildren();
    if (!articlesState.items.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "Todavía no hay artículos en este grupo.";
      list.append(empty);
      return;
    }
    articlesState.items.forEach((article) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "article-row" + (articlesState.current?.id === article.id ? " active" : "");
      const title = document.createElement("strong");
      title.textContent = article.title;
      const meta = document.createElement("small");
      meta.textContent = [articleStatusLabel(article.status), article.event_date].filter(Boolean).join(" · ");
      button.append(title, meta);
      button.addEventListener("click", () => selectArticle(article));
      list.append(button);
    });
  }

  function selectArticle(article = null) {
    articlesState.current = article;
    $("article-title").value = article ? article.title : "";
    $("article-summary").value = article ? article.summary || "" : "";
    $("article-body").value = article ? article.body || "" : "";
    $("article-cover").value = article ? article.cover_url || "" : "";
    $("article-date").value = article ? article.event_date || "" : "";
    $("article-media-list").replaceChildren();
    (article?.media || []).forEach((media) => {
      const link = document.createElement("a");
      link.href = media.url;
      link.target = "_blank";
      link.rel = "noreferrer";
      link.textContent = [media.kind, media.caption || media.url].filter(Boolean).join(" · ");
      $("article-media-list").append(link);
    });
    const editing = Boolean(article);
    $("article-delete").classList.toggle("hidden", !(editing && article.can_edit && article.status !== "published"));
    $("article-withdraw").classList.toggle("hidden", !(editing && article.can_edit && article.status === "published"));
    $("article-publish").classList.toggle("hidden", !(editing && article.can_publish && article.status !== "published"));
    $("article-message").textContent = "";
    renderArticlesList();
  }

  async function loadArticles() {
    const group = activeGroup();
    if (!group) return;
    $("articles-group-name").textContent = group.name;
    const items = await request(`/api/v1/groups/${encodeURIComponent(group.id)}/articles`);
    articlesState.items = Array.isArray(items) ? items : [];
    if (articlesState.current) {
      const current = articlesState.items.find((item) => item.id === articlesState.current.id);
      selectArticle(current || null);
    } else {
      renderArticlesList();
    }
  }

  async function openArticles() {
    if (!activeGroup()) {
      openGroupPicker();
      return;
    }
    articlesState.current = null;
    $("articles-modal").classList.remove("hidden");
    selectArticle(null);
    try { await loadArticles(); } catch (error) {
      showMessage("article-message", error.message, "error");
    }
  }

  function articlePayload() {
    return {
      title: $("article-title").value.trim(),
      summary: $("article-summary").value.trim() || null,
      body: $("article-body").value || null,
      cover_url: $("article-cover").value.trim() || null,
      event_date: $("article-date").value || null,
    };
  }

  async function saveArticle() {
    const group = activeGroup();
    if (!group) return;
    const payload = articlePayload();
    if (!payload.title) {
      showMessage("article-message", "El título es obligatorio.", "error");
      return;
    }
    const button = $("article-save");
    setBusy(button, true, "Guardando…");
    try {
      const current = articlesState.current;
      const article = current
        ? await request(`/api/v1/articles/${encodeURIComponent(current.id)}`, {
          method: "PATCH", body: JSON.stringify(payload),
        })
        : await request(`/api/v1/groups/${encodeURIComponent(group.id)}/articles`, {
          method: "POST", body: JSON.stringify(payload),
        });
      articlesState.current = article;
      await loadArticles();
      selectArticle(articlesState.items.find((item) => item.id === article.id) || article);
      showMessage("article-message", "Artículo guardado.", "success");
    } catch (error) {
      showMessage("article-message", error.message, "error");
    } finally {
      setBusy(button, false);
    }
  }

  async function articleAction(action) {
    const current = articlesState.current;
    if (!current) return;
    try {
      if (action === "delete") {
        await request(`/api/v1/articles/${encodeURIComponent(current.id)}`, {method: "DELETE"});
      } else {
        await request(`/api/v1/articles/${encodeURIComponent(current.id)}/${action}`, {
          method: "POST", body: JSON.stringify({}),
        });
      }
      articlesState.current = null;
      await loadArticles();
      selectArticle(null);
      showMessage("article-message", action === "delete" ? "Artículo eliminado." : "Estado actualizado.", "success");
    } catch (error) {
      showMessage("article-message", error.message, "error");
    }
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
    const creator = document.createElement("span");
    creator.className = "agenda-creator-badge";
    creator.textContent = event.creator_badge || "D";
    const kind = document.createElement("span");
    kind.className = "dash-event-kind " + event.kind;
    kind.textContent = kindLabel(event.kind);
    head.append(left, creator, kind);
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
    const now = Date.now();
    const events = (agendaState.events || []).filter(
      (event) => new Date(event.starts_at).getTime() >= now
        && (!activeGroupId || !event.group_id || event.group_id === activeGroupId),
    );
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
    const previous = messageState.groupId || activeGroupId || select.value;
    select.replaceChildren();
    groups.forEach((group) => select.append(new Option(group.name, group.id)));
    if (!groups.length) {
      messageState = { groupId: "", messages: [] };
      return;
    }
    const exists = groups.some((group) => group.id === previous);
    select.value = exists
      ? previous
      : (groups.find((group) => group.id === activeGroupId) || groups[0]).id;
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
  let mailboxMode = "inbox";
  let mailboxGroupId = "";
  let inboxRows = [];
  const inboxMemberNames = new Map();

  async function refreshUnread() {
    try {
      const data = await request("/api/v1/messages/unread-count");
      const count = Number(data.count || 0);
      $("inbox-count").textContent = String(count);
      $("inbox-button").classList.toggle("badge-gold", count > 0);
      const headerBadge = $("inbox-unread");
      if (headerBadge) {
        headerBadge.textContent = count ? `${count} sin leer` : "Al día";
        headerBadge.className = "badge " + (count ? "badge-gold" : "badge-muted");
      }
    } catch (_) {
      /* silencioso */
    }
  }

  function inboxInitials(name) {
    const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return "A";
    if (parts.length === 1) return parts[0].slice(0, 2);
    return `${parts[0][0]}${parts[parts.length - 1][0]}`;
  }

  function memberName(groupId, sub) {
    const map = inboxMemberNames.get(String(groupId || ""));
    return (map && map.get(String(sub || ""))) || "";
  }

  function senderLabel(row) {
    if (row.is_sender) return "Tú";
    return memberName(row.group_id, row.sender_sub) || "Administración del grupo";
  }

  function formatMessageTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const now = new Date();
    if (date.toDateString() === now.toDateString()) {
      return date.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
    }
    return new Intl.DateTimeFormat("es-ES", { day: "2-digit", month: "short" }).format(date);
  }

  async function loadInboxMemberNames(rows) {
    const groupIds = [...new Set(rows.map((row) => String(row.group_id || "")).filter(Boolean))];
    await Promise.all(groupIds.map(async (groupId) => {
      if (inboxMemberNames.has(groupId)) return;
      try {
        const members = await request(`/api/v1/groups/${encodeURIComponent(groupId)}/members`);
        const map = new Map();
        (Array.isArray(members) ? members : []).forEach((member) => {
          map.set(String(member.user_sub), member.name || String(member.user_sub).slice(0, 8));
        });
        inboxMemberNames.set(groupId, map);
      } catch (_) {
        inboxMemberNames.set(groupId, new Map());
      }
    }));
  }

  async function loadInboxRows() {
    const rows = await request("/api/v1/messages/inbox");
    const seen = new Set();
    inboxRows = (Array.isArray(rows) ? rows : []).filter((row) => {
      if (!row || seen.has(row.id)) return false;
      seen.add(row.id);
      return true;
    });
    await loadInboxMemberNames(inboxRows);
  }

  function setMailboxTab(mode) {
    document.querySelectorAll(".mailbox-tab").forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.mailbox === mode);
    });
  }

  function renderMailboxGroups() {
    const container = $("messages-groups");
    container.replaceChildren();
    (agendaState.groups || []).forEach((group) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "messages-group-card" + (
        mailboxMode === "group" && String(mailboxGroupId) === String(group.id) ? " active" : ""
      );
      const avatar = document.createElement("span");
      avatar.className = "messages-group-avatar";
      avatar.setAttribute("aria-hidden", "true");
      avatar.textContent = inboxInitials(group.name);
      const copy = document.createElement("span");
      copy.className = "messages-group-copy";
      const name = document.createElement("strong");
      name.textContent = group.name;
      const subtitle = document.createElement("small");
      subtitle.textContent = group.role === "manager" ? "Gestión del grupo" : "Mensajes del grupo";
      copy.append(name, subtitle);
      const badge = document.createElement("span");
      badge.className = "messages-group-active";
      badge.textContent = "Activo";
      button.append(avatar, copy, badge);
      button.addEventListener("click", () => {
        mailboxMode = "group";
        mailboxGroupId = group.id;
        messageState.groupId = group.id;
        setMailboxTab("");
        void openInbox(false);
      });
      container.append(button);
    });
  }

  function renderSupportPanel(list) {
    const panel = document.createElement("div");
    panel.className = "support-panel";
    const title = document.createElement("h3");
    title.textContent = "Ayuda y administración";
    const text = document.createElement("p");
    text.textContent = "Escribe directamente a la administración de tus grupos. Te responderán en la bandeja de entrada.";
    panel.append(title, text);
    const groups = agendaState.groups || [];
    if (!groups.length) {
      const empty = document.createElement("p");
      empty.textContent = "Todavía no perteneces a ningún grupo.";
      panel.append(empty);
    }
    groups.forEach((group) => {
      const card = document.createElement("div");
      card.className = "support-group";
      const copy = document.createElement("div");
      const name = document.createElement("strong");
      name.textContent = group.name;
      const subtitle = document.createElement("small");
      subtitle.textContent = "Administración y gestores del grupo";
      copy.append(name, subtitle);
      const button = document.createElement("button");
      button.type = "button";
      button.className = "button button-outline button-small";
      button.textContent = "Escribir a los gestores";
      button.addEventListener("click", () => {
        messageState.groupId = group.id;
        mailboxMode = "inbox";
        setMailboxTab("inbox");
        void openInbox(true);
        $("msg-scope").value = "managers";
        $("msg-people-wrap").classList.add("hidden");
        $("msg-filters").classList.add("hidden");
      });
      card.append(copy, button);
      panel.append(card);
    });
    list.append(panel);
  }

  function renderInboxRows() {
    const list = $("inbox-list");
    list.replaceChildren();
    const unread = inboxRows.filter((row) => !row.is_sender && !row.my_read_at).length;
    const count = $("mailbox-unread");
    if (count) {
      count.textContent = unread ? `(${unread} no ${unread === 1 ? "leído" : "leídos"})` : "";
    }
    const headerBadge = $("inbox-unread");
    if (headerBadge) {
      headerBadge.textContent = unread ? `${unread} sin leer` : "Al día";
      headerBadge.className = "badge " + (unread ? "badge-gold" : "badge-muted");
    }
    if (mailboxMode === "support") {
      renderSupportPanel(list);
      return;
    }
    let rows = inboxRows.slice();
    if (mailboxMode === "sent") rows = rows.filter((row) => row.is_sender);
    else if (mailboxMode === "group") rows = rows.filter((row) => String(row.group_id) === String(mailboxGroupId));
    else rows = rows.filter((row) => !row.is_sender);
    if (!rows.length) {
      const empty = document.createElement("div");
      empty.className = "inbox-empty-state";
      const icon = document.createElement("span");
      icon.className = "inbox-empty-icon";
      icon.setAttribute("aria-hidden", "true");
      icon.textContent = mailboxMode === "sent" ? "➤" : "✉";
      const title = document.createElement("h3");
      title.textContent = mailboxMode === "sent"
        ? "Todavía no has enviado mensajes"
        : mailboxMode === "group"
          ? "Este grupo no tiene mensajes"
          : "Tu bandeja está vacía";
      const text = document.createElement("p");
      text.textContent = mailboxMode === "sent"
        ? "Cuando escribas al grupo o a sus gestores, verás aquí lo enviado."
        : mailboxMode === "group"
          ? "Los avisos y conversaciones del grupo aparecerán en este espacio."
          : "Los avisos de tus grupos y las conversaciones con sus gestores aparecerán aquí.";
      const action = document.createElement("button");
      action.type = "button";
      action.className = "button button-primary";
      action.textContent = "Escribir mensaje";
      action.addEventListener("click", () => void openInbox(true));
      empty.append(icon, title, text, action);
      list.append(empty);
      return;
    }
    rows.forEach((row) => {
      const unreadRow = !row.my_read_at && !row.is_sender;
      const item = document.createElement("button");
      item.type = "button";
      item.className = "inbox-item" + (unreadRow ? " unread" : "");
      const avatar = document.createElement("span");
      avatar.className = "inbox-avatar";
      avatar.setAttribute("aria-hidden", "true");
      avatar.textContent = inboxInitials(senderLabel(row));
      const main = document.createElement("span");
      main.className = "inbox-item-main";
      const top = document.createElement("span");
      top.className = "inbox-item-top";
      const from = document.createElement("strong");
      from.textContent = senderLabel(row);
      const time = document.createElement("span");
      time.className = "inbox-time";
      time.textContent = formatMessageTime(row.created_at);
      top.append(from, time);
      const subject = document.createElement("span");
      subject.className = "inbox-subject";
      subject.textContent = row.subject;
      const snippet = document.createElement("span");
      snippet.className = "inbox-snippet";
      snippet.textContent = `${row.group_name ? row.group_name + " · " : ""}${row.body || ""}`;
      main.append(top, subject, snippet);
      item.append(avatar, main);
      if (unreadRow) {
        const dot = document.createElement("span");
        dot.className = "inbox-unread-dot";
        dot.setAttribute("aria-hidden", "true");
        item.append(dot);
      }
      item.addEventListener("click", () => void openInboxMessage(row.id));
      list.append(item);
    });
  }

  async function openInbox(showCompose = false) {
    $("inbox-modal").classList.remove("hidden");
    $("inbox-detail").classList.add("hidden");
    $("inbox-compose").classList.add("hidden");
    if (showCompose) {
      if (!messageState.groupId) {
        const first = (agendaState.groups || [])[0];
        if (first) messageState.groupId = first.id;
      }
      $("inbox-list").classList.add("hidden");
      $("inbox-compose").classList.remove("hidden");
      $("msg-content").classList.remove("hidden");
      $("msg-form").classList.remove("hidden");
      renderMailboxGroups();
      void loadMessages();
      $("msg-subject").focus();
      return;
    }
    $("inbox-list").classList.remove("hidden");
    renderMailboxGroups();
    const loading = document.createElement("div");
    loading.className = "inbox-loading";
    loading.textContent = "Cargando mensajes…";
    $("inbox-list").replaceChildren(loading);
    try {
      await loadInboxRows();
      renderInboxRows();
      renderMailboxGroups();
    } catch (error) {
      const list = $("inbox-list");
      list.replaceChildren();
      const empty = document.createElement("p");
      empty.className = "inbox-empty";
      empty.textContent = error.message;
      list.append(empty);
    }
  }

  function normalizeMessageSubject(value) {
    return String(value || "").replace(/^(re|fw|fwd)\s*:\s*/gi, "").trim().toLowerCase();
  }

  function threadRowsFor(row) {
    const base = normalizeMessageSubject(row.subject);
    const rows = inboxRows.filter(
      (item) => String(item.group_id) === String(row.group_id)
        && normalizeMessageSubject(item.subject) === base,
    );
    if (!rows.some((item) => item.id === row.id)) rows.push(row);
    return rows.sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)));
  }

  function renderReplyTargets(row) {
    const chips = $("inbox-recipients");
    chips.replaceChildren();
    const add = (text) => {
      const chip = document.createElement("span");
      chip.className = "composer-chip";
      chip.textContent = text;
      chips.append(chip);
    };
    if (!row.is_sender) add(senderLabel(row));
    if (row.scope === "group") add(`Grupo: ${row.group_name} (Todos)`);
    else if (row.scope === "managers") add(`Gestores: ${row.group_name}`);
    else {
      const subs = Array.isArray(row.recipient_subs) ? row.recipient_subs : [];
      const names = subs
        .filter((sub) => sub !== row.sender_sub)
        .map((sub) => memberName(row.group_id, sub) || String(sub).slice(0, 8));
      if (names.length) names.forEach(add);
      else add("Personas concretas");
    }
  }

  function renderInboxThread(row) {
    const container = $("inbox-thread");
    container.replaceChildren();
    threadRowsFor(row).forEach((item) => {
      const article = document.createElement("article");
      article.className = "inbox-thread-item";
      const avatar = document.createElement("span");
      avatar.className = "inbox-thread-avatar";
      avatar.setAttribute("aria-hidden", "true");
      avatar.textContent = inboxInitials(senderLabel(item));
      const main = document.createElement("div");
      main.className = "inbox-thread-main";
      const head = document.createElement("div");
      head.className = "inbox-thread-head";
      const from = document.createElement("strong");
      from.textContent = senderLabel(item);
      const time = document.createElement("time");
      time.textContent = formatMessageTime(item.created_at);
      head.append(from, time);
      const body = document.createElement("p");
      body.className = "inbox-thread-body";
      body.textContent = item.body || "";
      main.append(head, body);
      article.append(avatar, main);
      container.append(article);
    });
  }

  function participantsLabel(row) {
    const group = row.group_name || "tu grupo";
    if (row.scope === "group") return `Todo el grupo «${group}»`;
    if (row.scope === "managers") return `Gestores de «${group}»`;
    return "Personas concretas del grupo";
  }

  async function openInboxMessage(messageId) {
    try {
      const row = await request(`/api/v1/messages/${encodeURIComponent(messageId)}`);
      inboxCurrent = row;
      await loadInboxMemberNames([...(inboxRows || []), row]);
      $("inbox-list").classList.add("hidden");
      $("inbox-compose").classList.add("hidden");
      $("inbox-detail").classList.remove("hidden");
      $("inbox-subject").textContent = row.subject;
      $("inbox-participants").textContent = participantsLabel(row);
      renderInboxThread(row);
      renderReplyTargets(row);
      $("inbox-reply").classList.toggle("hidden", Boolean(row.is_sender));
      $("inbox-reply-body").value = "";
      if (!row.is_sender) {
        await request(`/api/v1/messages/${encodeURIComponent(messageId)}/read`, { method: "POST" });
        await refreshUnread();
      }
    } catch (error) {
      showMessage("inbox-message", error.message, "error");
    }
  }

  async function sendInboxReply(event, all = false) {
    event.preventDefault();
    if (!inboxCurrent) return;
    const text = $("inbox-reply-body").value.trim();
    if (!text) return;
    const button = all
      ? $("inbox-reply").querySelector("button[type=submit]")
      : $("inbox-reply-sender");
    setBusy(button, true, "Enviando…");
    try {
      await request(`/api/v1/messages/${encodeURIComponent(inboxCurrent.id)}/reply`, {
        method: "POST",
        body: JSON.stringify({ body: text, all }),
      });
      $("inbox-reply-body").value = "";
      await loadInboxRows();
      await openInboxMessage(inboxCurrent.id);
      showMessage("inbox-message", "Respuesta enviada.", "success");
    } catch (error) {
      showMessage("inbox-message", error.message, "error");
    } finally {
      setBusy(button, false);
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
    // Campos corales
    $("ga-foundation-date").value = item.foundation_date || "";
    $("ga-dissolution-date").value = item.dissolution_date || "";
    $("ga-locality").value = item.locality || "";
    $("ga-region").value = item.region || "";
    $("ga-country-code").value = item.country_code || "";
    $("ga-venue").value = item.venue || "";
    $("ga-formation-type").value = item.formation_type || "";
    $("ga-member-count").value = item.member_count !== null && item.member_count !== undefined ? item.member_count : "";
    $("ga-public-email").value = item.public_email || "";
    $("ga-language").value = Array.isArray(item.language) ? item.language.join(", ") : (item.language || "");
    $("ga-repertoire").value = Array.isArray(item.repertoire) ? item.repertoire.map(r => `${r.value || ""}|${r.position || ""}`).join("\n") : "";
    $("ga-venues").value = Array.isArray(item.venues) ? item.venues.map(v => `${v.value || ""}|${v.position || ""}`).join("\n") : "";
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
      // Serializar JSON
      const language = $("ga-language").value.trim();
      const languageArray = language ? language.split(",").map(s => s.trim()).filter(Boolean) : null;
      
      const repertoireText = $("ga-repertoire").value.trim();
      const repertoire = repertoireText ? repertoireText.split("\n").map(line => {
        const [value, position] = line.split("|").map(s => s.trim());
        return { value, position: parseInt(position, 10) || 0 };
      }).filter(r => r.value) : null;
      
      const venuesText = $("ga-venues").value.trim();
      const venues = venuesText ? venuesText.split("\n").map(line => {
        const [value, position] = line.split("|").map(s => s.trim());
        return { value, position: parseInt(position, 10) || 0 };
      }).filter(r => r.value) : null;

      await request(`/api/v1/groups/${encodeURIComponent(groupAdminState.group.id)}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: $("ga-name").value.trim(),
          timezone: $("ga-timezone").value.trim(),
          foundation_date: $("ga-foundation-date").value || null,
          dissolution_date: $("ga-dissolution-date").value || null,
          locality: $("ga-locality").value.trim() || null,
          region: $("ga-region").value.trim() || null,
          country_code: $("ga-country-code").value.trim().toUpperCase() || null,
          venue: $("ga-venue").value.trim() || null,
          formation_type: $("ga-formation-type").value.trim() || null,
          member_count: $("ga-member-count").value ? parseInt($("ga-member-count").value, 10) : null,
          public_email: $("ga-public-email").value.trim() || null,
          language: languageArray,
          repertoire: repertoire,
          venues: venues,
        }),
      });
      showMessage("ga-message", "Datos del grupo guardados.", "success");
      await loadAgenda();
    } catch (error) {
      showMessage("ga-message", error.message, "error");
    }
  }
  async function loadMaterialGroups() {
    const select = $("material-group");
    const view = $("material-view-group");
    if (select) select.replaceChildren(new Option("Biblioteca personal", ""));
    if (view) view.replaceChildren(new Option("Mi biblioteca", ""));
    (agendaState.groups || []).forEach((group) => {
      if (select && group.can_manage) select.append(new Option(group.name, group.id));
      if (view) view.append(new Option(group.name, group.id));
    });
    if (select) {
      select.closest("label")?.classList.add("hidden");
      if (select.options.length > 1 && !select.value) select.value = select.options[1].value;
      void loadMaterialSections();
    }
  }

  async function loadMaterialSections() {
    const groupId = $("material-group").value;
    const select = $("material-section");
    select.replaceChildren(new Option("Todas", ""));
    if (!groupId) return;
    try {
      const catalog = await request(`/api/v1/groups/${encodeURIComponent(groupId)}/catalog`);
      (catalog.section || []).forEach((item) => select.append(new Option(item.name, item.id || "")));
    } catch (_) {
      /* sin secciones */
    }
  }

  async function loadMaterialTree() {
    const container = $("material-tree");
    if (!container) return;
    try {
      const works = await request("/api/v1/material/tree");
      container.replaceChildren();
      if (!works.length) {
        const p = document.createElement("p");
        p.className = "muted";
        p.textContent = "Aún no hay material propio importado.";
        container.append(p);
        return;
      }
      works.forEach((work) => {
        const workBox = document.createElement("section");
        workBox.className = "material-work";
        const heading = document.createElement("h4");
        heading.textContent = work.title;
        workBox.append(heading);
        (work.resources || []).forEach((resource) => {
          const version = document.createElement("p");
          version.className = "material-version";
          version.textContent = `${resource.version_label || "Original"} · ${resource.material_status}`;
          workBox.append(version);
          (resource.files || []).forEach((file) => {
            const row = document.createElement("div");
            row.className = "material-file";
            const label = document.createElement("span");
            label.textContent = `${file.folder_path ? file.folder_path + "/" : ""}${file.display_name || file.name}`;
            const status = document.createElement("span");
            status.className = "badge badge-muted";
            status.textContent = file.status;
            row.append(label, status);
            workBox.append(row);
          });
          const review = document.createElement("button");
          review.type = "button";
          review.className = "button button-outline button-small";
          review.textContent = resource.material_status === "draft" ? "Marcar revisado" : "Revisado";
          review.disabled = resource.material_status !== "draft";
          review.addEventListener("click", async () => {
            try {
              await request(`/api/v1/material/resources/${encodeURIComponent(resource.id)}`, {
                method: "PATCH",
                body: JSON.stringify({ material_status: "reviewed" }),
              });
              await loadMaterialTree();
            } catch (error) {
              showMessage("material-message", error.message, "error");
            }
          });
          workBox.append(review);
          const publish = document.createElement("button");
          publish.type = "button";
          publish.className = "button button-quiet button-small";
          publish.textContent = resource.material_status === "published" ? "Publicado" : "Publicar";
          publish.disabled = resource.material_status === "published";
          publish.addEventListener("click", async () => {
            try {
              await request(`/api/v1/material/resources/${encodeURIComponent(resource.id)}/publish`, { method: "POST" });
              await loadMaterialTree();
            } catch (error) {
              showMessage("material-message", error.message, "error");
            }
          });
          workBox.append(publish);
        });
        container.append(workBox);
      });
    } catch (error) {
      showMessage("material-message", error.message, "error");
    }
  }

  let pendingMaterial = null;

  function renderMaterialPreview(data) {
    const container = $("material-preview");
    container.replaceChildren();
    const table = document.createElement("table");
    table.className = "material-preview-table";
    const head = document.createElement("tr");
    ["Original", "Nombre propuesto", "Carpeta", "SHA-256"].forEach((text) => {
      const th = document.createElement("th");
      th.textContent = text;
      head.append(th);
    });
    table.append(head);
    (data.files || []).forEach((file) => {
      const row = document.createElement("tr");
      [file.original, file.display_name, file.folder || "—", String(file.sha).slice(0, 12)]
        .forEach((value) => {
          const cell = document.createElement("td");
          cell.textContent = value;
          row.append(cell);
        });
      table.append(row);
    });
    container.append(table);
    if (data.duplicates?.length) {
      const duplicate = document.createElement("p");
      duplicate.className = "muted";
      duplicate.textContent = `Duplicados omitidos: ${data.duplicates.join(", ")}`;
      container.append(duplicate);
    }
    const confirm = document.createElement("button");
    confirm.type = "button";
    confirm.className = "button button-primary button-small";
    confirm.textContent = "Confirmar importación";
    confirm.addEventListener("click", () => void confirmMaterial());
    container.append(confirm);
  }

  async function importMaterial(event) {
    event.preventDefault();
    const files = [
      ...Array.from($("material-files").files || []),
      ...Array.from($("material-folder").files || []),
    ];
    if (!files.length) return;
    const metadata = {
      work_title: $("material-work").value.trim(),
      group_id: $("material-group").value || null,
      group_section_id: $("material-section").value || null,
      version_label: $("material-version").value.trim() || "Original",
      part_label: $("material-part").value.trim() || null,
      preview: true,
    };
    const form = new FormData();
    form.append("metadata", JSON.stringify(metadata));
    files.forEach((file) => form.append("files", file, file.webkitRelativePath || file.name));
    try {
      const data = await request("/api/v1/material/import", { method: "POST", body: form });
      pendingMaterial = { files, metadata };
      renderMaterialPreview(data);
      showMessage("material-message", "Revisa la propuesta y confirma.", "success");
    } catch (error) {
      showMessage("material-message", error.message, "error");
    }
  }

  async function confirmMaterial() {
    if (!pendingMaterial) return;
    const { files, metadata } = pendingMaterial;
    const form = new FormData();
    form.append("metadata", JSON.stringify({ ...metadata, preview: false }));
    files.forEach((file) => form.append("files", file, file.webkitRelativePath || file.name));
    try {
      const data = await request("/api/v1/material/import", { method: "POST", body: form });
      showMessage("material-message", data.duplicates?.length ? "Importado; algunos duplicados se omitieron." : "Material importado.", "success");
      pendingMaterial = null;
      $("material-preview").replaceChildren();
      $("material-form").classList.add("hidden");
      $("material-form").reset();
      $("material-version").value = "Original";
      await loadMaterialTree();
    } catch (error) {
      showMessage("material-message", error.message, "error");
    }
  }
  let agendaSelected = new Date();

  function eventDate(event) {
    const value = event.starts_at || event.created_at;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function agendaKindIcon(kind) {
    return { rehearsal: "♪", concert: "★", note: "✎" }[kind] || "♪";
  }

  let agendaCursor = new Date();
  let agendaFilter = "";

  function eventMatchesFilter(event) {
    if (agendaFilter === "all") return true;
    if (agendaFilter === "personal") return event.scope === "personal" || !event.group_id;
    return String(event.group_id || "") === agendaFilter;
  }

  function renderAgendaFilters() {
    const container = $("agenda-filters");
    if (!container) return;
    container.replaceChildren();
    const options = [["all", "Todos"], ["personal", "Personal"]];
    (agendaState.groups || []).forEach((group) => options.push([group.id, group.name]));
    options.forEach(([value, label]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "agenda-filter" + (agendaFilter === value ? " active" : "");
      button.textContent = label;
      button.addEventListener("click", () => {
        agendaFilter = value;
        renderAgendaCalendar();
      });
      container.append(button);
    });
  }

  function renderAgendaCalendar() {
    const calendar = $("agenda-calendar");
    if (!calendar) return;
    const cursor = agendaCursor;
    const year = cursor.getFullYear();
    const month = cursor.getMonth();
    const monthLabel = new Intl.DateTimeFormat("es-ES", {
      month: "long", year: "numeric",
    }).format(cursor);
    $("agenda-month").textContent = monthLabel.charAt(0).toUpperCase() + monthLabel.slice(1);
    calendar.replaceChildren();
    ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"].forEach((day) => {
      const cell = document.createElement("div");
      cell.className = "dow";
      cell.textContent = day;
      calendar.append(cell);
    });
    const first = new Date(year, month, 1);
    const offset = (first.getDay() + 6) % 7;
    const start = new Date(year, month, 1 - offset);
    const events = (agendaState.events || []).filter(eventMatchesFilter);
    const todayKey = new Date().toDateString();
    for (let index = 0; index < 42; index += 1) {
      const date = new Date(start.getFullYear(), start.getMonth(), start.getDate() + index);
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "day" + (date.getMonth() !== month ? " muted" : "");
      if (date.toDateString() === agendaSelected.toDateString()) cell.classList.add("selected");
      if (date.toDateString() === todayKey) cell.classList.add("today");
      const number = document.createElement("span");
      number.className = "day-number";
      number.textContent = String(date.getDate());
      cell.append(number);
      const count = events.filter((event) => {
        const eventAt = eventDate(event);
        return eventAt && eventAt.toDateString() === date.toDateString();
      }).length;
      if (count) {
        const dot = document.createElement("span");
        dot.className = "dot";
        dot.title = `${count} ${count === 1 ? "evento" : "eventos"}`;
        cell.append(dot);
      }
      cell.addEventListener("click", () => {
        agendaSelected = date;
        agendaCursor = new Date(date.getFullYear(), date.getMonth(), 1);
        renderAgendaCalendar();
      });
      calendar.append(cell);
    }
    renderAgendaDay();
  }

  function agendaTime(event) {
    const at = eventDate(event);
    return at ? at.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" }) : "";
  }

  function renderAgendaDay() {
    const container = $("agenda-day-events");
    if (!container) return;
    container.replaceChildren();
    const title = new Intl.DateTimeFormat("es-ES", {
      weekday: "long", day: "2-digit", month: "long",
    }).format(agendaSelected);
    $("agenda-day-title").textContent = title.charAt(0).toUpperCase() + title.slice(1);
    const rows = (agendaState.events || [])
      .filter(eventMatchesFilter)
      .filter((event) => eventDate(event)?.toDateString() === agendaSelected.toDateString())
      .sort((a, b) => String(a.starts_at).localeCompare(String(b.starts_at)));
    if (!rows.length) {
      const empty = document.createElement("div");
      empty.className = "agenda-day-empty";
      const icon = document.createElement("span");
      icon.className = "agenda-empty-icon";
      icon.setAttribute("aria-hidden", "true");
      icon.textContent = "▦";
      const text = document.createElement("p");
      text.textContent = "No hay eventos este día.";
      empty.append(icon, text);
      container.append(empty);
      return;
    }
    rows.forEach((event) => {
      const card = document.createElement("article");
      card.className = "agenda-day-event";
      const head = document.createElement("div");
      head.className = "agenda-day-event-head";
      const time = document.createElement("strong");
      time.textContent = agendaTime(event) || "Todo el día";
      const creator = document.createElement("span");
      creator.className = "agenda-creator-badge";
      creator.textContent = event.creator_badge || "D";
      creator.title = "Creado por el autor de la cita";
      const kind = document.createElement("span");
      kind.className = "agenda-kind";
      kind.textContent = kindLabel(event.kind);
      head.append(time, creator, kind);
      if (event.can_manage) {
        const edit = document.createElement("button");
        edit.type = "button";
        edit.className = "agenda-edit-button";
        edit.textContent = "Editar";
        edit.addEventListener("click", () => openEventForm(event));
        head.append(edit);
      }
      const name = document.createElement("h4");
      name.textContent = event.title;
      const meta = document.createElement("p");
      meta.textContent = [event.location, event.group_name].filter(Boolean).join(" · ") || "Sin lugar asignado";
      card.append(head, name, meta);
      if (event.notes) {
        const notes = document.createElement("p");
        notes.className = "agenda-day-notes";
        notes.textContent = event.notes;
        card.append(notes);
      }
      if (event.kind !== "note" && event.scope !== "personal") {
        const actions = document.createElement("div");
        actions.className = "agenda-rsvp";
        [["yes", "Asisto"], ["no", "No asisto"]].forEach(([status, label]) => {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "agenda-rsvp-button" + (event.my_rsvp === status ? " active" : "");
          button.textContent = label;
          button.addEventListener("click", () => void setRsvp(event.id, status, button));
          actions.append(button);
        });
        card.append(actions);
      }
      container.append(card);
    });
  }

  function openAgendaModal() {
    agendaSelected = new Date();
    agendaCursor = new Date(agendaSelected.getFullYear(), agendaSelected.getMonth(), 1);
    if (!agendaFilter) agendaFilter = activeGroupId || "all";
    $("agenda-modal").classList.remove("hidden");
    renderAgendaFilters();
    renderAgendaCalendar();
  }

  function agendaMessageTarget() {
    const modal = $("agenda-modal");
    return modal && !modal.classList.contains("hidden") ? "agenda-message" : "dash-event-message";
  }

  async function setRsvp(eventId, status, button) {
    const target = agendaMessageTarget();
    setBusy(button, true, "Guardando…");
    try {
      await request(`/api/v1/events/${encodeURIComponent(eventId)}/rsvp`, {
        method: "POST",
        body: JSON.stringify({ status }),
      });
      await loadAgenda();
      showMessage(
        target,
        status === "yes" ? "Asistencia confirmada." : "Ausencia registrada.",
        "success",
      );
    } catch (error) {
      showMessage(target, error.message, "error");
    } finally {
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
      showWorkspace(data.nickname || data.email || data.user_id, data);
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
      showWorkspace(profile.nickname || profile.email || profile.user_id, profile);
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
      showWorkspace(profile.nickname || profile.email || email, profile);
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
  $("articles-button").addEventListener("click", () => void openArticles());
  $("articles-close").addEventListener("click", () => {
    $("articles-modal").classList.add("hidden");
  });
  $("article-new").addEventListener("click", () => selectArticle(null));
  $("article-save").addEventListener("click", () => void saveArticle());
  $("article-publish").addEventListener("click", () => void articleAction("publish"));
  $("article-withdraw").addEventListener("click", () => void articleAction("withdraw"));
  $("article-delete").addEventListener("click", () => {
    if (window.confirm("¿Eliminar este artículo?")) void articleAction("delete");
  });  $("active-group-button").addEventListener("click", openGroupPicker);

  let editingEvent = null;

  function localInputValue(value) {
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const pad = (number) => String(number).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  function populateEventGroups(selected) {
    const select = $("event-group");
    const preferred = selected || activeGroupId;
    const groups = (agendaState.groups || []).filter(
      (group) => group.can_manage || group.id === preferred,
    );
    select.replaceChildren();
    groups.forEach((group) => select.append(new Option(group.name, group.id)));
    if (preferred && groups.some((group) => group.id === preferred)) {
      select.value = preferred;
    }
    return groups;
  }

  async function loadEventSections(selected) {
    const groupId = $("event-group").value;
    const select = $("event-section");
    select.replaceChildren(new Option("Selecciona una sección", ""));
    if (!groupId) return;
    try {
      const catalog = await request(
        `/api/v1/groups/${encodeURIComponent(groupId)}/catalog`,
      );
      (catalog.section || []).forEach((item) => {
        select.append(new Option(item.name, item.id || ""));
      });
      const sectionOption = Array.from($("event-scope").options)
        .find((option) => option.value === "section");
      if (sectionOption) {
        sectionOption.disabled = select.options.length <= 1 && !selected;
      }
      if (selected) select.value = selected;
    } catch (_) {
      /* sin secciones */
    }
  }

  function syncEventForm() {
    const scope = $("event-scope").value;
    $("event-section-wrap").classList.toggle("hidden", scope !== "section");
    $("event-until-wrap").classList.toggle(
      "hidden", $("event-recurrence").value === "none",
    );
    $("event-edit-scope-wrap").classList.toggle(
      "hidden", !(editingEvent && editingEvent.is_series),
    );
  }

  async function openEventForm(event = null) {
    if (!(agendaState.groups || []).length) {
      try { await loadAgenda(); } catch (_) { /* sin grupos */ }
    }
    editingEvent = event;
    const form = $("event-form");
    form.reset();
    $("event-form-title").textContent = event ? "Editar cita" : "Nueva cita";
    $("event-save").textContent = event ? "Guardar cambios" : "Guardar cita";
    $("event-delete").classList.toggle("hidden", !(event && event.can_manage));
    $("event-delete-choice").classList.add("hidden");
    $("event-message").textContent = "";
    $("event-message").className = "message";
    const groups = populateEventGroups(event && event.group_id);
    let scope = "personal";
    if (event) {
      scope = event.group_id ? (event.section_id ? "section" : "group") : "personal";
    } else if (groups.length) {
      scope = "group";
    }
    $("event-scope").value = scope;
    $("event-title").value = event ? event.title : "";
    $("event-location").value = event ? event.location || "" : "";
    $("event-notes").value = event ? event.notes || "" : "";
    const start = event
      ? new Date(event.starts_at)
      : new Date(
        agendaSelected.getFullYear(), agendaSelected.getMonth(),
        agendaSelected.getDate(), 19, 0,
      );
    $("event-start").value = localInputValue(start);
    $("event-end").value = localInputValue(
      event && event.ends_at ? new Date(event.ends_at) : new Date(start.getTime() + 3600000),
    );
    $("event-recurrence").value = event ? event.recurrence || "none" : "none";
    $("event-until").value = event && event.recurrence_until
      ? new Date(event.recurrence_until).toISOString().slice(0, 10)
      : "";
    $("event-edit-scope").value = "single";
    syncEventForm();
    if (event && event.group_id) void loadEventSections(event.section_id);
    $("event-modal").classList.remove("hidden");
    $("event-title").focus();
  }

  function closeEventForm() {
    $("event-modal").classList.add("hidden");
    editingEvent = null;
  }

  $("agenda-new").addEventListener("click", () => openEventForm());
  $("event-close").addEventListener("click", closeEventForm);
  $("event-cancel").addEventListener("click", closeEventForm);
  $("event-delete-cancel").addEventListener("click", () => {
    $("event-delete-choice").classList.add("hidden");
  });
  $("event-scope").addEventListener("change", () => {
    syncEventForm();
    if ($("event-scope").value === "section") void loadEventSections();
  });
  $("event-group").addEventListener("change", () => { void loadEventSections(); });
  $("event-recurrence").addEventListener("change", () => {
    if ($("event-recurrence").value !== "none" && !$("event-until").value) {
      const start = new Date($("event-start").value);
      if (!Number.isNaN(start.getTime())) {
        const until = new Date(start.getFullYear(), start.getMonth() + 1, start.getDate());
        $("event-until").value = until.toISOString().slice(0, 10);
      }
    }
    syncEventForm();
  });
  $("event-start").addEventListener("change", () => {
    const start = new Date($("event-start").value);
    if (!Number.isNaN(start.getTime())) {
      $("event-end").value = localInputValue(new Date(start.getTime() + 3600000));
    }
  });

  $("event-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.submitter || $("event-save");
    setBusy(button, true, "Guardando…");
    const scope = $("event-scope").value;
    const startsAt = new Date($("event-start").value);
    const endsAt = $("event-end").value ? new Date($("event-end").value) : null;
    if (Number.isNaN(startsAt.getTime())) {
      showMessage("event-message", "Indica una fecha de inicio válida.", "error");
      setBusy(button, false);
      return;
    }
    if (endsAt && (Number.isNaN(endsAt.getTime()) || endsAt <= startsAt)) {
      showMessage("event-message", "La fecha de fin debe ser posterior al inicio.", "error");
      setBusy(button, false);
      return;
    }
    const recurrence = $("event-recurrence").value;
    const until = $("event-until").value;
    if (recurrence !== "none" && !until) {
      showMessage("event-message", "Indica hasta cuándo se repite.", "error");
      setBusy(button, false);
      return;
    }
    const payload = {
      group_id: scope === "personal" ? null : $("event-group").value,
      scope,
      section_id: scope === "section" ? $("event-section").value || null : null,
      recipient_subs: [],
      kind: editingEvent ? editingEvent.kind : "rehearsal",
      title: $("event-title").value.trim(),
      starts_at: startsAt.toISOString(),
      ends_at: endsAt ? endsAt.toISOString() : null,
      location: $("event-location").value.trim() || null,
      notes: $("event-notes").value.trim() || null,
      recurrence,
      recurrence_until: recurrence === "none" || !until
        ? null
        : new Date(`${until}T23:59:59`).toISOString(),
      edit_scope: editingEvent && editingEvent.is_series
        ? $("event-edit-scope").value
        : "single",
    };
    try {
      const wasEditing = Boolean(editingEvent);
      if (editingEvent) {
        await request(`/api/v1/events/${encodeURIComponent(editingEvent.id)}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      } else {
        await request("/api/v1/events", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      closeEventForm();
      await loadAgenda();
      showMessage(
        "agenda-message",
        wasEditing ? "Cita actualizada." : "Cita creada.",
        "success",
      );
    } catch (error) {
      showMessage("event-message", error.message, "error");
    } finally {
      setBusy(button, false);
    }
  });

  async function deleteEvent(scope) {
    if (!editingEvent) return;
    try {
      await request(
        `/api/v1/events/${encodeURIComponent(editingEvent.id)}?scope=${scope}`,
        { method: "DELETE" },
      );
      closeEventForm();
      await loadAgenda();
      showMessage(
        "agenda-message",
        scope === "series" ? "Secuencia eliminada." : "Cita eliminada.",
        "success",
      );
    } catch (error) {
      showMessage("event-message", error.message, "error");
    }
  }

  $("event-delete").addEventListener("click", () => {
    if (editingEvent && editingEvent.is_series) {
      $("event-delete-choice").classList.remove("hidden");
      return;
    }
    if (window.confirm("¿Eliminar esta cita?")) void deleteEvent("single");
  });
  $("event-delete-single").addEventListener("click", () => { void deleteEvent("single"); });
  $("event-delete-series").addEventListener("click", () => { void deleteEvent("series"); });
  const _msgContent = $("msg-content");
  if (_msgContent) {
    $("inbox-compose").appendChild(_msgContent);
    _msgContent.classList.add("hidden");
  }

  $("inbox-button").addEventListener("click",()=>{mailboxMode="inbox";mailboxGroupId="";setMailboxTab("inbox");void openInbox(false);});
  $("messages-new").addEventListener("click",()=>{void openInbox(true);});
  document.querySelectorAll(".mailbox-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      mailboxMode = tab.dataset.mailbox || "inbox";
      mailboxGroupId = "";
      setMailboxTab(mailboxMode);
      void openInbox(false);
    });
  });
  $("inbox-close").addEventListener("click",()=>{$("inbox-modal").classList.add("hidden");});
  $("inbox-back").addEventListener("click",()=>{void openInbox(false);});
  $("inbox-reply").addEventListener("submit",(event)=>{void sendInboxReply(event, true);});
  $("inbox-reply-sender").addEventListener("click",()=>{void sendInboxReply({preventDefault(){}}, false);});
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
  $("material-import-toggle").addEventListener("click",()=>{$("material-form").classList.toggle("hidden");});
  $("material-form").addEventListener("submit",(event)=>{void importMaterial(event);});
  $("material-group").addEventListener("change",()=>{void loadMaterialSections();});
  $("repertoire-add").addEventListener("click",()=>{
    document.getElementById("library-section").scrollIntoView({behavior:"smooth"});
    $("material-form").classList.remove("hidden");
    $("material-files").focus();
  });
  $("open-agenda").addEventListener("click", openAgendaModal);
  $("agenda-close").addEventListener("click",()=>{$("agenda-modal").classList.add("hidden");});
  $("agenda-prev").addEventListener("click",()=>{
    agendaCursor = new Date(agendaCursor.getFullYear(), agendaCursor.getMonth() - 1, 1);
    agendaSelected = new Date(agendaCursor.getFullYear(), agendaCursor.getMonth(), 1);
    renderAgendaCalendar();
  });
  $("agenda-next").addEventListener("click",()=>{
    agendaCursor = new Date(agendaCursor.getFullYear(), agendaCursor.getMonth() + 1, 1);
    agendaSelected = new Date(agendaCursor.getFullYear(), agendaCursor.getMonth(), 1);
    renderAgendaCalendar();
  });
  $("agenda-today").addEventListener("click",()=>{
    agendaSelected = new Date();
    agendaCursor = new Date(agendaSelected.getFullYear(), agendaSelected.getMonth(), 1);
    renderAgendaCalendar();
  });
  $("material-view-button").addEventListener("click",()=>{void loadMaterialTree($("material-view-group").value);});
  $("material-part").disabled = true;
  $("material-files").addEventListener("change",()=>{
    const first = $("material-files").files?.[0];
    if (first && !$("material-work").value) {
      $("material-work").value = first.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ");
    }
  });
  const materialForm = $("material-form");
  if (materialForm) {
    materialForm.prepend($("material-folder").closest("label"));
    materialForm.prepend($("material-files").closest("label"));
  }
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
  function avatarDataFromFile(file) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      const url = URL.createObjectURL(file);
      image.onload = () => {
        try {
          const side = Math.min(image.width, image.height);
          const sx = (image.width - side) / 2;
          const sy = (image.height - side) / 2;
          const canvas = document.createElement("canvas");
          canvas.width = 256;
          canvas.height = 256;
          const context = canvas.getContext("2d");
          context.drawImage(image, sx, sy, side, side, 0, 0, 256, 256);
          resolve(canvas.toDataURL("image/jpeg", 0.82));
        } catch (error) {
          reject(error);
        } finally {
          URL.revokeObjectURL(url);
        }
      };
      image.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error("No se pudo leer la imagen"));
      };
      image.src = url;
    });
  }
  const avatarFile = $("avatar-file");
  if (avatarFile) avatarFile.addEventListener("change", async (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    if (!/^image\/(jpeg|png|webp)$/.test(file.type)) {
      showMessage("avatar-message", "Usa una imagen JPG, PNG o WebP.", "error");
      event.target.value = "";
      return;
    }
    showMessage("avatar-message", "Subiendo foto…");
    try {
      const data = await avatarDataFromFile(file);
      const profile = await request("/api/v1/auth/me/avatar", {
        method: "PATCH",
        body: JSON.stringify({data}),
      });
      profileAvatarUrl = profile && profile.avatar_url
        ? `${profile.avatar_url}?v=${Date.now()}`
        : null;
      paintAvatar($("account-label").querySelector(".account-avatar"), profileAvatarInitials, profileAvatarUrl);
      paintAvatar($("dash-avatar"), profileAvatarInitials, profileAvatarUrl);
      paintAvatar($("profile-avatar-preview"), profileAvatarInitials, profileAvatarUrl);
      showMessage("avatar-message", "Foto actualizada.", "ok");
    } catch (error) {
      showMessage("avatar-message", error.message, "error");
    } finally {
      event.target.value = "";
    }
  });
  const avatarRemove = $("avatar-remove");
  if (avatarRemove) avatarRemove.addEventListener("click", async () => {
    showMessage("avatar-message", "Quitando foto…");
    try {
      const profile = await request("/api/v1/auth/me/avatar", {method: "DELETE"});
      profileAvatarUrl = profile && profile.avatar_url
        ? `${profile.avatar_url}?v=${Date.now()}`
        : null;
      paintAvatar($("account-label").querySelector(".account-avatar"), profileAvatarInitials, profileAvatarUrl);
      paintAvatar($("dash-avatar"), profileAvatarInitials, profileAvatarUrl);
      paintAvatar($("profile-avatar-preview"), profileAvatarInitials, profileAvatarUrl);
      showMessage("avatar-message", "Foto eliminada.", "ok");
    } catch (error) {
      showMessage("avatar-message", error.message, "error");
    }
  });
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
      try{const profile=await request("/api/v1/auth/me",{},false);if(profile.onboarding && profile.onboarding.required){showMessage("login-error","Completa primero el alta de tu cuenta OSAP.","error");return;}showWorkspace(profile.nickname || profile.email || profile.user_id, profile);}
      catch(_){accessToken=null;}
    });
  }
})();

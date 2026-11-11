(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
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
    $("account-label").textContent = profileLabel || "Sesión iniciada";
    refreshLibrary().catch(()=>{});
  }
  function showLogin() {
    $("workspace-view").classList.add("hidden");
    $("login-view").classList.remove("hidden");
    $("logout-button").classList.add("hidden");
    $("account-label").textContent = "";
  }
  async function refreshLibrary() {
    const data = await request("/api/v1/library");
    renderLibrary(data || {});
  }
  function renderLibrary(data) {
    const items = data.items || [];
    const collections = data.collections || [];
    $("library-summary").textContent = items.length + " elementos · " + collections.length + " colecciones";
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
      const title = document.createElement("strong");
      title.textContent = item.title || "Sin título";
      const meta = document.createElement("span");
      meta.className = "muted";
      meta.textContent = item.kind === "local_work"
        ? "Obra propia"
        : "OSAP · " + (item.external_work_id || "");
      li.append(title, meta);
      list.append(li);
    });
  }
  async function saveReference(work, rep, button) {
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
        title: work.title || "Obra de OSAP",
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
  function groupRepresentations(reps) {
    const groups = new Map();
    for (const rep of reps) {
      const provider = String(rep.provider || "original");
      const format = String(rep.format || "archivo");
      const key = provider.toLowerCase() + "|" + format.toLowerCase();
      const entry = groups.get(key) || { rep, provider, format, count: 0 };
      entry.count += 1;
      groups.set(key, entry);
    }
    return [...groups.values()];
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
      const variants = groupRepresentations(reps);
      const providers = [...new Set(variants.map((variant) => variant.provider))];
      const card = document.createElement("article");
      card.className = "result-card";
      const info = document.createElement("div");
      const title = document.createElement("h3");
      title.textContent = work.title || "Obra sin título";
      const meta = document.createElement("div");
      meta.className = "result-meta";
      meta.textContent = [work.composer, work.catalogue,
        variants.length ? variants.length + " formatos · " + providers.join(", ") : "sin representaciones"]
        .filter(Boolean).join(" · ");
      info.append(title,meta);
      const actions = document.createElement("div");
      actions.className = "result-actions";
      variants.forEach(({ rep, provider, format, count }) => {
        const fmt = String(format).toLowerCase();
        const supported = /mxl|musicxml|\.xml|midi|\.mid|mscz|mscx|capella|\.capx|\.gp|\.gpx/.test(fmt);
        const group = document.createElement("div");
        group.className = "rep-group";
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "button button-outline rep-button";
        btn.textContent = "Usar " + provider + " · " + format;
        btn.disabled = rep.available === false || !supported;
        btn.title = btn.disabled
          ? "Formato no descargable o no compatible con el editor"
          : (count > 1 ? count + " variantes; se usará la primera" : "Crear borrador desde esta representación");
        btn.addEventListener("click", () => startFromOsap(work,rep,btn));
        const save = document.createElement("button");
        save.type = "button";
        save.className = "rep-save";
        save.textContent = "Guardar";
        save.title = "Guardar esta referencia en tu biblioteca";
        save.addEventListener("click", () => saveReference(work,rep,save));
        group.append(btn, save);
        actions.append(group);
      });
      if (!variants.length) {
        const note = document.createElement("span"); note.className = "result-meta"; note.textContent = "No hay representaciones disponibles."; actions.append(note);
      }
      card.append(info,actions);
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
      $("draft-section").scrollIntoView({behavior:"smooth",block:"center"});
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
      const wrapper = "/editor.html?src=" + encodeURIComponent(data.editor_url)
        + "&title=" + encodeURIComponent(title);
      window.open(wrapper,"_blank","noopener");
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
  $("new-draft-button").addEventListener("click",async()=>{
    const button=$("new-draft-button");setBusy(button,true,"Creando borrador…");
    try {currentDraft=await createDraft($("new-title").value.trim() || null);showDraft($("new-title").value.trim() || "Nueva partitura","Borrador privado · partitura creada desde cero");showMessage("draft-message","Borrador creado. Abre MuseEncore para escribir y exporta el resultado como .mxl.");$("draft-section").scrollIntoView({behavior:"smooth",block:"center"});}
    catch(error){showMessage("draft-message",error.message,"error");}
    finally{setBusy(button,false);}
  });
  $("open-editor-button").addEventListener("click",openEditor);
  $("library-refresh").addEventListener("click",()=>{refreshLibrary().catch((error)=>showMessage("library-message",error.message,"error"));});
  $("mxl-file").addEventListener("change",(event)=>uploadMxl(event.target.files[0]));
  $("logout-button").addEventListener("click",async()=>{
    try{if(accessToken)await request("/api/v1/auth/logout",{method:"POST"},false);}catch(_){}
    accessToken=null;currentDraft=null;showLogin();
  });
  const hashToken = new URLSearchParams(location.hash.replace(/^#/, "")).get("access_token");
  if (hashToken) {
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

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
  async function refreshLibrary(query) {
    const path = query
      ? "/api/v1/library?q=" + encodeURIComponent(query)
      : "/api/v1/library";
    const data = await request(path);
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

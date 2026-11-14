(() => {
  const form = document.getElementById("alta-form");
  const message = document.getElementById("alta-message");
  const submit = document.getElementById("alta-submit");
  const success = document.getElementById("alta-success");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const data = new FormData(form);
    const interests = [];
    for (const [key, value] of [
      ["subscription", "subscription"],
      ["whatsapp", "whatsapp"],
      ["sms", "sms"],
    ]) {
      if (data.get(key)) interests.push(value);
    }
    const members = String(data.get("members") || "").trim();
    const payload = {
      entity_name: String(data.get("entity_name") || "").trim(),
      entity_kind: String(data.get("entity_kind") || "coral"),
      city: String(data.get("city") || "").trim() || null,
      members: members ? Number(members) : null,
      contact_name: String(data.get("contact_name") || "").trim(),
      contact_email: String(data.get("contact_email") || "").trim(),
      contact_phone: String(data.get("contact_phone") || "").trim() || null,
      website: String(data.get("website") || "").trim() || null,
      interests,
      message: String(data.get("message") || "").trim() || null,
      consent: Boolean(data.get("consent")),
      company_website: String(data.get("company_website") || ""),
    };
    submit.disabled = true;
    submit.textContent = "Enviando…";
    if (message) {
      message.textContent = "";
      message.className = "message";
    }
    try {
      const response = await fetch("/api/v1/entity-leads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || "No se pudo enviar la solicitud");
      }
      form.classList.add("hidden");
      if (success) {
        success.classList.remove("hidden");
        const name = document.getElementById("alta-success-name");
        if (name) name.textContent = payload.entity_name;
      }
    } catch (error) {
      if (message) {
        message.textContent = error instanceof Error ? error.message : "No se pudo enviar";
        message.className = "message error";
      }
      submit.disabled = false;
      submit.textContent = "Solicitar alta";
    }
  });
})();

(() => {
  const toast = document.getElementById("toast");
  let toastTimer = null;

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("visible");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove("visible"), 3200);
  }

  const notificationsButton = document.getElementById("notifications-button");
  const popover = document.getElementById("notifications-popover");
  function closePopover() {
    if (!popover) return;
    popover.classList.add("hidden");
    notificationsButton?.setAttribute("aria-expanded", "false");
  }
  notificationsButton?.addEventListener("click", (event) => {
    event.stopPropagation();
    const open = popover?.classList.toggle("hidden") === false;
    notificationsButton.setAttribute("aria-expanded", open ? "true" : "false");
  });
  document.addEventListener("click", (event) => {
    if (popover && !popover.classList.contains("hidden") && !popover.contains(event.target)) {
      closePopover();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closePopover();
  });

  const rsvpCount = document.getElementById("rsvp-count");
  const rsvpButtons = Array.from(document.querySelectorAll(".rsvp"));
  rsvpButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const already = button.classList.contains("selected");
      rsvpButtons.forEach((item) => item.classList.remove("selected"));
      if (!already) button.classList.add("selected");
      if (rsvpCount) {
        rsvpCount.textContent = already ? "18 de 34 han respondido" : "19 de 34 han respondido";
      }
      showToast(already ? "Respuesta retirada." : "Asistencia guardada. ¡Gracias!");
    });
  });

  document.getElementById("notify-manager")?.addEventListener("click", () => {
    showToast("Aviso enviado al responsable. Te contestará por aquí.");
  });

  document.getElementById("cover-search")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const query = document.getElementById("cover-query")?.value.trim();
    showToast(query ? `Vista previa: se buscará “${query}” en OSAP.` : "Escribe una obra, compositor o catálogo.");
  });

  const navLinks = Array.from(document.querySelectorAll(".cover-nav a"));
  navLinks.forEach((link) => {
    link.addEventListener("click", () => {
      navLinks.forEach((item) => item.classList.toggle("active", item === link));
      closePopover();
    });
  });
})();

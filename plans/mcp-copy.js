// The endpoint remains selectable when clipboard access is unavailable.
(() => {
  for (const button of document.querySelectorAll("[data-copy-endpoint]")) {
    const endpoint = document.getElementById(button.dataset.copyEndpoint);
    const status = button
      .closest(".endpoint-card")
      ?.querySelector('[role="status"]');
    if (!endpoint || !status || !navigator.clipboard?.writeText) continue;
    button.hidden = false;
    button.addEventListener("click", async () => {
      status.textContent = "";
      button.disabled = true;
      try {
        await navigator.clipboard.writeText(endpoint.textContent.trim());
        status.textContent = "Copied";
      } catch {
        status.textContent = "Copy unavailable. Select and copy the URL above.";
      } finally {
        button.disabled = false;
      }
    });
  }
})();

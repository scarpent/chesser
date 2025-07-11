export function navigateWithSpinner(url, delay = 300) {
  window.dispatchEvent(new CustomEvent("show-loading"));
  setTimeout(() => {
    window.location.href = url;
  }, delay);
}

window.addEventListener("pageshow", () => {
  window.dispatchEvent(new CustomEvent("hide-loading"));
});

// use overlay on all local links
document.addEventListener("DOMContentLoaded", () => {
  const origin = window.location.origin;

  document.querySelectorAll("a[href]").forEach((link) => {
    const href = link.getAttribute("href");

    // Skip external, anchor, or modifier-clickable links
    if (
      !href.startsWith("/") || // skip external
      href.startsWith("#") ||
      link.hasAttribute("target") ||
      link.dataset.noSpinner // opt-out per-link
    ) {
      return;
    }

    link.addEventListener("click", (e) => {
      if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey || e.button !== 0) {
        return; // allow modifiers (new tab, etc)
      }

      e.preventDefault();
      window.navigateWithSpinner(href);
    });
  });
});

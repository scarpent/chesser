window.addEventListener("pageshow", () => {
  // Ensure loading overlay is hidden on load or bfcache restore
  // (Alpine doesn't reset x-data when using browser back)
  window.dispatchEvent(new CustomEvent("hide-loading"));
});

// use overlay on all local links
document.addEventListener("DOMContentLoaded", () => {
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

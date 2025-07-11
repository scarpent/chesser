export function navigateWithSpinner(url, delay = 150) {
  window.dispatchEvent(new CustomEvent("show-loading"));
  setTimeout(() => {
    window.location.href = url;
  }, delay);
}

window.addEventListener("pageshow", () => {
  // Force kill spinner; not using Alpine CustomEvent because
  // it doesn't want to work on browser "back" navigation
  // (Alpine may not be ready - let's just brute force it)
  const overlay = document.querySelector(".loading-overlay");
  if (overlay) {
    overlay.style.display = "none";
    overlay.style.opacity = "0";
    overlay.innerHTML = ""; // optional, for good measure
  }
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

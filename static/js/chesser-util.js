// Small global helpers shared across Chesser pages.
//
// Note: this file is intentionally a classic (non-module) script and
// intentionally attaches helpers to `window`.
//
// Alpine inline expressions (e.g. x-init="setPageTitle(...)",
// @click="window.navigateWithSpinner('/')") are evaluated in the global
// scope at interaction time. They cannot see ES module exports unless
// explicitly bridged, and module execution timing can introduce subtle
// races on fast clicks or cold loads.
//
// For simple cross-page helpers used by Alpine, this classic-global
// pattern has proven to be more reliable and easier to reason about.
//
// Keep this file small and dependency-free.
function isDemoMode() {
  return document.documentElement?.dataset?.demo === "1";
}

function setPageTitle(baseTitle) {
  document.title = isDemoMode() ? `${baseTitle} (Demo)` : baseTitle;
}

function navigateWithSpinner(url, delay = 150) {
  // Used by inline Alpine expressions (e.g. @click="window.navigateWithSpinner('/')")
  // and by loading.js for local-link interception.
  window.dispatchEvent(new CustomEvent("show-loading"));
  setTimeout(() => {
    window.location.href = url;
  }, delay);
}

window.readJsonScript = function (id) {
  const el = document.getElementById(id);
  if (!el) throw new Error(`json_script element not found: ${id}`);
  return JSON.parse(el.textContent);
};

// Expose globally for Alpine expressions.
window.isDemoMode = isDemoMode;
window.setPageTitle = setPageTitle;
window.navigateWithSpinner = navigateWithSpinner;

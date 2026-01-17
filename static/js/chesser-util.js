// Small global helpers shared across Chesser pages.
//
// Note: this file is intentionally a classic (non-module) script and
// intentionally attaches helpers to `window`. Alpine inline expressions
// (e.g. x-init="setPageTitle(...)") are evaluated in the global scope and
// cannot see ES module exports unless you explicitly bridge them.
//
// Keep this file small and dependency-free.
function isDemoMode() {
  return document.documentElement?.dataset?.demo === "1";
}

function setPageTitle(baseTitle) {
  document.title = isDemoMode() ? `${baseTitle} (Demo)` : baseTitle;
}

// Expose globally for Alpine expressions.
window.isDemoMode = isDemoMode;
window.setPageTitle = setPageTitle;

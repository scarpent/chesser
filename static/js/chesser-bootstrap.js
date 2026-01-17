// static/js/chesser-bootstrap.js
//
// Chesser bootstrap: attach a few cross-page helpers to `window`.
//
// This file is intentionally small and side-effectful:
// it wires shared utilities into the global scope so they can be called from
// inline HTML/Alpine expressions (e.g. @click="window.navigateWithSpinner('/')").
//
// Keep this file minimal; app logic should stay in page modules (variation.js,
// edit.js, etc.) and pure helpers should live in chesser-util.js.

import { navigateWithSpinner } from "./loading.js";

window.navigateWithSpinner = navigateWithSpinner;

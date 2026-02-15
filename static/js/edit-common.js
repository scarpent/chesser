// Shared helpers for edit.js and edit-shared.js

/**
 * POST JSON to a Django endpoint with CSRF protection.
 * Returns the parsed response JSON. Throws on network error.
 */
export async function postJson(endpoint, payload) {
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    credentials: "same-origin",
    body: JSON.stringify(payload),
  });
  return await response.json();
}

/**
 * Toggle save-button CSS classes to reflect pending/success/error state.
 */
export function handleSaveButton(status) {
  const btn = document.querySelector(".icon-save");
  if (btn) {
    btn.classList.remove("save-pending");
    btn.classList.add(`save-${status}`);
  }
}

/**
 * Parse a shapes JSON string into an array. Returns [] for falsy/empty input.
 */
export function parseShapes(shapesString) {
  return shapesString ? JSON.parse(shapesString) : [];
}

/**
 * Read shapes from a Chessground board and serialize to JSON string or "".
 */
export function serializeShapes(board) {
  const shapes = board.state.drawable.shapes;
  return shapes.length > 0 ? JSON.stringify(shapes) : "";
}

/**
 * Normalize annotation: convert the "none" sentinel to empty string.
 */
export function normalizeAnnotation(annotation) {
  return annotation === "none" ? "" : annotation;
}

/**
 * Create a Chessground board with shared default config.
 * extraConfig is merged into the defaults (shallow).
 */
export function createBoard(element, fen, orientation, extraConfig = {}) {
  return window.Chessground(element, {
    fen,
    orientation,
    coordinates: false,
    movable: { free: false, showDests: false },
    highlight: { lastMove: true, check: true },
    ...extraConfig,
  });
}

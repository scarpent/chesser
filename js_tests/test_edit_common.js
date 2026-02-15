import { describe, it, beforeEach, mock } from "node:test";
import assert from "node:assert/strict";
import {
  parseShapes,
  serializeShapes,
  normalizeAnnotation,
  handleSaveButton,
  postJson,
} from "../static/js/edit-common.js";

// --- parseShapes ---

describe("parseShapes", () => {
  it("returns empty array for null", () => {
    assert.deepEqual(parseShapes(null), []);
  });

  it("returns empty array for undefined", () => {
    assert.deepEqual(parseShapes(undefined), []);
  });

  it("returns empty array for empty string", () => {
    assert.deepEqual(parseShapes(""), []);
  });

  it("parses valid JSON array", () => {
    const shapes = [{ orig: "e2", dest: "e4", brush: "green" }];
    assert.deepEqual(parseShapes(JSON.stringify(shapes)), shapes);
  });

  it("parses empty JSON array", () => {
    assert.deepEqual(parseShapes("[]"), []);
  });
});

// --- serializeShapes ---

describe("serializeShapes", () => {
  it("returns empty string for empty shapes array", () => {
    const board = { state: { drawable: { shapes: [] } } };
    assert.equal(serializeShapes(board), "");
  });

  it("returns JSON string for non-empty shapes", () => {
    const shapes = [{ orig: "e2", dest: "e4", brush: "green" }];
    const board = { state: { drawable: { shapes } } };
    assert.equal(serializeShapes(board), JSON.stringify(shapes));
  });

  it("handles multiple shapes", () => {
    const shapes = [
      { orig: "e2", dest: "e4", brush: "green" },
      { orig: "d2", dest: "d4", brush: "red" },
    ];
    const board = { state: { drawable: { shapes } } };
    const result = JSON.parse(serializeShapes(board));
    assert.equal(result.length, 2);
  });
});

// --- normalizeAnnotation ---

describe("normalizeAnnotation", () => {
  it('converts "none" to empty string', () => {
    assert.equal(normalizeAnnotation("none"), "");
  });

  it("passes through regular annotations", () => {
    assert.equal(normalizeAnnotation("!"), "!");
  });

  it("passes through empty string", () => {
    assert.equal(normalizeAnnotation(""), "");
  });

  it("passes through question mark", () => {
    assert.equal(normalizeAnnotation("?"), "?");
  });

  it("passes through brilliant move annotation", () => {
    assert.equal(normalizeAnnotation("!!"), "!!");
  });
});

// --- handleSaveButton ---

describe("handleSaveButton", () => {
  let mockBtn;

  beforeEach(() => {
    // Minimal DOM mock
    mockBtn = {
      classList: {
        _classes: new Set(["save-pending"]),
        add(cls) {
          this._classes.add(cls);
        },
        remove(cls) {
          this._classes.delete(cls);
        },
        contains(cls) {
          return this._classes.has(cls);
        },
      },
    };
    globalThis.document = {
      querySelector(sel) {
        return sel === ".icon-save" ? mockBtn : null;
      },
    };
  });

  it("removes save-pending and adds save-success", () => {
    handleSaveButton("success");
    assert.equal(mockBtn.classList.contains("save-pending"), false);
    assert.equal(mockBtn.classList.contains("save-success"), true);
  });

  it("removes save-pending and adds save-error", () => {
    handleSaveButton("error");
    assert.equal(mockBtn.classList.contains("save-pending"), false);
    assert.equal(mockBtn.classList.contains("save-error"), true);
  });

  it("handles missing button gracefully", () => {
    globalThis.document = {
      querySelector() {
        return null;
      },
    };
    // Should not throw
    handleSaveButton("success");
  });
});

// --- postJson ---

describe("postJson", () => {
  beforeEach(() => {
    // Mock getCookie globally (it's a global in the app via csrf.js)
    globalThis.getCookie = () => "fake-csrf-token";
  });

  it("sends POST with correct headers and returns parsed JSON", async () => {
    const expectedPayload = { variation_id: 1, title: "Test" };
    const expectedResponse = { status: "success" };

    globalThis.fetch = mock.fn(async (url, opts) => {
      assert.equal(url, "/save-variation/");
      assert.equal(opts.method, "POST");
      assert.equal(opts.headers["Content-Type"], "application/json");
      assert.equal(opts.headers["X-CSRFToken"], "fake-csrf-token");
      assert.equal(opts.credentials, "same-origin");
      assert.deepEqual(JSON.parse(opts.body), expectedPayload);
      return {
        json: async () => expectedResponse,
      };
    });

    const result = await postJson("/save-variation/", expectedPayload);
    assert.deepEqual(result, expectedResponse);
  });

  it("propagates fetch errors", async () => {
    globalThis.fetch = mock.fn(async () => {
      throw new Error("Network error");
    });

    await assert.rejects(() => postJson("/save-variation/", {}), {
      message: "Network error",
    });
  });

  it("returns error status from server", async () => {
    const errorResponse = { status: "error", message: "Bad data" };

    globalThis.fetch = mock.fn(async () => ({
      json: async () => errorResponse,
    }));

    const result = await postJson("/save-variation/", {});
    assert.equal(result.status, "error");
    assert.equal(result.message, "Bad data");
  });
});

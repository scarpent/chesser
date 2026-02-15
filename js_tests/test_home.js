import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  resolveNextDue,
  formatCountdownTick,
  FUDGE_SECONDS,
  COUNTDOWN_THRESHOLD,
} from "../static/js/home.js";

// --- resolveNextDue ---

describe("resolveNextDue", () => {
  it("no future reviews, nothing due now", () => {
    const result = resolveNextDue({
      has_due_now: false,
      seconds_until: null,
      label: "…?",
    });
    assert.equal(result.label, "🔮 Next: …?");
    assert.equal(result.countdown, null);
  });

  it("no future reviews, something due now", () => {
    const result = resolveNextDue({
      has_due_now: true,
      seconds_until: null,
      label: "…?",
    });
    assert.equal(result.label, "⏰ Next: Now, and then in …?");
    assert.equal(result.countdown, null);
  });

  it("future review > 5 min away, nothing due now", () => {
    const result = resolveNextDue({
      has_due_now: false,
      seconds_until: 600,
      label: "10m",
    });
    assert.equal(result.label, "🔮 Next: 10m");
    assert.equal(result.countdown, null);
  });

  it("future review > 5 min away, something due now", () => {
    const result = resolveNextDue({
      has_due_now: true,
      seconds_until: 3600,
      label: "1h",
    });
    assert.equal(result.label, "⏰ Next: Now, and then in 1h");
    assert.equal(result.countdown, null);
  });

  it("future review <= 5 min away triggers countdown", () => {
    const result = resolveNextDue({
      has_due_now: false,
      seconds_until: 120,
      label: "2m",
    });
    assert.notEqual(result.countdown, null);
    assert.equal(result.countdown.seconds, 120 + FUDGE_SECONDS);
    assert.equal(result.countdown.prefix, "");
  });

  it("countdown with due-now prefix", () => {
    const result = resolveNextDue({
      has_due_now: true,
      seconds_until: 60,
      label: "1m",
    });
    assert.notEqual(result.countdown, null);
    assert.equal(result.countdown.seconds, 60 + FUDGE_SECONDS);
    assert.equal(result.countdown.prefix, "Now, and then in ");
  });

  it("threshold boundary: seconds_until where fudged == 300 counts down", () => {
    // 298 + 2 fudge = 300, which is NOT > 300, so should countdown
    const result = resolveNextDue({
      has_due_now: false,
      seconds_until: COUNTDOWN_THRESHOLD - FUDGE_SECONDS,
      label: "4m 58s",
    });
    assert.notEqual(result.countdown, null);
    assert.equal(result.countdown.seconds, COUNTDOWN_THRESHOLD);
  });

  it("threshold boundary: seconds_until where fudged == 301 does not", () => {
    // 299 + 2 fudge = 301, which IS > 300, so no countdown
    const result = resolveNextDue({
      has_due_now: false,
      seconds_until: COUNTDOWN_THRESHOLD - FUDGE_SECONDS + 1,
      label: "4m 59s",
    });
    assert.equal(result.countdown, null);
  });
});

// --- formatCountdownTick ---

describe("formatCountdownTick", () => {
  it("formats minutes and seconds", () => {
    assert.equal(formatCountdownTick(125, ""), "⏰ Next: 2m 5s");
  });

  it("formats with prefix", () => {
    assert.equal(
      formatCountdownTick(65, "Now, and then in "),
      "⏰ Next: Now, and then in 1m 5s",
    );
  });

  it("sub-minute shows dynamite emoji", () => {
    assert.equal(formatCountdownTick(42, ""), "⏰ Next: 42 🧨");
  });

  it("value of 1 shows Now!", () => {
    assert.equal(formatCountdownTick(1, ""), "⏰ Next: 🚀 Now!");
  });

  it("value of 0 shows Now!", () => {
    assert.equal(formatCountdownTick(0, ""), "⏰ Next: 🚀 Now!");
  });

  it("exactly 60 seconds shows 1m 0s", () => {
    assert.equal(formatCountdownTick(60, ""), "⏰ Next: 1m 0s");
  });
});

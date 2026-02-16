function buildNavQueryString(nav) {
  const params = [];
  if (nav?.color) params.push(`color=${nav.color}`);
  if (nav?.chapter_id) params.push(`chapter_id=${nav.chapter_id}`);
  return params.length ? "?" + params.join("&") : "";
}

export function homeApp() {
  return {
    homeData: homeData,

    initHome() {
      this.scrollToVariationIfNeeded();

      // test in console document.dispatchEvent(new Event("visibilitychange"));
      this.$nextTick(() => {
        document.addEventListener("visibilitychange", () => {
          if (document.visibilityState === "visible") {
            // console.log("➡️  Dispatching next-due-refresh");
            window.dispatchEvent(new CustomEvent("next-due-refresh"));
          }
        });
      });
    },

    //--------------------------------------------------------------------------------
    scrollToVariationIfNeeded() {
      const params = new URLSearchParams(window.location.search);
      const varId = params.get("id");
      if (!varId) return;

      this.$nextTick(() => {
        const el = document.getElementById("var_" + varId);
        if (el) {
          el.scrollIntoView({ behavior: "auto", block: "start" });
          el.classList.add("chapter-var-highlight");
        }
      });

      window.history.replaceState({}, "", window.location.pathname);
    },

    //--------------------------------------------------------------------------------
    goToRandomReview() {
      const url = "/review/random/" + buildNavQueryString(this.homeData.nav);
      window.navigateWithSpinner(url);
    },

    //--------------------------------------------------------------------------------
    titleCase(str) {
      return str ? str.charAt(0).toUpperCase() + str.slice(1) : "";
    },

    //--------------------------------------------------------------------------------
    demoCard() {
      return {
        storageKey: "chesser_demo_card_open",
        isOpen: true,

        init() {
          const raw = localStorage.getItem(this.storageKey);
          if (raw !== null) {
            this.isOpen = raw === "true";
          }
        },

        toggle() {
          this.isOpen = !this.isOpen;
          localStorage.setItem(this.storageKey, String(this.isOpen));
        },
      };
    },
  };
}

// --- Pure functions (testable) -------------------------------------------

export const FUDGE_SECONDS = 2;
export const COUNTDOWN_THRESHOLD = 5 * 60;

export function resolveNextDue(data) {
  const prefix = data.has_due_now ? "Now, and then in " : "";
  const emoji = data.has_due_now ? "\u23F0" : "\uD83D\uDD2E";

  const staticLabel = `${emoji} Next: ${prefix}${data.label}`;

  if (data.seconds_until == null) {
    return { label: staticLabel, countdown: null };
  }

  const countdownSeconds = data.seconds_until + FUDGE_SECONDS;

  if (countdownSeconds > COUNTDOWN_THRESHOLD) {
    return { label: staticLabel, countdown: null };
  }

  return { label: staticLabel, countdown: { seconds: countdownSeconds, prefix } };
}

export function formatCountdownTick(value, prefix) {
  if (value <= 1) {
    return "\u23F0 Next: \uD83D\uDE80 Now!";
  }
  const m = Math.floor(value / 60);
  const s = value % 60;
  const timeLabel = m > 0 ? `${m}m ${s}s` : `${s} \uD83E\uDDE8`;
  return `\u23F0 Next: ${prefix}${timeLabel}`;
}

// --- Alpine component ----------------------------------------------------

// Not that necessary but it's fun; this whole thing could be removed with little impact
export function nextDueTimer() {
  return {
    nextDue: window.homeData.next_due,
    label: "",
    timerId: null,
    lastRefreshed: 0,

    initCountdown() {
      this.setNextDue(this.nextDue);

      // One-time fetch on first load; ensures fresh data after PWA
      // splash screen; cooldown timer ensures it's not excessive
      this.refreshFromServer();
    },

    async refreshFromServer() {
      const now = Date.now();
      if (now - this.lastRefreshed < 30 * 1000) return; // time in milliseconds
      this.lastRefreshed = now;

      try {
        const url = "/home-upcoming/" + buildNavQueryString(this.homeData.nav);
        console.log(`🔄 Refreshing next due from server ${url}`);
        const response = await fetch(url);
        const data = await response.json();

        if (data?.next_due) {
          this.setNextDue(data.next_due);
        }
        if (data?.upcoming) {
          // cloning to force reactivity, although not sure if needed
          this.homeData.upcoming = [...data.upcoming];
        }
      } catch (err) {
        console.error("❌ Failed to refresh next due from server:", err);
      }
    },

    setNextDue(data) {
      this.clearCountdown();
      this.nextDue = data;

      const resolved = resolveNextDue(data);
      this.label = resolved.label;

      if (!resolved.countdown) return;

      let value = resolved.countdown.seconds;
      const prefix = resolved.countdown.prefix;

      const tick = () => {
        if (value-- > 1) {
          this.label = formatCountdownTick(value, prefix);
          this.timerId = setTimeout(tick, 1000);
        } else {
          this.label = formatCountdownTick(0, prefix);
          this.timerId = null;

          setTimeout(() => {
            this.refreshFromServer();
          }, 10_000);
        }
      };

      tick();
    },

    clearCountdown() {
      if (this.timerId) {
        clearTimeout(this.timerId);
        this.timerId = null;
      }
    },
  };
}

if (typeof document !== "undefined") {
  document.addEventListener("alpine:init", () => {
    Alpine.store("loading", { visible: true });
    Alpine.data("homeApp", homeApp);
    Alpine.data("nextDueTimer", nextDueTimer);
  });
}

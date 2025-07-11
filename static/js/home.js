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
  };
}

// Kind of unruly but it's fun; this whole thing could be removed with little impact
export function nextDueTimer() {
  return {
    label: window.homeData.next_due,
    timerId: null,
    lastRefreshed: Date.now(),

    initCountdown() {
      this.setNextDue(this.label);

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

    setNextDue(label) {
      this.clearCountdown();
      this.label = label;

      const match = label.match(/Next: (?:(\d+)m)? ?(?:(\d+)s)?/);
      if (!match) return;

      const minutes = match[1] ? parseInt(match[1], 10) : 0;
      const seconds = match[2] ? parseInt(match[2], 10) : 0;
      let value = minutes * 60 + seconds;

      if (value === 0 || value > 5 * 60) return;

      const tick = () => {
        // console.log("⏱️ Countdown");

        if (value-- > 1) {
          const m = Math.floor(value / 60);
          const s = value % 60;
          const timeLabel = m > 0 ? `${m}m ${s}s` : `${s}  🧨`;
          this.label = `⏰ Next: ${timeLabel}`;
          this.timerId = setTimeout(tick, 1000);
        } else {
          this.label = "⏰ Next: 🚀 Now!";
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

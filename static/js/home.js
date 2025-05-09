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
      const course = this.homeData.nav.course_id;
      const chapter = this.homeData.nav.chapter_id;
      let url = "/review/random/";

      const params = [];
      if (course) params.push(`course_id=${course}`);
      if (chapter) params.push(`chapter_id=${chapter}`);
      if (params.length) url += "?" + params.join("&");

      window.location.href = url;
    },
  };
}

// Kind of unruly but it's fun
export function nextDueTimer() {
  return {
    label: window.homeData.next_due,
    timerId: null,
    lastRefreshed: Date.now(),

    initCountdown() {
      this.setNextDue(this.label);
    },

    async refreshFromServer() {
      const now = Date.now();
      // time in milliseconds
      if (now - this.lastRefreshed < 30 * 1000) {
        console.log("⏱️ Skipping nextDue refresh (cooldown active)");
        return;
      }
      this.lastRefreshed = now;

      try {
        const response = await fetch("/home-upcoming/");
        const data = await response.json();
        // console.log("✅ Upcoming data from server:", data);

        if (data?.next_due) {
          this.setNextDue(data.next_due);
        }
        if (data?.upcoming) {
          window.homeData.upcoming = data.upcoming;
          console.log("🔄  updated homeData.upcoming:", data.upcoming);
        }
      } catch (err) {
        console.error("❌ Failed to refresh next due from server:", err);
      }
    },

    setNextDue(label) {
      this.clearCountdown();
      this.label = label;
      console.log(`⏱️ setNextDue: ${label}`);

      const match = label.match(/Next: (?:(\d+)m)? ?(?:(\d+)s)?/);
      if (!match) return;

      const minutes = match[1] ? parseInt(match[1], 10) : 0;
      const seconds = match[2] ? parseInt(match[2], 10) : 0;
      let value = minutes * 60 + seconds;

      if (value === 0 || value > 5 * 60) return;

      const tick = () => {
        // console.log("🚀 Countdown");

        if (value-- > 1) {
          const m = Math.floor(value / 60);
          const s = value % 60;
          const timeLabel = m > 0 ? `${m}m ${s}s` : `${s}  🧨`;
          this.label = `⏰ Next: ${timeLabel}`;
          this.timerId = setTimeout(tick, 1000);
        } else {
          this.label = "⏰ Next: 🚀 Now!";
          this.timerId = null;
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

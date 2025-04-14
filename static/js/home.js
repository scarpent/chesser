export function homeApp() {
  return {
    homeData: homeData,

    initHome() {
      this.scrollToVariationIfNeeded();
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

    //--------------------------------------------------------------------------------
    nextDueTimer() {
      return {
        originalText: window.homeData.next_due,
        label: window.homeData.next_due,

        initCountdown() {
          const match = this.originalText.match(/Next: (?:(\d+)m)? ?(?:(\d+)s)?/);
          if (!match) return;

          const minutes = match[1] ? parseInt(match[1], 10) : 0;
          const seconds = match[2] ? parseInt(match[2], 10) : 0;

          if (minutes > 4) return;

          let value = minutes * 60 + seconds;
          if (value === 0) return;

          const tick = () => {
            if (value-- > 1) {
              const m = Math.floor(value / 60);
              const s = value % 60;
              const timeLabel = m > 0 ? `${m}m ${s}s` : `${s}  🧨`;
              this.label = `⏰ Next: ${timeLabel}`;
              setTimeout(tick, 1000);
            } else {
              this.label = "⏰ Next: 🚀 Now!";
            }
          };

          tick();
        },
      };
    },
  };
}

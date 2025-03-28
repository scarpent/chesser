export function importApp() {
  return {
    chapters: window.importData?.chapters || [],
    formDefaults: {
      ...window.importData?.form_defaults,
      next_review_date:
        window.importData?.form_defaults?.next_review_date ||
        new Date().toISOString().split("T")[0],
    },
    statusMessage: window.importData?.statusMessage || "",

    // ran into all kinds of issues restoring dropdown
    // values on errors; this reliably does the job
    init() {
      const id = window.importData?.form_defaults?.chapter_id;
      this.$nextTick(() => {
        const el = document.getElementById("chapter");
        if (el && id && el.querySelector(`option[value="${id}"]`)) {
          el.value = id;
        }
      });
    },
  };
}

export function importApp() {
  return {
    chapters: window.importData?.chapters || [],
    // en-CA is English (Canada) official format (YYYY-MM-DD)
    // this is the required html format and is widely supported
    // but not universally by all browsers
    formDefaults: {
      ...window.importData?.form_defaults,
      start_move: 2,
      next_review_date:
        window.importData?.form_defaults?.next_review_date ||
        new Date().toLocaleDateString("en-CA"),
    },

    // Alpine's x-model struggles to restore select values
    // on repop due to mismatch in value types (string vs number)
    // This ensures the correct option is selected after render
    init() {
      const id = window.importData?.form_defaults?.chapter_id;
      this.$nextTick(() => {
        const el = document.getElementById("chapter");
        if (el && id !== undefined && id !== null) {
          el.value = id;
        }
      });
    },
  };
}

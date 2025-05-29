export function importApp() {
  return {
    chapters: window.importData?.chapters || [],
    formDefaults: {
      ...window.importData?.form_defaults,
      start_move: 2,
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

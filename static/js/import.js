export function importApp() {
  return {
    importData: importData,
    quizMoveIndex: 0,

    initImport() {
      console.log("initImport()");
      console.log("importer loaded");
    },
  }; // return { ... }
}

export function homeApp() {
  return {
    homeData: homeData,
    quizMoveIndex: 0,

    initHome() {
      console.log("initHome()");
      console.log("Home loaded");
    },
  }; // return { ... }
}

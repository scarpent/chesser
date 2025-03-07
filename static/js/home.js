export function homeApp() {
  return {
    homeData: homeData,

    initHome() {
      console.log("initHome()");
      console.log("Home loaded");
    },
  }; // return { ... }
}

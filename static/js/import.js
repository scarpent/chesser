export function importApp() {
  return {
    importData: importData,
    quizMoveIndex: 0,

    initImport() {
      const urlParams = new URLSearchParams(window.location.search);
      console.log("urlParams", urlParams);
      this.statusMessage = urlParams.get("status") || "";
    },
  }; // return { ... }
}

// Global handler to update chapter dropdown based on course
document.addEventListener("DOMContentLoaded", () => {
  const courseSelect = document.getElementById("course");
  const chapterSelect = document.getElementById("chapter");

  const courseChapterData = window.importData.chapters || {};

  function populateCourses() {
    courseSelect.innerHTML = "";
    Object.keys(courseChapterData).forEach((courseTitle) => {
      const option = document.createElement("option");
      option.value = courseTitle;
      option.textContent = courseTitle;
      courseSelect.appendChild(option);
    });
  }

  function populateChapters(courseId) {
    chapterSelect.innerHTML = "";
    const chapters = courseChapterData[courseId] || [];
    chapters.forEach((title) => {
      const option = document.createElement("option");
      option.value = title;
      option.textContent = title;
      chapterSelect.appendChild(option);
    });
  }

  populateCourses();

  courseSelect.addEventListener("change", () => {
    populateChapters(courseSelect.value);
  });

  if (courseSelect.value) {
    populateChapters(courseSelect.value);
  }

  const nextReviewInput = document.getElementById("next_review_date");

  if (nextReviewInput && !nextReviewInput.value) {
    const today = new Date();
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, "0");
    const dd = String(today.getDate()).padStart(2, "0");
    nextReviewInput.value = `${yyyy}-${mm}-${dd}`;
  }
});

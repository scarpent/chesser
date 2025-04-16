document.addEventListener("DOMContentLoaded", () => {
  const boardContainer = document.getElementById("resizable-board");
  const resizeHandle = document.getElementById("resize-handle");
  const boardId = boardContainer?.dataset.boardId || "default";
  const STORAGE_KEY = `resizableBoardWidth-${boardId}`;

  const savedWidth = localStorage.getItem(STORAGE_KEY);
  let boardSizeToUse;
  if (savedWidth) {
    const savedWidthPx = parseInt(savedWidth.replace("px", ""), 10);
    const maxBoardSize = Math.min(window.innerWidth, window.innerHeight) - 50;
    // Round to nearest lower multiple of 8 to match square grid
    boardSizeToUse = Math.floor(Math.min(savedWidthPx, maxBoardSize) / 8) * 8;
  } else {
    boardSizeToUse = 400; // fallback
  }

  boardContainer.style.width = `${boardSizeToUse}px`;
  boardContainer.style.height = `${boardSizeToUse}px`;

  resizeHandle.addEventListener("mousedown", (e) => {
    e.preventDefault();

    resizeHandle.classList.add("drag-active");

    const startX = e.clientX;
    const startWidth = boardContainer.offsetWidth;

    function resize(e) {
      const newWidth = Math.max(300, startWidth + (e.clientX - startX));
      boardContainer.style.width = `${newWidth}px`;
      boardContainer.style.height = `${newWidth}px`;

      localStorage.setItem(STORAGE_KEY, `${newWidth}px`);

      const boardEl = document.getElementById("board");
      if (boardEl?.cg?.redraw) {
        boardEl.cg.redraw();
      }
    }

    function stopResize() {
      document.removeEventListener("mousemove", resize);
      document.removeEventListener("mouseup", stopResize);
      resizeHandle.classList.remove("drag-active");
    }

    document.addEventListener("mousemove", resize);
    document.addEventListener("mouseup", stopResize);
  });
});

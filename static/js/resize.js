const STORAGE_KEY = "resizableBoardWidth-quiz"; // Eventually make this dynamic

document.addEventListener("DOMContentLoaded", () => {
  const boardContainer = document.getElementById("resizable-board");
  const resizeHandle = document.getElementById("resize-handle");
  const STORAGE_KEY = "resizableBoardWidth-quiz";

  // Restore saved size
  const savedWidth = localStorage.getItem(STORAGE_KEY);
  if (savedWidth) {
    const savedWidthPx = parseInt(savedWidth.replace("px", ""), 10);
    const maxBoardSize = Math.min(window.innerWidth, window.innerHeight) - 50;
    const boardSizeToUse = Math.min(savedWidthPx, maxBoardSize);

    boardContainer.style.width = `${boardSizeToUse}px`;
    boardContainer.style.height = `${boardSizeToUse}px`;
  }

  // Resize handler
  resizeHandle.addEventListener("mousedown", (e) => {
    e.preventDefault();

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
    }

    document.addEventListener("mousemove", resize);
    document.addEventListener("mouseup", stopResize);
  });
});

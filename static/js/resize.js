document.addEventListener("DOMContentLoaded", () => {
  const boardContainer = document.getElementById("resizable-board");
  const resizeHandle = document.getElementById("resize-handle");

  // Restore saved size
  const savedWidth = localStorage.getItem("resizableBoardWidth");
  if (savedWidth) {
    boardContainer.style.width = savedWidth;
    boardContainer.style.height = savedWidth; // square
  }

  resizeHandle.addEventListener("mousedown", (e) => {
    e.preventDefault();

    const startX = e.clientX;
    const startWidth = boardContainer.offsetWidth;

    function resize(e) {
      const newWidth = Math.max(300, startWidth + (e.clientX - startX)); // Minimum width 300px
      const newHeight = newWidth; // Keep square shape
      boardContainer.style.width = `${newWidth}px`;
      boardContainer.style.height = `${newHeight}px`;

      // Save new size to localStorage
      localStorage.setItem("resizableBoardWidth", `${newWidth}px`);

      if (window.chessgroundBoard) {
        window.chessgroundBoard.redraw();
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

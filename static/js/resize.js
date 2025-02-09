document.addEventListener("DOMContentLoaded", () => {
  const boardContainer = document.getElementById("resizable-board");
  const resizeHandle = document.getElementById("resize-handle");

  resizeHandle.addEventListener("mousedown", (e) => {
    e.preventDefault();

    const startX = e.clientX;
    const startY = e.clientY;
    const startWidth = boardContainer.offsetWidth;
    const startHeight = boardContainer.offsetHeight;

    function resize(e) {
      const newWidth = Math.max(300, startWidth + (e.clientX - startX)); // Minimum width 300px
      const newHeight = newWidth; // Keep square shape
      boardContainer.style.width = `${newWidth}px`;
      boardContainer.style.height = `${newHeight}px`;
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

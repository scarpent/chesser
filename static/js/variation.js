import { Chessground } from "https://cdn.jsdelivr.net/npm/chessground@9.1.1/dist/chessground.min.js";
import { Chess } from "https://cdn.jsdelivr.net/npm/chess.js@1.0.0/dist/esm/chess.js";

window.Chessground = Chessground;
window.Chess = Chess;

export function variationApp() {
  return {
    board: null,
    chess: null,
    variationData: variationData,
    mainlineMoveIndex: 0,
    subvarMoveIndex: -1,

    initVariation() {
      console.log("initVariation()");
      const boardElement = document.getElementById("board");
      if (boardElement && window.Chessground && window.Chess) {
        this.chess = new window.Chess();

        this.goToStartingPosition();
        this.board = window.Chessground(boardElement, {
          viewOnly: true,
          highlight: { lastMove: true, check: true },
          orientation: this.variationData.color,
          fen: this.chess.fen(),
          coordinates: false,
          movable: {
            color: "both",
            free: false, // Only legal moves
            showDests: false,
          },
        });
        this.updateBoard();
        setTimeout(() => {
          // Wait for alpine.js to process dynamic html
          this.highlightMainlineMove();
          this.attachClickHandlers(); // To moves
        }, 100);
        console.log("Chess board loaded");
      } else {
        console.error("chessground or chess.js failed to load");
      }
    }, // initVariation()

    goToStartingPosition() {
      // Show the state before our first move
      this.mainlineMoveIndex = this.variationData.start_index - 1;
      if (this.mainlineMoveIndex >= 0) {
        for (let i = 0; i <= this.mainlineMoveIndex; i++)
          this.chess.move(this.variationData.moves[i].san);
      }
    },

    //--------------------------------------------------------------------------------
    drawShapes() {
      const shapes =
        this.mainlineMoveIndex >= 0
          ? this.variationData.moves[this.mainlineMoveIndex].shapes || "[]"
          : "[]";

      this.board.set({ drawable: { shapes: JSON.parse(shapes) } });
    },

    //--------------------------------------------------------------------------------
    nextMainlineMove() {
      if (this.mainlineMoveIndex < this.variationData.moves.length - 1) {
        this.exitSubvariation();
        this.chess.move(this.variationData.moves[++this.mainlineMoveIndex].san);
        this.updateBoard();
      }
    },

    //--------------------------------------------------------------------------------
    previousMainlineMove() {
      if (this.isInSubvariation()) {
        // We're already on the move we want to be at, so
        // we'll just exit subvar and update the board
        this.exitSubvariation();
      } else if (this.mainlineMoveIndex > 0) {
        this.chess.undo();
        this.mainlineMoveIndex--;
      } else {
        this.mainlineMoveIndex = -1; // Ensure forward nav works correctly
        this.chess.reset();
      }
      this.updateBoard();
    },

    //--------------------------------------------------------------------------------
    updateBoard() {
      this.board.set({
        fen: this.chess.fen(),
        drawable: {
          shapes:
            this.mainlineMoveIndex >= 0
              ? JSON.parse(
                  this.variationData.moves[this.mainlineMoveIndex].shapes || "[]"
                )
              : [],
        },
      });

      this.highlightMainlineMove();
    },

    //--------------------------------------------------------------------------------
    highlightMainlineMove() {
      document
        .querySelectorAll(".mainline-move.highlight")
        .forEach((el) => el.classList.remove("highlight"));

      const mainlineMoveElement = document.querySelector(
        `.mainline-move[data-index="${this.mainlineMoveIndex}"]`
      );
      if (mainlineMoveElement) {
        mainlineMoveElement.classList.add("highlight");
        this.scrollIntoView(mainlineMoveElement);
      }
      this.removeSubvarHighlights();
    },

    //--------------------------------------------------------------------------------
    nextSubvarMove() {
      const subvarMoves = this.getSubvarMoves();
      if (subvarMoves.length === 0) {
        this.nextMainlineMove();
        return;
      }

      if (!this.isInSubvariation()) {
        this.subvarMoveIndex = 0; // Enter subvariation
      } else if (this.subvarMoveIndex < subvarMoves.length - 1) {
        this.subvarMoveIndex++;
      } else {
        this.exitSubvariation();
        this.nextMainlineMove();
        return;
      }
      this.updateBoardForSubvar(subvarMoves[this.subvarMoveIndex]);
    },

    //--------------------------------------------------------------------------------
    previousSubvarMove() {
      const subvarMoves = this.getSubvarMoves();

      if (!this.isInSubvariation()) {
        this.previousMainlineMove();

        // See if previous mainline move has subvariation(s)
        const prevSubvarMoves = this.getSubvarMoves();
        if (prevSubvarMoves.length) {
          // Enter the last subvar move of the previous mainline move
          this.subvarMoveIndex = prevSubvarMoves.length - 1;
          this.updateBoardForSubvar(prevSubvarMoves[this.subvarMoveIndex]);
        }
        return;
      }

      if (this.subvarMoveIndex > 0) {
        this.subvarMoveIndex--; // Move up within the subvar list
      } else {
        this.exitSubvariation(); // Return to parent mainline move
        this.updateBoard(); // Ensure correct board and highlight update
      }

      if (this.isInSubvariation()) {
        this.updateBoardForSubvar(subvarMoves[this.subvarMoveIndex]);
      }
    },

    selectClickedSubvarMove(moveElement) {
      // Ensure we're inside a subvariations container and
      // get the parent mainline move index
      const subvarContainer = moveElement.closest(".subvariations");
      if (!subvarContainer) return;

      const parentMainlineIndex = parseInt(subvarContainer.dataset.mainlineIndex, 10);
      if (!isNaN(parentMainlineIndex)) {
        this.jumpToMainlineMove(parentMainlineIndex);
      }

      const subvarMoves = this.getSubvarMoves();
      const clickedIndex = subvarMoves.indexOf(moveElement);

      if (clickedIndex !== -1) {
        this.subvarMoveIndex = clickedIndex;
        this.updateBoardForSubvar(moveElement);
      }
    },

    //--------------------------------------------------------------------------------
    updateBoardForSubvar(moveElement) {
      // Sets scrolling and removes subvar highlights
      // (subvar scrolling and scrolling in general needs work)
      this.highlightMainlineMove();

      if (moveElement) {
        moveElement.classList.add("highlight");

        // Set board position from the move's FEN
        const fen = moveElement.dataset.fen;
        this.board.set({ fen: fen, drawable: { shapes: [] } }); // Clear shapes
      }
    },

    //--------------------------------------------------------------------------------
    removeSubvarHighlights() {
      document
        .querySelectorAll(".subvar-move.highlight")
        .forEach((el) => el.classList.remove("highlight"));
    },

    //--------------------------------------------------------------------------------
    getSubvarMoves() {
      if (this.mainlineMoveIndex < 0) return [];
      return Array.from(
        document.querySelectorAll(
          `.subvariations[data-mainline-index="${this.mainlineMoveIndex}"] .subvar-move`
        )
      );
    },

    //
    isInSubvariation() {
      return this.subvarMoveIndex !== -1;
    },

    exitSubvariation() {
      this.subvarMoveIndex = -1;
    },

    //--------------------------------------------------------------------------------
    attachClickHandlers() {
      document.querySelectorAll(".mainline-move, .subvar-move").forEach((move) => {
        move.style.cursor = "pointer";
        move.addEventListener("click", this.handleMoveClick.bind(this));
      });
    },

    //--------------------------------------------------------------------------------
    jumpToMainlineMove(index) {
      if (index < 0 || index >= this.variationData.moves.length) return;
      this.chess.reset();
      for (let i = 0; i <= index; i++) {
        this.chess.move(this.variationData.moves[i].san);
      }
      this.mainlineMoveIndex = index;
      this.updateBoard();
    },

    //--------------------------------------------------------------------------------
    handleMoveClick(event) {
      const moveElement = event.target;

      if (moveElement.classList.contains("mainline-move")) {
        this.jumpToMainlineMove(parseInt(moveElement.dataset.index, 10));
      } else if (moveElement.classList.contains("subvar-move")) {
        this.selectClickedSubvarMove(moveElement);
      }
    },

    //--------------------------------------------------------------------------------
    handleKeyNavigation(event) {
      if (event.key === "ArrowLeft") {
        this.previousMainlineMove();
      } else if (event.key === "ArrowRight") {
        this.nextMainlineMove();
      } else if (event.key === "ArrowUp") {
        this.previousSubvarMove();
      } else if (event.key === "ArrowDown") {
        this.nextSubvarMove();
      }
    },

    scrollIntoView(element) {
      if (element) {
        const container = document.getElementById("variation-text");
        const offset = 20; // Margin from the top
        const elementTop =
          element.getBoundingClientRect().top + container.scrollTop - offset;

        container.scrollTo({
          top: elementTop,
          behavior: "smooth",
        });
      }
    },
  }; // return { ... }
}

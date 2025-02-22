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
        this.chess.move(this.variationData.moves[++this.mainlineMoveIndex].san);
        this.updateBoard();
      }
    },

    //--------------------------------------------------------------------------------
    previousMainlineMove() {
      if (this.mainlineMoveIndex <= 0) {
        this.mainlineMoveIndex = -1; // Ensure forward navigation works correctly
        this.chess.reset();
      } else {
        this.chess.undo();
        this.mainlineMoveIndex--;
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
      }
      this.removeSubvarHighlights();
    },

    //--------------------------------------------------------------------------------
    nextSubvarMove() {
      const subvarMoves = this.getSubvarMoves();
      if (subvarMoves.length === 0) {
        // No subvariations, move to next mainline move
        this.nextMainlineMove();
        return;
      }

      if (this.subvarMoveIndex === null) {
        // Enter subvariation
        this.subvarMoveIndex = 0;
      } else if (this.subvarMoveIndex < subvarMoves.length - 1) {
        // Move forward in subvariation
        this.subvarMoveIndex++;
      } else {
        // End of subvariations, move to next mainline move
        this.subvarMoveIndex = null;
        this.nextMainlineMove();
        return;
      }

      // Highlight & update board
      this.updateBoardForSubvar(subvarMoves[this.subvarMoveIndex]);
    },

    //--------------------------------------------------------------------------------
    previousSubvarMove() {
      const subvarMoves = this.getSubvarMoves();

      if (this.subvarMoveIndex === null) {
        // We are in the mainline → check if the previous mainline move has subvariations
        this.previousMainlineMove();

        // Get the new subvar moves of the previous mainline move
        const prevSubvarMoves = this.getSubvarMoves();
        if (prevSubvarMoves.length > 0) {
          // Enter the last subvar move of the previous mainline move
          this.subvarMoveIndex = prevSubvarMoves.length - 1;
          this.updateBoardForSubvar(prevSubvarMoves[this.subvarMoveIndex]);
        }
        return;
      }

      if (this.subvarMoveIndex > 0) {
        // Move up within the subvariation list
        this.subvarMoveIndex--;
      } else {
        // At first subvar move, return to parent mainline move
        this.subvarMoveIndex = null;
        this.updateBoard(); // Ensure correct board and highlight update
      }

      // Highlight & update board with new subvariation move
      if (this.subvarMoveIndex !== null) {
        this.updateBoardForSubvar(subvarMoves[this.subvarMoveIndex]);
      }
    },

    //--------------------------------------------------------------------------------
    updateBoardForSubvar(moveElement) {
      this.removeSubvarHighlights();

      if (moveElement) {
        moveElement.classList.add("highlight");
      }

      // Set the board position from the subvar move
      let fen = moveElement.dataset.fen;
      this.board.set({ fen: fen, drawable: { shapes: [] } }); // Clear shapes
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
  }; // return { ... }
}

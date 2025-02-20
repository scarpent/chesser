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
        this.drawShapes();
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
      if (this.mainlineMoveIndex >= this.variationData.moves.length - 1) return;
      this.mainlineMoveIndex++;
      this.chess.move(this.variationData.moves[this.mainlineMoveIndex].san);
      this.board.set({ fen: this.chess.fen() });
      this.drawShapes();
    },

    //--------------------------------------------------------------------------------
    previousMainlineMove() {
      if (this.mainlineMoveIndex === 0) {
        // we're on the first move and going back to the starting position
        this.mainlineMoveIndex--; // so that going forward will work properly
        this.chess.reset();
        this.board.set({
          fen: this.chess.fen(),
          drawable: { shapes: [] },
        });
      } else if (this.mainlineMoveIndex > 0) {
        this.chess.undo();
        this.mainlineMoveIndex--;
        this.board.set({ fen: this.chess.fen() });
        this.drawShapes();
      }
    },
  }; // return { ... }
}

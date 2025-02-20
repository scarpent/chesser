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

        if (!this.variationData || Object.keys(this.variationData).length === 0) {
          this.nothingToSeeHere(boardElement);
          return;
        }

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
      this.mainlineMoveIndex = this.variationData.start_index;
      if (this.variationData.start_index >= 0) {
        for (let i = 0; i <= this.variationData.start_index; i++)
          this.chess.move(this.variationData.moves[i].san);
      }
    },

    //--------------------------------------------------------------------------------
    noMoreMoves() {
      return this.mainlineMoveIndex >= this.variationData.moves.length;
    },

    //--------------------------------------------------------------------------------
    drawShapes() {
      const shapes = this.variationData.moves[this.mainlineMoveIndex].shapes;
      if (!shapes) return;
      this.board.set({
        drawable: { shapes: JSON.parse(shapes) },
      });
    },

    //--------------------------------------------------------------------------------
    nextMainlineMove() {
      if (this.noMoreMoves()) return;
      this.mainlineMoveIndex++;
      this.chess.move(this.variationData.moves[this.mainlineMoveIndex].san);
      this.board.set({ fen: this.chess.fen() });
      this.drawShapes();
    },

    //--------------------------------------------------------------------------------
    previousMainlineMove() {
      if (this.mainlineMoveIndex <= 0) return;
      this.chess.undo();
      this.mainlineMoveIndex--;
      this.board.set({ fen: this.chess.fen() });
      this.drawShapes();
    },

    //--------------------------------------------------------------------------------
    gotoPreviousMove() {
      this.moveIndex = this.mainlineMoveIndex - 2;
      this.chess.undo();
      this.chess.undo();
      this.board.set({
        fen: this.chess.fen(),
        movable: { dests: this.toDests() },
      });
    },

    //--------------------------------------------------------------------------------
    nothingToSeeHere(boardElement) {
      console.log("no variation data");
      this.status = "😌";
      this.board = window.Chessground(boardElement, {
        viewOnly: true,
        orientation: "white",
        fen: this.chess.fen(),
        coordinates: false,
      });
    },
  }; // return { ... }
}

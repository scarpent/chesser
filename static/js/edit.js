import { Chessground } from "https://cdn.jsdelivr.net/npm/chessground@9.1.1/dist/chessground.min.js";
import { Chess } from "https://cdn.jsdelivr.net/npm/chess.js@1.0.0/dist/esm/chess.js";

window.Chessground = Chessground;
window.Chess = Chess;

export function editApp() {
  return {
    board: null,
    chess: null,
    course: "Course ➤",
    chapter: "Chapter Name ➤",
    variationTitle: "Variation Title",
    variationMoves: "1.e4 e5 2.Nf3 Nc6 3.d4 exd4 4.Nxd4 Nf6 5.Nxc6 bxc6",
    variationData: variationData,

    initEditor() {
      console.log("initEditor()");
      const boardElement = document.getElementById("edit-board");
      if (boardElement && window.Chessground && window.Chess) {
        this.chess = new window.Chess();
        this.board = window.Chessground(boardElement, {
          viewOnly: false,
          draggable: false,
          orientation: this.variationData.color,
          fen: this.chess.fen(),
          coordinates: false,
          movable: {
            free: false, // only legal moves (no moves because no dests)
            showDests: false,
          },
        });
        console.log("editor loaded");
      } else {
        console.error("chessground or chess.js failed to load");
      }
    }, // initEditor()
  }; // return { ... }
}

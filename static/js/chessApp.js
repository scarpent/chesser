import { Chessground } from "https://cdn.jsdelivr.net/npm/chessground@9.1.1/dist/chessground.min.js";
import { Chess } from "https://cdn.jsdelivr.net/npm/chess.js@1.0.0/dist/esm/chess.js";

window.Chessground = Chessground;
window.Chess = Chess;

export function chessApp() {
  return {
    board: null,
    chess: null,
    status: "Ready",
    initChessground() {
      const boardElement = document.getElementById("board");
      if (boardElement && window.Chessground && window.Chess) {
        this.chess = new window.Chess();

        this.board = window.Chessground(boardElement, {
          viewOnly: false,
          draggable: true,
          highlight: {
            lastMove: true,
            check: true,
          },
          orientation: "black",
          movable: {
            color: "both", // Allow both white and black to move
            free: true, // Any moves
            showDests: false,
          },
        });

        this.status = "Chessboard Loaded!";
      } else {
        console.error("Chessground or Chess.js failed to load");
      }
    },
  };
}

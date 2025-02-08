import { Chessground } from "https://cdn.jsdelivr.net/npm/chessground@9.1.1/dist/chessground.min.js";
import { Chess } from "https://cdn.jsdelivr.net/npm/chess.js@1.0.0/dist/esm/chess.js";

window.Chessground = Chessground;
window.Chess = Chess;

export function quizApp() {
  return {
    board: null,
    chess: null,
    status: "Ready",
    quizData: quizData,

    initChessground() {
      const boardElement = document.getElementById("board");
      if (boardElement && window.Chessground && window.Chess) {
        this.chess = new window.Chess();

        const first = this.quizData.moves[this.quizData.start]
        console.log(first.fen, first.move)

        this.chess.load(first.fen);
        this.board = window.Chessground(boardElement, {
          viewOnly: false,
          draggable: true,
          highlight: {
            lastMove: true,
            check: true,
          },
          orientation: this.quizData.color,
          fen: first.fen,
          movable: {
            color: "both", // Allow both white and black to move
            free: false, // Only legal moves
            dests: this.toDests(),
            showDests: false,
            events: {
              after: this.handleMove.bind(this),
            },
          },
        });

        this.status = "Chessboard loaded!";
      } else {
        console.error("Chessground or chess.js failed to load");
      }
    },
    toDests() {
      const dests = new Map();
      const squares =
        this.chess.SQUARES ||
        this.chess
          .board()
          .flatMap((row) =>
            row.map((square) => (square ? square.square : null))
          )
          .filter(Boolean);
      squares.forEach((s) => {
        const ms = this.chess.moves({ square: s, verbose: true });
        if (ms.length)
          dests.set(
            s,
            ms.map((m) => m.to)
          );
      });
      return dests;
    },
    handleMove(orig, dest) {
      const move = this.chess.move({ from: orig, to: dest });
      if (move) {
        this.status = `Moved from ${orig} to ${dest}`;
        this.board.set({
          fen: this.chess.fen(),
          movable: {
            dests: this.toDests(),
          },
        });

        // this.checkQuizMove(this.chess.fen());
      } else {  // this won't happen because of "free: false"
        this.status = `Illegal move from ${orig} to ${dest}`;
      }
    },
  };
}

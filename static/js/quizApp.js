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
    quizMoveIndex: 0,

    initChessground() {
      const boardElement = document.getElementById("board");
      if (boardElement && window.Chessground && window.Chess) {
        this.chess = new window.Chess();

        const first = this.quizData.moves[this.quizData.start]
        console.log(first.fen, first.move)

        this.chess.load(first.fen);
        this.board = window.Chessground(boardElement, {
          viewOnly: false,
          draggable: false,
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

        console.log("Chess board loaded in initChessground()");

        this.startQuiz();


      } else {
        console.error("Chessground or chess.js failed to load");
      }
    }, // initChessground()

    //--------------------------------------------------------------------------------

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

    //--------------------------------------------------------------------------------

    handleMove(orig, dest) {
      const move = this.chess.move({ from: orig, to: dest });
      if (move) {
        this.board.set({
          fen: this.chess.fen(),
          movable: {
            dests: this.toDests(),
          },
        });
        console.log(`Moved from ${orig} to ${dest}`);
        // this.checkQuizMove(this.chess.fen());
      } else {  // this won't happen because of "free: false"
        this.status = `Illegal move from ${orig} to ${dest}`;
      }
    },

    //--------------------------------------------------------------------------------

    startQuiz() {
      console.log("starting the quiz...");
      this.quizMoveIndex = this.quizData.start + 1;
      this.playOpposingMove(this.quizMoveIndex);
    },

    //--------------------------------------------------------------------------------

    playOpposingMove(index) {
      setTimeout(() => {
        const sanMove = this.quizData.moves[index].move;
        const move = this.chess.move(sanMove);
        if (move) {
          this.board.set({
            fen: this.chess.fen(),
            movable: {
              dests: this.toDests(),
            },
            lastMove: [move.from, move.to],
          });
          console.log(`Opposing move: ${sanMove} ➤ ${this.chess.fen()}`);
        } else {  // this would be an error with the variation setup
          console.error("Invalid opposing move: " + sanMove);
        }
      }, 1000) // 1-second delay
    },

    //--------------------------------------------------------------------------------


  }  // return { ... }
};

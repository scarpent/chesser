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
          draggable: false,  // true is no different? (only want to click anyway)
          highlight: {
            lastMove: true,
            check: true,
          },
          orientation: this.quizData.color,
          fen: first.fen,
          movable: {
            color: "both", // allow both white and black to move
            free: false, // only legal moves
            dests: this.toDests(),
            showDests: false,
            events: {
              after: this.handleMove.bind(this),
            },
          },
        });
        console.log("Chess board loaded in initChessground()");

        this.playOpposingMove();

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
        this.checkQuizMove();
      } else {  // this won't happen because of "free: false"
        this.status = `Illegal move from ${orig} to ${dest}`;
      }
    },

    //--------------------------------------------------------------------------------
    playOpposingMove() {
      setTimeout(() => {
        this.quizMoveIndex++;
        if (this.quizMoveIndex >= this.quizData.moves.length
          || this.quizMoveIndex >= this.quizData.end) {
          this.completeQuiz();
          return;
        }
        const sanMove = this.quizData.moves[this.quizMoveIndex].move;
        const move = this.chess.move(sanMove);
        if (move) {
          this.board.set({
            fen: this.chess.fen(),
            movable: {
              dests: this.toDests(),
            },
            lastMove: [move.from, move.to],
          });
          console.log(`Opposing move (qi: ${this.quizMoveIndex}): ${sanMove} ➤ ${this.chess.fen()}`);
          this.quizMoveIndex++;
        } else {  // this would be an error with the variation setup
          console.error("Invalid opposing move: " + sanMove);
        }
      }, 250) // 0.25 second delay
      // (later: maybe 1 second for first move? shorter for subsequent?)
    },

    //--------------------------------------------------------------------------------
    checkQuizMove() {
      if (this.quizMoveIndex < this.quizData.moves.length) {
        const correct = this.quizData.moves[this.quizMoveIndex];
        const altMoves = Object.keys(correct.alt).length > 0
          ? ` (alt: ${Object.keys(correct.alt).join(", ")}`
          : "";

        if (this.chess.fen() === correct.fen) {
          console.log(`Correct move: ${correct.move}${altMoves})`);
          this.playOpposingMove();
        } else {
          console.error("Incorrect move");
        }
      } else {
        this.completeQuiz();
      }
    },

    //--------------------------------------------------------------------------------
    completeQuiz() {
      console.log("Quiz completed!");
    }

  }  // return { ... }
};

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

        const quizMove = this.quizData.moves[this.quizData.start]
        console.log(quizMove.san)

        this.chess.move(quizMove.san);
        this.board = window.Chessground(boardElement, {
          viewOnly: false,
          draggable: false,  // true is no different? (only want to click anyway)
          highlight: {
            lastMove: true,
            check: true,
          },
          orientation: this.quizData.color,
          fen: this.chess.fen(),
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
        console.log(`Moved from ${orig} to ${dest} (${move.san})`);
        this.checkQuizMove(move.san);
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
        const sanMove = this.quizData.moves[this.quizMoveIndex].san;
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
          console.log(`Invalid opposing move: ${sanMove}`);
        }
      }, 250) // 0.25 second delay
      // (later: maybe 1 second for first move? shorter for subsequent?)
    },

    //--------------------------------------------------------------------------------
    checkQuizMove(sanMove) {
      if (this.quizMoveIndex < this.quizData.moves.length) {
        const correct = this.quizData.moves[this.quizMoveIndex];
        const altMoves = Object.keys(correct.alt).length > 0
          ? ` (alt: ${Object.keys(correct.alt).join(", ")}`
          : "";

        console.log(`Checking move ${this.quizMoveIndex}: ${sanMove} against ${correct.san}`);
        if (sanMove === correct.san) {
          console.log(`Correct move: ${correct.san}${altMoves})`);
          this.playOpposingMove();
        } else {
          console.log("Incorrect move");
          this.gotoPreviousMove();
        }
      } else {
        this.completeQuiz();
      }
    },

    //--------------------------------------------------------------------------------
    gotoPreviousMove() {
      // TODO: maybe should havae a boundary check here? 🤷
      this.quizMoveIndex = this.quizMoveIndex - 2;
      this.chess.undo();
      this.chess.undo();
      this.board.set({
        fen: this.chess.fen(),
        movable: {
          dests: this.toDests(),
        },
      });
      this.playOpposingMove();
    },

    //--------------------------------------------------------------------------------
    completeQuiz() {
      console.log("Quiz completed!");
    }

  }  // return { ... }
};

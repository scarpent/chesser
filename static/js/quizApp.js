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
    failed: false, // we'll report failure back to the server, but it can be reset
    completed: false, // finished the quiz and now we'll make user go through it again
    reviewAfterFailure: false, // when true, disallow restart and clearing the failure

    initChessground() {
      console.log("initChessground()");
      const boardElement = document.getElementById("board");
      if (boardElement && window.Chessground && window.Chess) {
        this.chess = new window.Chess();

        this.goToStartingPosition();
        this.board = window.Chessground(boardElement, {
          viewOnly: false,
          draggable: false, // true is no different? (only want to click anyway)
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
        console.log("chess board loaded");

        this.playOpposingMove();
      } else {
        console.error("chessground or chess.js failed to load");
      }
    }, // initChessground()

    goToStartingPosition() {
      this.status = "🟣🟣";
      this.quizMoveIndex = this.quizData.start;
      if (this.quizData.start >= 0) {
        for (let i = 0; i <= this.quizData.start; i++) {
          const move = this.quizData.moves[i];
          this.chess.move(move.san);
        }
      }
    },

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
        // console.log(`moved from ${orig} to ${dest} (${move.san})`);
        this.checkQuizMove(move);
      } else {
        // this shouldn't happen, because of "free: false"
        this.status = `illegal move from ${orig} to ${dest}`;
      }
    },

    //--------------------------------------------------------------------------------
    playOpposingMove() {
      setTimeout(() => {
        this.quizMoveIndex++;
        if (
          // TODO: make sure this logic is correct
          this.quizMoveIndex >= this.quizData.moves.length ||
          this.quizMoveIndex >= this.quizData.end
        ) {
          this.completeQuiz();
          return;
        }
        const san = this.quizData.moves[this.quizMoveIndex].san;
        const move = this.chess.move(san);
        if (move) {
          this.board.set({
            fen: this.chess.fen(),
            movable: {
              dests: this.toDests(),
            },
            lastMove: [move.from, move.to],
          });
          this.quizMoveIndex++;
        } else {
          // this would be an error with the variation setup
          console.log(`invalid opposing move: ${san}`);
        }
      }, 250); // 0.25 second delay
      // (later: maybe 1 second for first move? shorter for subsequent?)
    },

    //--------------------------------------------------------------------------------
    checkQuizMove(move) {
      if (this.quizMoveIndex >= this.quizData.moves.length) {
        this.completeQuiz();
        return;
      }

      const answer = this.quizData.moves[this.quizMoveIndex];

      // console.log(`checking move ${this.quizMoveIndex}: ${move.san} against ${answer.san} (alt: ${answer.alt}, alt_fail: ${answer.alt_fail})`);

      // TODO: decide what to do with handling alt/wrong moves:
      // delays, buttons, etc (annotations probably in variation view)

      if (move.san === answer.san) {
        this.status = "🟢🟣";
        this.playOpposingMove();
      } else if (answer.alt.includes(move.san)) {
        this.status = "🟢🟡";
        this.annotateMissedMove(move.from, move.to, "green", "yellow");
      } else if (answer.alt_fail.includes(move.san)) {
        this.status = "🟢🔴";
        this.annotateMissedMove(move.from, move.to, "green", "red");
        this.failed = true;
      } else {
        this.status = "🔴🔴";
        this.annotateMissedMove(move.from, move.to, "red", "red");
        this.failed = true;
      }
    },

    //--------------------------------------------------------------------------------
    showQuizMove() {
      if (this.quizMoveIndex > this.quizData.end) {
        this.status = "🤷 no more moves to show 💣️";
        return;
      }
      const san = this.quizData.moves[this.quizMoveIndex].san;
      const move = this.chess.move(san);
      if (move) {
        this.failed = true;
        this.annotateMove(move.from, move.to, "blue", "blue");
        this.chess.undo();
      } else {
        // this shouldn't happen if the quiz is set up correctly
        this.status = `invalid move: ${san}`;
      }
      // TODO: report this to the server as a failure
    },

    //--------------------------------------------------------------------------------
    annotateMove(from, to, arrowColor, circleColor) {
      this.board.set({
        drawable: {
          shapes: [
            { orig: to, brush: circleColor, piece: "circle" },
            { orig: from, dest: to, brush: arrowColor, piece: "arrow" },
          ],
        },
      });
    },

    //--------------------------------------------------------------------------------
    annotateMissedMove(from, to, arrowColor, circleColor) {
      this.annotateMove(from, to, arrowColor, circleColor);
      setTimeout(() => {
        this.gotoPreviousMove();
      }, 1000);
    },

    //--------------------------------------------------------------------------------
    gotoPreviousMove() {
      // TODO: maybe should have a boundary check here? 🤷
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
      this.completed = true;
      if (this.failed) {
        this.status = "❌";
        // TODO: report failure to server and review again
        // to see if we actually learned anything
      } else {
        this.status = "✅";
      }
    },

    //--------------------------------------------------------------------------------
    restartQuiz() {
      // TODO: a bunch of logic about when you can and can't restart
      // and if things get reported to the server or not

      this.failed = false;
      this.chess.reset();
      this.goToStartingPosition();
      this.board.set({
        fen: this.chess.fen(),
        movable: {
          dests: this.toDests(),
        },
      });
      this.playOpposingMove();
    },

    //--------------------------------------------------------------------------------
    analysisBoard() {
      const fen = this.chess.fen().replace(/ /g, "_");
      const url = `https://lichess.org/analysis/standard/${fen}`;
      window.open(url, "_blank");
    },
  }; // return { ... }
}

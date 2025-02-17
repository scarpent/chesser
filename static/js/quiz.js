import { Chessground } from "https://cdn.jsdelivr.net/npm/chessground@9.1.1/dist/chessground.min.js";
import { Chess } from "https://cdn.jsdelivr.net/npm/chess.js@1.0.0/dist/esm/chess.js";

window.Chessground = Chessground;
window.Chess = Chess;

export function quizApp() {
  return {
    board: null,
    chess: null,
    status: "⚪️⚪️",
    variationData: variationData,
    quizMoveIndex: 0,
    failed: false, // we'll report failure back to the server (can reset before finish)
    completed: false, // finished the quiz! if failed we'll review again
    reviewAfterFailure: false, // if true: disallow restart and clearing the failure

    initChessground() {
      console.log("initChessground()");
      const boardElement = document.getElementById("board");
      if (boardElement && window.Chessground && window.Chess) {
        this.chess = new window.Chess();

        if (!this.variationData || Object.keys(this.variationData).length === 0) {
          this.nothingToSeeHere(boardElement);
          return;
        }

        this.goToStartingPosition();
        this.board = window.Chessground(boardElement, {
          viewOnly: false,
          draggable: false,
          highlight: {
            lastMove: true,
            check: true,
          },
          orientation: this.variationData.color,
          fen: this.chess.fen(),
          coordinates: false,
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
      this.quizMoveIndex = this.variationData.start_index;
      if (this.variationData.start_index >= 0) {
        for (let i = 0; i <= this.variationData.start_index; i++) {
          const quizMove = this.variationData.moves[i];
          this.chess.move(quizMove.san);
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
          .flatMap((row) => row.map((square) => (square ? square.square : null)))
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
    noMoreMoves() {
      return this.quizMoveIndex >= this.variationData.moves.length;
    },

    //--------------------------------------------------------------------------------
    handleMove(orig, dest) {
      const move = this.chess.move({ from: orig, to: dest });

      this.board.set({
        fen: this.chess.fen(),
        movable: {
          dests: this.toDests(),
        },
      });
      this.checkQuizMove(move);
    },

    //--------------------------------------------------------------------------------
    playOpposingMove() {
      setTimeout(() => {
        this.quizMoveIndex++;
        if (this.noMoreMoves()) {
          this.completeQuiz();
          return;
        }
        const san = this.variationData.moves[this.quizMoveIndex].san;
        const move = this.chess.move(san);

        this.board.set({
          fen: this.chess.fen(),
          movable: {
            dests: this.toDests(),
          },
          lastMove: [move.from, move.to],
        });
        this.quizMoveIndex++;
      }, 250); // 0.25 second delay
      // (later: maybe 1 second for first move? shorter for subsequent?)
    },

    //--------------------------------------------------------------------------------
    checkQuizMove(move) {
      if (this.noMoreMoves()) {
        this.completeQuiz();
        return;
      }

      const answer = this.variationData.moves[this.quizMoveIndex];

      if (move.san === answer.san) {
        // green indicates that the move was successful, and purple
        // that the outcome of the quiz is still pending
        this.status = "🟢🟣";
        this.playOpposingMove();
      } else if (answer.alt.includes(move.san)) {
        // alt moves are acceptable moves; yellow means we won't fail you for it
        this.status = "🟢🟡";
        this.annotateMissedMove(move.from, move.to, "green", "yellow");
      } else if (answer.alt_fail.includes(move.san)) {
        // alt moves are acceptable moves; red means we will fail you for it
        this.status = "🟢🔴";
        this.annotateMissedMove(move.from, move.to, "green", "red");
        this.failed = true;
      } else {
        // complete fail (the move might be fine; we just haven't marked it as such)
        this.status = "🔴🔴";
        this.annotateMissedMove(move.from, move.to, "red", "red");
        this.failed = true;
      }
    },

    //--------------------------------------------------------------------------------
    showQuizMove() {
      if (this.noMoreMoves()) {
        this.status = "🤷 no more moves to show 💣️";
        return;
      }
      const san = this.variationData.moves[this.quizMoveIndex].san;
      const move = this.chess.move(san);

      this.failed = true;
      this.annotateMove(move.from, move.to, "blue", "blue");
      this.chess.undo();
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
        // green indicates that the last move was successful, which it *has* to be
        // in order to complete the quiz; it seems like we need some indication
        // that the move itself was good, but the quiz as a whole was not
        this.status = "🟢🔴";
        this.reportResult(false);
      } else {
        this.status = "🟢🟢";
        this.reportResult(true);
      }
    },

    //--------------------------------------------------------------------------------
    restartQuiz() {
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

    //--------------------------------------------------------------------------------
    reportResult(passed) {
      const variationId = this.variationData.variation_id;

      fetch("/report_result/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          variation_id: variationId,
          passed: passed,
        }),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.status === "success") {
            console.log(`result reported successfully: ${variationId} ${passed}`);
          } else {
            console.error("failed to report result:", data.message);
          }
        })
        .catch((error) => {
          console.error("error reporting result:", error);
        });
    },

    //--------------------------------------------------------------------------------
    nothingToSeeHere(boardElement) {
      console.log("no variation data");
      this.status = "😌";
      this.board = window.Chessground(boardElement, {
        viewOnly: true,
        draggable: false, // true is no different? (only want to click anyway)
        orientation: "white",
        fen: this.chess.fen(),
        coordinates: false,
      });
    },

    //--------------------------------------------------------------------------------
    nextQuiz() {
      window.location.href = "/review/";
    },

    //--------------------------------------------------------------------------------
    editVariation() {
      const variationId = this.variationData.variation_id || 1;
      window.location.href = `/edit/${variationId}/`;
    },
  }; // return { ... }
}

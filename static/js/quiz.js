import { Chessground } from "../chessground/chessground.min.js";
import { Chess } from "../chessjs/chess.js";

window.Chessground = Chessground;
window.Chess = Chess;

export function quizApp() {
  return {
    board: null,
    chess: null,
    status: "⚪️⚪️",
    reviewStats: "",
    variationData: variationData,
    reviewData: reviewData,
    showInfo: false,
    quizMoveIndex: 0,
    failed: false,
    completed: false,

    initQuiz() {
      console.log("initQuiz()");
      const boardElement = document.getElementById("board");

      if (!this.variationData || Object.keys(this.variationData).length === 0) {
        this.nothingToSeeHere(boardElement);
        return;
      }

      if (boardElement && window.Chessground && window.Chess) {
        this.chess = new window.Chess();

        this.goToStartingPosition();
        if (this.reviewSessionIsComplete()) {
          this.resetReviewSession();
        }
        this.board = window.Chessground(boardElement, {
          viewOnly: false,
          highlight: { lastMove: true, check: true },
          orientation: this.variationData.color,
          fen: this.chess.fen(),
          coordinates: false,
          movable: {
            color: "both", // Allow both white and black to move
            free: false, // Only legal moves
            dests: this.toDests(),
            showDests: false,
            events: { after: this.handleMove.bind(this) },
          },
        });
        console.log("Chess board loaded");
      } else {
        console.error("chessground or chess.js failed to load");
      }

      this.playOpposingMove();
      this.displayReviewSessionStats();

      const isLocal = ["127.0.0.1", "localhost"].includes(window.location.hostname);
      if (isLocal) {
        const devIndicator = document.getElementById("dev-indicator");
        if (devIndicator) {
          devIndicator.style.display = "block";
        }
      }
    }, // initQuiz()

    goToStartingPosition() {
      this.status = "🟣🟣";
      // Go back two so we can play the first opposing move
      this.quizMoveIndex = this.variationData.start_index - 2;
      if (this.quizMoveIndex >= 0) {
        for (let i = 0; i <= this.quizMoveIndex; i++) {
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
        movable: { dests: this.toDests() },
      });
      this.checkQuizMove(move);
    },

    //--------------------------------------------------------------------------------
    playOpposingMove() {
      setTimeout(() => {
        if (this.quizMoveIndex === -2) {
          // White quiz starting on first move (not something we'll see often)
          // (either playing it or missing it and going back)
          this.quizMoveIndex = 0;
          return;
        }
        this.quizMoveIndex++;
        if (this.noMoreMoves()) {
          this.completeQuiz();
          return;
        }
        const san = this.variationData.moves[this.quizMoveIndex].san;
        const move = this.chess.move(san);

        this.board.set({
          fen: this.chess.fen(),
          movable: { dests: this.toDests() },
          lastMove: [move.from, move.to],
        });
        this.quizMoveIndex++;
      }, 250); // 0.25 second delay
      // (Later: maybe 1 second for first move? shorter for subsequent?)
    },

    //--------------------------------------------------------------------------------
    checkQuizMove(move) {
      if (this.noMoreMoves()) {
        this.completeQuiz();
        return;
      }

      const answer = this.variationData.moves[this.quizMoveIndex];
      let correct = false;

      if (move.san === answer.san) {
        correct = true;
      } else {
        // e.g. Nge7 => Ne7
        const reambiguateMove = (san) => {
          return san.replace(/([NBRQK])([a-h1-8])x?([a-h][1-8][+#]?)/g, "$1$3");
        };
        const normalizedMoveSan = reambiguateMove(move.san);
        const normalizedAnswerSan = reambiguateMove(answer.san);
        correct = normalizedMoveSan === normalizedAnswerSan;
        if (correct) {
          console.log(
            `move.san (${move.san}) !== answer.san (${answer.san}), but normalized/reambiguated values matched! ${normalizedMoveSan} === ${normalizedAnswerSan}`
          );
        }
      }

      if (correct) {
        // Green indicates that the move was successful, and purple
        // that the outcome of the quiz is still pending
        this.status = "🟢🟣";
        this.playOpposingMove();
      } else if (answer.alt.includes(move.san)) {
        // Alt moves are playable moves; yellow means we won't fail you for it
        this.status = "🟢🟡";
        this.annotateMissedMove(move.from, move.to, "green", "yellow");
      } else if (answer.alt_fail.includes(move.san)) {
        // Alt moves are playable moves; red means we will fail you for it
        this.status = "🟢🔴";
        this.annotateMissedMove(move.from, move.to, "green", "red");
        this.failed = true;
      } else {
        // Complete fail (the move might be playable; but we haven't yet marked it so)
        this.status = "🔴🔴";
        this.annotateMissedMove(move.from, move.to, "red", "red");
        this.failed = true;
      }
    },

    //--------------------------------------------------------------------------------
    showQuizMove() {
      if (!this.variationData.moves) return;
      if (this.noMoreMoves()) {
        this.status = "🤷 no move to show 💣️";
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
      // piece: "circle" or "arrow" is implied based on one or two points being given
      this.board.set({
        drawable: {
          shapes: [
            { orig: to, brush: circleColor },
            { orig: from, dest: to, brush: arrowColor },
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
        movable: { dests: this.toDests() },
      });
      this.playOpposingMove();
    },

    //--------------------------------------------------------------------------------
    completeQuiz() {
      this.completed = true;
      this.showInfo = true;
      if (this.failed) {
        // Green indicates that the last move was successful, which it *has* to be
        // in order to complete the quiz; it seems like we need some indication
        // that the move itself was good, but the quiz as a whole was not
        this.status = "🟢🔴";
      } else {
        this.status = "🟢🟢";
      }

      if (this.reviewData.extra_study) {
        console.log("extra study: not reporting result");
      } else {
        this.reportResult(!this.failed);
      }

      if (this.failed && !this.reviewData.extra_study) {
        this.reviewData.extra_study = true;
        this.showInfo = false;
        this.restartQuiz();
      } else {
        const shapes = this.variationData.moves[this.quizMoveIndex - 1].shapes || "[]";
        this.board.set({ drawable: { shapes: JSON.parse(shapes) } });
      }
    },

    //--------------------------------------------------------------------------------
    restartQuiz() {
      if (!this.variationData.moves) return;
      if (this.completed) {
        this.reviewData.extra_study = true;
      } else {
        this.failed = false;
      }
      this.chess.reset();
      this.goToStartingPosition();
      this.board.set({
        fen: this.chess.fen(),
        movable: { dests: this.toDests() },
      });
      this.playOpposingMove();
      this.displayReviewSessionStats();
    },

    //--------------------------------------------------------------------------------
    finalMove() {
      if (!this.variationData.moves || this.variationData.moves.length === 0) return {};
      return this.variationData.moves[this.variationData.moves.length - 1];
    },

    //--------------------------------------------------------------------------------
    displayReviewSessionStats() {
      if (!this.reviewData) return;

      const passed = parseInt(localStorage.getItem("review_pass") || "0", 10);
      const failed = parseInt(localStorage.getItem("review_fail") || "0", 10);

      const totalCompleted = passed + failed;
      const dueSoon = this.reviewData.total_due_soon
        ? ` (+${this.reviewData.total_due_soon} soon)`
        : "";

      const extra = this.reviewData.extra_study ? "(Extra Study) " : "";

      this.reviewStats = `${extra} Done: ${totalCompleted} (${passed}/${totalCompleted}, ${
        totalCompleted ? Math.round((passed / totalCompleted) * 100) : 0
      }%), Due: ${this.reviewData.total_due_now}${dueSoon}`;
    },

    //--------------------------------------------------------------------------------
    saveQuizResult(passed) {
      console.log("saveQuizResult", passed);
      if (this.reviewSessionIsComplete()) {
        localStorage.removeItem("review_session_complete");
        localStorage.setItem("review_pass", 0);
        localStorage.setItem("review_fail", 0);
      }

      let passCount = parseInt(localStorage.getItem("review_pass") || "0", 10);
      let failCount = parseInt(localStorage.getItem("review_fail") || "0", 10);

      if (passed) {
        localStorage.setItem("review_pass", ++passCount);
      } else {
        localStorage.setItem("review_fail", ++failCount);
      }

      this.displayReviewSessionStats();
    },

    //--------------------------------------------------------------------------------
    completeReviewSession() {
      localStorage.setItem("review_session_complete", "true");
    },

    //--------------------------------------------------------------------------------
    reviewSessionIsComplete() {
      return localStorage.getItem("review_session_complete") === "true";
    },

    //--------------------------------------------------------------------------------
    resetReviewSession() {
      localStorage.removeItem("review_pass");
      localStorage.removeItem("review_fail");
      localStorage.removeItem("review_complete");

      this.displayReviewSessionStats();
    },

    //--------------------------------------------------------------------------------
    gotoVariationView() {
      const variationId = this.variationData.variation_id || 1;
      const idx = this.quizMoveIndex - 1 || 6;
      window.location.href = `/variation/${variationId}/?idx=${idx}`;
    },

    //--------------------------------------------------------------------------------
    nextMove() {
      // can lock this down later to only allow after quiz is completed;
      // buttons are hidden until after, but maybe we'll add arrow key nav
      if (this.quizMoveIndex < this.variationData.moves.length) {
        this.chess.move(this.variationData.moves[this.quizMoveIndex++].san);
        this.updateBoard();
      }
    },

    //--------------------------------------------------------------------------------
    previousMove() {
      if (this.quizMoveIndex > 0) {
        this.chess.undo();
        this.quizMoveIndex--;
      } else {
        this.quizMoveIndex = 0; // Ensure forward nav works correctly
        this.chess.reset();
      }
      this.updateBoard();
    },

    //--------------------------------------------------------------------------------
    updateBoard() {
      this.board.set({
        fen: this.chess.fen(),
        drawable: {
          shapes:
            this.quizMoveIndex > 0
              ? JSON.parse(
                  this.variationData.moves[this.quizMoveIndex - 1].shapes || "[]"
                )
              : [],
        },
      });
    },

    //--------------------------------------------------------------------------------
    reportResult(passed) {
      const variationId = this.variationData.variation_id;

      fetch("/report-result/", {
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
            const text = passed ? "Passed" : "Failed";
            console.log(`Result reported successfully: ${text} ${variationId}`);
            this.reviewData.total_due_now = data.total_due_now;
            this.reviewData.total_due_soon = data.total_due_soon;
            this.saveQuizResult(passed);
            if (data.total_due_now === 0 && data.total_due_soon === 0)
              this.completeReviewSession();
          } else {
            console.error("Failed to report result:", data.message);
          }
        })
        .catch((error) => {
          console.error("Error reporting result:", error);
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
      this.completeReviewSession();
      this.displayReviewSessionStats();
    },
  }; // return { ... }
}

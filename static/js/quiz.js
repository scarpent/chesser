import { Chessground } from "../chessground/chessground.min.js";
import { Chess } from "../chessjs/chess.js";

window.Chessground = Chessground;
window.Chess = Chess;

export function quizApp() {
  return {
    board: null,
    chess: null,
    status: "",
    reviewStats: "",
    variationData: variationData,
    reviewData: reviewData,
    showInfo: false,
    showCounterReset: false,
    quizMoveIndex: 0,
    failed: false,
    completed: false,
    quizCompleteOverlay: "", // emoji or empty string
    annotateTimeoutId: null, // helps manage quiz restarts

    initQuiz() {
      const boardElement = document.getElementById("board");

      if (boardElement && window.Chessground && window.Chess) {
        this.chess = new window.Chess();

        if (this.nothingToSeeHere(boardElement) || this.alreadyCompleted()) {
          return;
        }

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

        this.playOpposingMove();
        this.displayReviewSessionStats();
      } else {
        console.error("chessground or chess.js failed to load");
      }
    }, // initQuiz()

    goToStartingPosition() {
      if (this.failed) {
        this.status = this.getQuizCompleteEmoji();
      } else {
        this.status = "🟤";
      }
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
    async handleMove(orig, dest) {
      const piece = this.chess.get(orig);
      const isPromotion =
        piece && piece.type === "p" && (dest.endsWith("8") || dest.endsWith("1"));

      let move;
      if (isPromotion) {
        const promotion = await this.showPromotionModal();
        move = this.chess.move({ from: orig, to: dest, promotion });
      } else {
        move = this.chess.move({ from: orig, to: dest });
      }

      if (!move) {
        console.error(`Illegal move: ${orig} to ${dest}`);
        return;
      }

      this.board.set({
        fen: this.chess.fen(),
        movable: { dests: this.toDests() },
      });

      this.checkQuizMove(move);
    },

    //--------------------------------------------------------------------------------
    showPromotionModal() {
      return new Promise((resolve) => {
        const modal = document.getElementById("promotion-modal");
        modal.dispatchEvent(new CustomEvent("promotion", { detail: resolve }));
      });
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

        // quizzes *should* end on our move but if we have a
        // hanging opposing move we'll need to end things here...
        if (this.noMoreMoves()) {
          this.completeQuiz();
          return;
        }
      }, 250); // 0.25 second delay
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
        this.status = "🟢";
        this.playOpposingMove();
        this.annotateCircle(move.to, "green");
      } else if (answer.alt.includes(move.san)) {
        // Alt moves are playable moves; yellow means we won't fail you for it
        this.status = "🟡";
        this.annotateMissedMove(move.from, move.to, "yellow", "green");
      } else if (answer.alt_fail.includes(move.san)) {
        // Alt moves are playable moves; red means we will fail you for it
        this.status = "🔴";
        this.annotateMissedMove(move.from, move.to, "red", "green");
        this.failed = true;
      } else {
        // Complete fail (the move might be playable; but we haven't yet marked it so)
        this.status = "🔴";
        this.annotateMissedMove(move.from, move.to, "red", "red");
        this.failed = true;
      }
    },

    //--------------------------------------------------------------------------------
    showQuizMove() {
      if (!this.variationData.moves) return;
      if (this.noMoreMoves()) {
        this.status = "💣️🤷";
        return;
      }
      const san = this.variationData.moves[this.quizMoveIndex].san;
      const move = this.chess.move(san);

      this.failed = true;
      this.annotateMove(move.from, move.to, "blue", "blue");
      this.chess.undo();
    },

    //--------------------------------------------------------------------------------
    annotateCircle(square, color) {
      this.board.set({
        drawable: {
          shapes: [{ orig: square, brush: color }],
        },
      });
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
      // Save timeout ID so it can be canceled if needed
      this.annotateTimeoutId = setTimeout(() => {
        this.gotoPreviousMove();
        this.annotateTimeoutId = null;
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
      // last move has to have succeeded to have completed the quiz; the board
      // status emoji overlay will indicate if the overall quiz failed
      this.status = "🟢";

      if (this.reviewData.extra_study) {
        console.log("extra study: not reporting result");
      } else {
        this.reportResult(!this.failed);
        // saw some issues with quiz "restarting" when returning from
        // lichess analysis board; we'll try to avoid that...
        localStorage.setItem(`quiz_completed_${this.variationData.variation_id}`, "1");
        localStorage.setItem("last_completed_time", new Date().toISOString());
      }

      if (this.failed && !this.reviewData.extra_study) {
        this.reviewData.extra_study = true;
        this.showInfo = false;
        // for this first forced re-review-extra-study, we want to maintain the
        // failure state; for other restarts, we'll reset failed to get nicer feedback
        // on our current effort
        this.restartQuiz(true);
        return;
      } else {
        // reveal arrows/circles for the last move
        const shapes = this.variationData.moves[this.quizMoveIndex - 1].shapes || "[]";
        this.board.set({ drawable: { shapes: JSON.parse(shapes) } });
      }
      this.quizCompleteOverlay = this.getQuizCompleteEmoji();
    },

    //--------------------------------------------------------------------------------
    restartQuiz(stayFailed = false) {
      if (!this.variationData.moves) return;

      // Cancel any pending "go back after missed move" (e.g. if we click "restart"
      // while still showing error state, before going back to the previous move)
      if (this.annotateTimeoutId) {
        clearTimeout(this.annotateTimeoutId);
        this.annotateTimeoutId = null;
      }

      if (this.completed) {
        this.reviewData.extra_study = true; // whether forced or elective
      } else {
        // this is the money, giving us the ability to restart e.g. because
        // we feel like we were distracted and didn't *really* miss a move
        this.failed = false;
      }
      // in general we want to start fresh on extra study, except
      // for the forced re-review after failing a live/due quiz
      if (this.reviewData.extra_study && !stayFailed) {
        this.failed = false;
      }

      this.quizCompleteOverlay = "";
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
    displayReviewSessionStats() {
      if (!this.reviewData) return;

      const passed = parseInt(localStorage.getItem("review_pass") || "0", 10);
      const failed = parseInt(localStorage.getItem("review_fail") || "0", 10);
      this.showCounterReset = passed + failed !== 0;

      const totalCompleted = passed + failed;
      // if we have enough reviews due, we're not much concerned about the "soon" count
      const dueSoon =
        this.reviewData.total_due_soon && this.reviewData.total_due_now < 25
          ? ` (+${this.reviewData.total_due_soon} soon)`
          : "";

      const extra_color = this.failed ? "red" : "lightgreen";
      const extra = this.reviewData.extra_study
        ? `<span style="color: ${extra_color}">extra study</span> `
        : "";

      const totalDue = this.reviewData.total_due_now + this.reviewData.total_due_soon;
      const emoji =
        totalDue === 0
          ? "💤" // nothing due, rest easy
          : totalDue > 24
          ? "😬" // yikes! better study
          : "🏃"; // manageable, keep on running

      this.reviewStats = `${extra}<span>✏️</span>
        <span>${passed}/${totalCompleted}</span>
        <span>${
          totalCompleted ? Math.round((passed / totalCompleted) * 100) : 0
        }%</span>
        <span>${emoji} ${this.reviewData.total_due_now}${dueSoon}</span>`;
    },

    //--------------------------------------------------------------------------------
    updateReviewSessionStats(passed) {
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
      if (localStorage.getItem("review_session_complete") === "true") {
        return true;
      }

      const lastCompleted = localStorage.getItem("last_completed_time");
      if (lastCompleted) {
        const lastTime = new Date(lastCompleted);
        const now = new Date();
        const diffMillis = now - lastTime;
        const diffMinutes = diffMillis / (1000 * 60);
        if (diffMinutes >= 30) {
          return true;
        }
      }

      return false;
    },

    //--------------------------------------------------------------------------------
    resetReviewSession() {
      localStorage.removeItem("review_pass");
      localStorage.removeItem("review_fail");
      localStorage.removeItem("review_complete");
      localStorage.removeItem("last_completed_time");

      Object.keys(localStorage).forEach((key) => {
        if (key.startsWith("quiz_completed_")) {
          localStorage.removeItem(key);
        }
      });

      this.displayReviewSessionStats();
    },

    //--------------------------------------------------------------------------------
    gotoVariationView() {
      const variationId = this.variationData.variation_id;
      const idx = this.quizMoveIndex - 1 || 6;
      window.location.href = `/variation/${variationId}/?idx=${idx}`;
    },

    //--------------------------------------------------------------------------------
    gotoEditView() {
      const variationId = this.variationData.variation_id;
      const idxParam =
        this.quizMoveIndex > this.variationData.start_index
          ? `?idx=${this.quizMoveIndex - 1}`
          : "";
      window.location.href = `/edit/${variationId}/${idxParam}`;
    },

    //--------------------------------------------------------------------------------
    nextMove() {
      if (!this.completed) return;

      if (this.quizMoveIndex < this.variationData.moves.length) {
        this.chess.move(this.variationData.moves[this.quizMoveIndex++].san);
        this.updateBoard();
      }
    },

    //--------------------------------------------------------------------------------
    previousMove() {
      if (!this.completed) return;

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
      this.quizCompleteOverlay = "";
    },

    //--------------------------------------------------------------------------------
    handleKeyNavigation(event) {
      if (event.key === "ArrowRight") {
        this.nextMove();
      } else if (event.key === "ArrowLeft") {
        this.previousMove();
      }
    },

    //--------------------------------------------------------------------------------
    async reportResult(passed) {
      const variationId = this.variationData.variation_id;

      try {
        const response = await fetch("/report-result/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ variation_id: variationId, passed }),
        });

        const data = await response.json();

        if (data.status === "success") {
          this.reviewData.total_due_now = data.total_due_now;
          this.reviewData.total_due_soon = data.total_due_soon;
          this.updateReviewSessionStats(passed);

          if (data.total_due_now === 0 && data.total_due_soon === 0) {
            this.completeReviewSession();
          }
        } else {
          console.error("Failed to report result:", data.message);
        }
      } catch (error) {
        console.error("Error reporting result:", error);
      }
    },
    //--------------------------------------------------------------------------------
    alreadyCompleted() {
      const variationId = this.variationData.variation_id;
      const completedKey = `quiz_completed_${variationId}`;

      let completedCount = parseInt(localStorage.getItem(completedKey) || "0", 10);
      completedCount += 1;
      localStorage.setItem(completedKey, completedCount.toString());

      // safety check -- if for some reason *not* completed, we won't get stuck in a
      // loop; also be mindful of extra study mode!
      if (completedCount === 2 && !this.reviewData.extra_study) {
        console.log(`Quiz ${variationId} already completed — skipping and redirecting`);
        window.location.href = "/review/";
        return true;
      }

      return false;
    },

    //--------------------------------------------------------------------------------
    hasVariationData() {
      return this.variationData && Object.keys(this.variationData).length > 0;
    },

    //--------------------------------------------------------------------------------
    getQuizCompleteEmoji() {
      const successEmojis = [
        "🔰", // L0
        "🌿", // L1
        "🪴", // L2
        "🍀", // L3
        "🐶", // L4
        "⭐️", // L5
        "🏵️", // L6
        "🔥", // L7
        "🤖", // L8
        "🏆", // L9
        "💎", // L10+
      ];
      const failEmojis = [
        "🔰", // L0 - it's okay, we're just beginning!
        "😬", // L1
        "😞", // L2
        "😦", // L3
        "😢", // L4
        "😠", // L5
        "🥵", // L6
        "😡", // L7
        "🤬", // L8
        "☠️", // L9
        "🙈", // L10+
      ];
      const level = Number(this.variationData?.level) || 0;
      const idx = Math.min(level, successEmojis.length - 1);

      if (this.failed) {
        return failEmojis[idx];
      }
      return successEmojis[idx];
    },

    //--------------------------------------------------------------------------------
    nothingToSeeHere(boardElement) {
      if (!this.hasVariationData() || !this.variationData.moves) {
        this.status = "😌";
        this.board = window.Chessground(boardElement, {
          viewOnly: true,
          orientation: "white",
          fen: this.chess.fen(),
          coordinates: false,
        });
        this.completeReviewSession();
        this.displayReviewSessionStats();
        return true;
      } else {
        return false;
      }
    },
  }; // return { ... }
}

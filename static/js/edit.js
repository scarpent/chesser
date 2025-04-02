import { Chessground } from "../chessground/chessground.min.js";
import { Chess } from "../chessjs/chess.js";

window.Chessground = Chessground;
window.Chess = Chess;

export function editApp() {
  return {
    boards: [],
    chess: null,
    variationData: variationData,
    currentMoveIndex: 0,

    initEditor() {
      document.addEventListener("alpine:initialized", () => {
        const chess = new window.Chess();

        this.$nextTick(() => {
          // Waits for DOM update to complete
          this.variationData.moves.forEach((move, index) => {
            const boardElement = document.getElementById(`edit-board-${index}`);
            if (boardElement) {
              const moveResult = chess.move(move.san);
              // We use x-init for move.fen in the template to avoid
              // a console error before we assign the value here
              move.fen = chess.fen();
              this.boards.push(
                window.Chessground(boardElement, {
                  fen: chess.fen(),
                  orientation: this.variationData.color,
                  coordinates: false,
                  movable: { free: false, showDests: false },
                  highlight: { lastMove: true, check: true },
                  lastMove: [moveResult.from, moveResult.to],
                  drawable: { shapes: move.shapes ? JSON.parse(move.shapes) : [] },
                })
              );
            } else {
              console.error(`Board element edit-board-${index} not found`);
            }
          });
          this.scrollToMoveBlockFromURL();

          const mainline = document.getElementById("edit-mainline-moves");
          if (mainline) {
            mainline.addEventListener("click", (e) => {
              if (e.target.classList.contains("edit-mainline-move-item")) {
                const idx = parseInt(e.target.dataset.idx, 10);
                if (!isNaN(idx)) this.scrollToMoveBlock(idx);
              }
            });
          }
        });
      });
    },

    //--------------------------------------------------------------------------------
    saveVariation() {
      console.log("Saving variation data...", this.variationData);
      this.saveErrors = [];
      const payload = {
        variation_id: this.variationData.variation_id,
        title: this.variationData.title,
        start_move: this.variationData.start_move, // TODO: validation
      };

      payload.moves = this.variationData.moves.map((move, index) => ({
        san: move.san,
        annotation: move.annotation === "none" ? "" : move.annotation,
        text: move.text,
        alt: move.alt,
        alt_fail: move.alt_fail,
        shapes:
          this.boards[index].state.drawable.shapes.length > 0
            ? JSON.stringify(this.boards[index].state.drawable.shapes)
            : "",
      }));

      fetch("/save-variation/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.errors) {
            this.saveErrors = data.errors;
            console.error("Save errors:", this.saveErrors);
          } else {
            console.log("Variation saved successfully");
            window.location.reload(); // Reload page to reflect backend changes
          }
        })
        .catch((error) => {
          console.error("Error saving variation:", error);
          this.saveErrors.push("An unexpected error occurred.");
        });
    },

    //--------------------------------------------------------------------------------
    validateAltMoves(index, field) {
      const actualSan = this.variationData.moves[index].san;
      const actualMoveVerbose = this.variationData.moves[index].move_verbose;
      let alternateMoves = this.variationData.moves[index][field];
      console.log("Validating alt moves for", actualMoveVerbose, "➤", alternateMoves);

      if (
        !alternateMoves ||
        typeof alternateMoves !== "string" ||
        !alternateMoves.trim()
      )
        return;

      // Trim spaces and remove duplicates
      const altMoves = [
        ...new Set(
          alternateMoves
            .split(/[,\s]+/)
            .map((m) => m.trim())
            .filter(Boolean)
        ),
      ];

      const bad = [],
        good = [];

      const chess = new window.Chess();
      // Play up to previous move so we can check for legal alt moves
      for (let i = 0; i < index; i++) chess.move(this.variationData.moves[i].san);

      altMoves.forEach((altMove) => {
        if (altMove === actualSan) {
          bad.push(altMove); // Ignore if identical to the actual move
          return;
        }
        try {
          chess.move(altMove);
          good.push(altMove);
          chess.undo();
        } catch (error) {
          console.error(`Invalid move for ${actualMoveVerbose}: ${altMove}`);
          bad.push(altMove);
        }
      });

      // console.log("good/bad:", good, bad);
      if (bad.length)
        console.error(
          `❌ Invalid alt moves for ${actualMoveVerbose} ➤ ${bad.join(", ")}`
        );

      // Update input with only valid moves
      this.variationData.moves[index][field] = good.join(", ");
    },

    //--------------------------------------------------------------------------------
    renderMainlineMoveLinks() {
      const moves = this.variationData.mainline.split(" ");
      const pairs = [];

      for (let i = 0; i < moves.length; i += 2) {
        const white = moves[i];
        const black = moves[i + 1] || "";

        const pairHtml = `
              <span class="edit-mainline-move-pair">
                <span class="edit-mainline-move-item" data-idx="${i}">${white}</span>
                ${
                  black
                    ? `<span class="edit-mainline-move-item" data-idx="${
                        i + 1
                      }">${black}</span>`
                    : ""
                }
              </span>
            `;

        pairs.push(pairHtml);
      }

      return pairs.join(" ");
    },

    //--------------------------------------------------------------------------------
    scrollToMoveBlockFromURL() {
      const params = new URLSearchParams(window.location.search);
      const idx = parseInt(params.get("idx"), 10);
      if (!isNaN(idx)) {
        this.scrollToMoveBlock(idx);

        // Remove idx from URL
        params.delete("idx");
        const newUrl =
          window.location.pathname + (params.toString() ? "?" + params.toString() : "");
        window.history.replaceState({}, "", newUrl);
      }
    },

    //--------------------------------------------------------------------------------
    scrollToMoveBlock(idx) {
      if (typeof idx !== "number" || isNaN(idx)) return;
      // Small delay to ensure the DOM is rendered
      setTimeout(() => {
        const moveBlock = document.querySelectorAll(".move-block")[idx];
        if (moveBlock) {
          const useSmooth = false;
          const behavior = useSmooth ? "smooth" : "auto";
          moveBlock.scrollIntoView({ behavior: behavior, block: "start" });
          this.currentMoveIndex = idx;
        }
      }, 100); // Tweak as needed based on render speed
    },

    //--------------------------------------------------------------------------------
    handleKeyNavigation(event) {
      const isUp = event.key === "ArrowUp";
      const isDown = event.key === "ArrowDown";
      const modifier = event.metaKey || event.ctrlKey || event.shiftKey;

      if (!isUp && !isDown) return;

      event.preventDefault();

      if (modifier) {
        if (isUp) {
          this.scrollToTop();
        } else if (isDown) {
          this.scrollToBottom();
        }
        return;
      }

      if (isUp) {
        if (this.currentMoveIndex > 0) {
          this.gotoPreviousMove();
        } else {
          this.scrollToTop(); // extra fallback
        }
      } else if (isDown) {
        if (this.currentMoveIndex < this.variationData.moves.length - 1) {
          this.gotoNextMove();
        }
      }
    },

    //--------------------------------------------------------------------------------
    scrollToTop() {
      window.scrollTo({ top: 0, behavior: "auto" });
      this.currentMoveIndex = 0;
    },

    //--------------------------------------------------------------------------------
    scrollToBottom() {
      const moveBlocks = document.querySelectorAll(".move-block");
      const lastIndex = moveBlocks.length - 1;
      if (lastIndex >= 0) {
        moveBlocks[lastIndex].scrollIntoView({ behavior: "auto", block: "start" });
        this.currentMoveIndex = lastIndex;
      }
    },

    //--------------------------------------------------------------------------------
    gotoNextMove() {
      const next = (this.currentMoveIndex ?? -1) + 1;
      if (next < this.variationData.moves.length) {
        this.scrollToMoveBlock(next);
      }
    },

    //--------------------------------------------------------------------------------
    gotoPreviousMove() {
      const prev = (this.currentMoveIndex ?? 1) - 1;
      if (prev >= 0) {
        this.scrollToMoveBlock(prev);
      } else {
        // Already at first move — scroll to top of page
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    },
  }; // return { ... }
}

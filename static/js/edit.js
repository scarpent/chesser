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
              // move.fen = chess.fen();
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
                const idx = parseInt(e.target.dataset.index, 10);
                if (!isNaN(idx)) this.scrollToMoveBlock(idx);
              }
            });
          }
        });
      });
    },

    //---------------------------------------------------------------------------------
    buildPayload() {
      const payload = {
        variation_id: this.variationData.variation_id,
        title: this.variationData.title,
        start_move: this.variationData.start_move, // TODO: validation
        moves: [],
      };

      payload.moves = this.variationData.moves.map((move, index) => {
        const boardShapes = this.boards[index].state.drawable.shapes;
        return {
          san: move.san,
          annotation: move.annotation === "none" ? "" : move.annotation,
          text: move.text.trim(),
          alt: move.alt,
          alt_fail: move.alt_fail,
          shapes: boardShapes.length > 0 ? JSON.stringify(boardShapes) : "",
        };
      });

      return payload;
    },

    //--------------------------------------------------------------------------------
    handleSaveResult(status, index = null) {
      const btn = document.querySelector(".icon-save");
      if (btn) {
        const className = `save-${status}`;
        btn.classList.add(className);
      }

      if (status === "success") {
        const isMobile = window.innerWidth < 700;

        setTimeout(() => {
          if (isMobile && index !== null) {
            const url = new URL(window.location.href);
            url.searchParams.set("idx", index);
            window.location.href = url.toString(); // mobile redirect to current move with idx
          } else {
            // desktop reload will automatically restore our place on the page
            window.location.reload();
          }
        }, 750);
      }
    },

    //--------------------------------------------------------------------------------
    saveFromMove(index) {
      this.saveVariation(index).then((success) => {
        this.variationData.moves[index].saved = success ? "success" : "error";
        // clear after short delay only if sucessuful (leave red background if error)
        if (success) {
          setTimeout(() => {
            this.variationData.moves[index].saved = null;
          }, 750);
        }
      });
    },

    //--------------------------------------------------------------------------------
    async saveVariation(index) {
      console.log("Saving variation data...", this.variationData);
      const payload = this.buildPayload();

      try {
        const response = await fetch("/save-variation/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        const data = await response.json();
        console.log("data:", data);

        if (data.status === "error") {
          console.error("Save error:", data.message);
          this.handleSaveResult("error");
          return false;
        } else {
          console.log("Variation saved successfully");
          this.handleSaveResult("success", index);
          return true;
        }
      } catch (error) {
        console.error("Error saving variation:", error);
        this.handleSaveResult("error");
        return false;
      }
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
                <span class="edit-mainline-move-item" data-index="${i}">${white}</span>
                ${
                  black
                    ? `<span class="edit-mainline-move-item" data-index="${
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
      }, 100);
    },

    //--------------------------------------------------------------------------------
    handleKeyNavigation(event) {
      const tag = event.target.tagName.toLowerCase();
      const isFormInput =
        tag === "input" ||
        tag === "textarea" ||
        tag === "select" ||
        event.target.isContentEditable;

      // 💾 Save shortcut: Cmd/Ctrl + S
      if ((event.metaKey || event.ctrlKey) && event.key === "s") {
        event.preventDefault();
        this.saveVariation(this.currentMoveIndex);
        return;
      }

      if (isFormInput) return; // skip navigation inside form elements

      const isBackward = event.key === "ArrowUp" || event.key === "ArrowLeft";
      const isForward = event.key === "ArrowDown" || event.key === "ArrowRight";
      const modifier = event.metaKey || event.ctrlKey || event.shiftKey;

      if (!isBackward && !isForward) return;

      event.preventDefault();

      if (modifier) {
        if (isBackward) {
          this.scrollToTop();
        } else if (isForward) {
          this.scrollToBottom();
        }
        return;
      }

      if (isBackward) {
        if (this.currentMoveIndex > 0) {
          this.gotoPreviousMove();
        } else {
          this.scrollToTop(); // extra fallback
        }
      } else if (isForward) {
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

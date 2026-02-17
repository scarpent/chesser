import "./chess-deps.js";
import {
  postJson,
  handleSaveButton,
  parseShapes,
  serializeShapes,
  normalizeAnnotation,
  createBoard,
} from "./edit-common.js";

export function editApp() {
  return {
    boards: [],
    chess: null,
    variationData: variationData,
    currentMoveIndex: 0,
    // make sure move state is initialized in time for UI references
    moveState: (() => {
      const map = {};
      variationData.moves.forEach((_, i) => (map[i] = {}));
      return map;
    })(),

    initEditor() {
      document.addEventListener("alpine:initialized", () => {
        const chess = new window.Chess();
        const self = this;

        this.$nextTick(() => {
          // Waits for DOM update to complete
          this.variationData.moves.forEach((move, index) => {
            const boardElement = document.getElementById(`edit-board-${index}`);
            if (boardElement) {
              const moveResult = chess.move(move.san);
              this.boards.push(
                createBoard(boardElement, chess.fen(), this.variationData.color, {
                  lastMove: [moveResult.from, moveResult.to],
                }),
              );
              self.updateSharedMoveState(index);
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
    updateSharedMoveState(index) {
      // Create a working structure to unify regular and shared move
      // data so the UI doesn't have to distinguish between them.
      // On save, the backend will decide what gets stored where.
      const move = this.variationData.moves[index];
      const sid = move.shared_move_id;
      const isShared = sid && !isNaN(parseInt(sid));
      const shared = isShared ? move.shared_candidates?.[sid] : null;

      // Create working copy of fields into moveState to be used by Alpine
      this.moveState[index] = {
        text: isShared ? (shared?.text ?? "") : move.text,
        annotation: isShared ? (shared?.annotation ?? "") : move.annotation,
        alt: isShared ? (shared?.alt ?? "") : move.alt,
        alt_fail: isShared ? (shared?.alt_fail ?? "") : move.alt_fail,
      };

      // Shapes are handled differently: they're not bound to Alpine data
      // but instead drawn and managed directly by Chessground.
      // We restore them here so the board reflects the selected state,
      // and rely on reading board state again at save time.
      const shapes = isShared ? shared?.shapes : move.shapes;
      this.boards[index].setShapes(parseShapes(shapes));
    },

    //---------------------------------------------------------------------------------
    buildPayload() {
      const payload = {
        variation_id: this.variationData.variation_id,
        title: this.variationData.title,
        chapter_id: this.variationData.chapter_id,
        start_move: this.variationData.start_move, // TODO: validation?
        moves: [],
      };

      payload.moves = this.variationData.moves.map((move, index) => {
        const state = this.moveState[index] || {};

        return {
          san: move.san,
          shared_move_id: move.shared_move_id,
          annotation: normalizeAnnotation(state.annotation),
          text: state.text.trim(),
          alt: state.alt,
          alt_fail: state.alt_fail,
          shapes: serializeShapes(this.boards[index]),
        };
      });

      return payload;
    },

    //--------------------------------------------------------------------------------
    handleSaveResult(status, index = null) {
      handleSaveButton(status);

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
      this.variationData.moves[index].saved = "pending";
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
      document.querySelector(".icon-save")?.classList.add("save-pending");

      const payload = this.buildPayload();

      try {
        const data = await postJson("/save-variation/", payload);
        console.log("data:", data);

        if (data.status === "error") {
          console.error("Save error:", data.message);
          alert(data.message || "Save failed."); // TODO: better error handling/UI
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
    validateAltMoves(index, field, evt = null) {
      // TODO: shared move editor currently doesn't validate; we could share this logic
      const actualSan = this.variationData.moves[index].san;
      const actualMoveVerbose = this.variationData.moves[index].move_verbose;

      // x-model is moveState, and on blur the DOM value is the freshest truth
      const raw =
        evt && evt.target && typeof evt.target.value === "string"
          ? evt.target.value
          : this.moveState[index][field];

      console.log("Validating alt moves for", actualMoveVerbose, "➤", raw);

      if (!raw || typeof raw !== "string" || !raw.trim()) return;

      // Remove move numbers / dot notation like "1.", "1...", "23..." and
      // drop tokens that are *only* digits.
      const cleaned = raw
        .replace(/\b\d+\.(?:\.\.)?\s*/g, " ") // 1. or 1... (and 23..., etc.)
        .replace(/\b\d+\b/g, " "); // standalone numbers

      // Trim spaces and remove duplicates
      const altMoves = [
        ...new Set(
          cleaned
            .split(/[,\s]+/)
            .map((m) => m.trim())
            .filter(Boolean),
        ),
      ];

      const bad = [];
      const good = [];

      const chess = new window.Chess();
      // Play up to previous move so we can check for legal alt moves
      for (let i = 0; i < index; i++) chess.move(this.variationData.moves[i].san);

      for (const altMove of altMoves) {
        if (altMove === actualSan) {
          bad.push(altMove); // Ignore if identical to the actual move
          continue;
        }

        try {
          const result = chess.move(altMove);

          // chess.js may either throw OR return null depending on build/version
          // (so says the bot; might as well be defensive)
          if (!result) {
            console.error(`Invalid move for ${actualMoveVerbose}: ${altMove}`);
            bad.push(altMove);
            continue;
          }

          good.push(altMove);
          chess.undo();
        } catch (error) {
          console.error(`Invalid move for ${actualMoveVerbose}: ${altMove}`);
          bad.push(altMove);
        }
      }

      if (bad.length)
        console.error(
          `❌ Invalid alt moves for ${actualMoveVerbose} ➤ ${bad.join(", ")}`,
        );

      const normalized = good.join(", ");

      // Update the model that the inputs are bound to
      this.moveState[index][field] = normalized;

      // Optional: force the visible input too
      if (evt && evt.target) evt.target.value = normalized;
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

    //--------------------------------------------------------------------------------
    buildAdminMatchingLink(move) {
      if (!move?.fen || !move?.san || !this.variationData?.color) return "#";

      const query = `fen="${move.fen}" and san="${move.san}" and variation.chapter.color="${this.variationData.color}"`;
      return "/admin/chesser/move/?q=" + encodeURIComponent(query);
    },
  }; // return { ... }
}

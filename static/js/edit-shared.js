import { Chessground } from "../chessground/chessground.min.js";
import { Chess } from "../chessjs/chess.js";

window.Chessground = Chessground;
window.Chess = Chess;

export function editApp() {
  return {
    boards: [],
    chess: null,
    moveData: moveData,
    overlayVisible: false,
    overlayBoard: null,

    initEditor() {
      document.addEventListener("alpine:initialized", () => {
        const chess = new window.Chess(this.moveData.fen);

        this.$nextTick(() => {
          // Waits for DOM update to complete
          this.moveData.shared_moves.forEach((move, index) => {
            const boardElement = document.getElementById(`edit-board-${index}`);
            if (boardElement) {
              this.boards.push(
                window.Chessground(boardElement, {
                  fen: chess.fen(),
                  orientation: this.moveData.color,
                  coordinates: false,
                  movable: { free: false, showDests: false },
                  highlight: { lastMove: true, check: true },
                })
              );
              const parsedShapes = move.shapes ? JSON.parse(move.shapes) : [];
              this.boards[index].setShapes(parsedShapes);
            } else {
              console.error(`Board element edit-board-${index} not found`);
            }
          });
        });

        // Hard force the dropdown and model to match once DOM is ready
        this.$nextTick(() => {
          this.moveData.move_groups.forEach((group, index) => {
            const select = document.querySelector(
              `#grouped-move-block-${index} select`
            );
            if (select) {
              group.shared_move_id = select.value;
            }
          });
        });
      });
    },

    //--------------------------------------------------------------------------------
    handleSaveResult(status, index) {
      const btn = document.querySelector(".icon-save");
      if (btn) {
        btn.classList.remove("save-pending");
        const className = `save-${status}`;
        btn.classList.add(className);
      }

      setTimeout(() => {
        if (status === "success") {
          window.location.reload();
        } else {
          this.markErrorBlock(`move-block-${index}`);
        }
      }, 750);
    },

    //---------------------------------------------------------------------------------
    buildPayload() {
      const payload = {
        fen: this.moveData.fen,
        san: this.moveData.san,
        color: this.moveData.color,
        shared_moves: [],
        grouped_moves: [],
      };

      payload.shared_moves = this.moveData.shared_moves.map((move, index) => {
        const boardShapes = this.boards[index].state.drawable.shapes;

        return {
          id: move.id,
          annotation: move.annotation === "none" ? "" : move.annotation,
          text: move.text.trim(),
          alt: move.alt,
          alt_fail: move.alt_fail,
          shapes: boardShapes.length > 0 ? JSON.stringify(boardShapes) : "",
        };
      });

      payload.grouped_moves = this.moveData.move_groups.map((move, index) => {
        return {
          move_ids: move.move_ids,
          shared_move_id: move.shared_move_id,
          sync: !!move.sync_shared_values_to_moves,
        };
      });

      return payload;
    },

    //--------------------------------------------------------------------------------
    async saveAll(index) {
      console.log("Saving all shared/grouped move data...");
      document.querySelector(".icon-save")?.classList.add("save-pending");

      const payload = this.buildPayload();
      console.log("Payload", payload);

      try {
        const response = await fetch("/save-shared-move/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        const data = await response.json();
        console.log("data:", data);

        if (data.status === "error") {
          this.handleSaveResult("error", index);
          return false;
        } else {
          console.log("Shared move saved successfully");
          this.handleSaveResult("success", index);
          return true;
        }
      } catch (error) {
        console.error("Error saving shared move:", error);
        this.handleSaveResult("error", index);
        return false;
      }
    },

    //--------------------------------------------------------------------------------
    buildAdminMatchingMovesLink(grouped_move = null) {
      if (grouped_move && grouped_move.move_ids && grouped_move.move_ids.length) {
        const ids = grouped_move.move_ids.join(",");
        return `/admin/chesser/move/?q=id in (${ids})`;
      }

      // fallback to regular identity filter
      const parts = [
        `fen="${this.moveData.fen}"`,
        `san="${this.moveData.san}"`,
        `variation.chapter.color="${this.moveData.color}"`,
      ];
      return "/admin/chesser/move/?q=" + encodeURIComponent(parts.join(" and "));
    },

    //--------------------------------------------------------------------------------
    buildAdminMatchingSharedMovesLink() {
      const query = `fen="${moveData.fen}" and san="${moveData.san}" and opening_color="${this.moveData.color}"`;
      return "/admin/chesser/sharedmove/?q=" + encodeURIComponent(query);
    },

    //--------------------------------------------------------------------------------
    showShapesOverlay(move) {
      this.overlayVisible = true;
      this.$nextTick(() => {
        if (!this.overlayBoard) {
          this.overlayBoard = window.Chessground(
            document.getElementById("overlay-board"),
            {
              fen: this.moveData.fen,
              orientation: this.moveData.color,
              coordinates: false,
              movable: { free: false },
              drawable: { enabled: false },
            }
          );
        } else {
          this.overlayBoard.set({
            fen: this.moveData.fen,
          });
        }
        const parsedShapes = move.shapes ? JSON.parse(move.shapes) : [];
        this.overlayBoard.setShapes(parsedShapes);
      });
    },

    //--------------------------------------------------------------------------------
    closeOverlay() {
      this.overlayVisible = false;
    },

    //--------------------------------------------------------------------------------
    markErrorBlock(blockId) {
      const block = document.getElementById(blockId);
      if (block) {
        block.classList.add("error");
        setTimeout(() => block.classList.remove("error"), 3000);
      }
    },

    // ---------------------------------------------------------
    groupedMoveSequence() {
      // they will all be the same so we'll just return the first one
      return this.moveData.move_groups.length
        ? this.moveData.move_groups[0].move_sequence
        : 0;
    },
  }; // return { ... }
}

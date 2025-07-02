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
          variation_ids: move.variation_ids,
          shared_move_id: move.shared_move_id,
          sync: !!move.sync_shared_values_to_moves,
        };
      });

      return payload;
    },

    //--------------------------------------------------------------------------------
    async saveAll(index) {
      console.log("Saving all shared/grouped move data...");
      const payload = this.buildPayload();
      console.log("Payload", payload);

      // try {
      //   const response = await fetch("/save-shared-move/", {
      //     method: "POST",
      //     headers: { "Content-Type": "application/json" },
      //     body: JSON.stringify(payload),
      //   });

      //   const data = await response.json();
      //   console.log("data:", data);

      //   if (data.status === "error") {
      //     this.handleSaveResult("error", index);
      //     return false;
      //   } else {
      //     console.log("Shared move saved successfully");
      //     this.handleSaveResult("success", index);
      //     return true;
      //   }
      // } catch (error) {
      //   console.error("Error saving variation:", error);
      //   this.handleSaveResult("error", index);
      //   return false;
      // }
    },

    //---------------------------------------------------------------------------------
    buildSharedMovePayload(index) {
      const move = this.moveData.shared_moves[index];
      const boardShapes = this.boards[index].state.drawable.shapes;

      return {
        id: move.id,
        san: this.moveData.san,
        fen: this.moveData.fen,
        color: this.moveData.color,
        annotation: move.annotation === "none" ? "" : move.annotation,
        text: move.text.trim(),
        alt: move.alt,
        alt_fail: move.alt_fail,
        shapes: boardShapes.length > 0 ? JSON.stringify(boardShapes) : "",
      };
    },

    //--------------------------------------------------------------------------------
    async saveSharedMove(index) {
      console.log("Saving shared move data...");
      const payload = this.buildSharedMovePayload(index);
      console.log("Shared move payload", payload);

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
        console.error("Error saving variation:", error);
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
        `variation.chapter.course.color="${this.moveData.color}"`,
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
    async updateGroupedMoveValues(grouped_move, index) {
      try {
        // 1️⃣ Get the current selected shared move ID
        const sharedMoveId = grouped_move.shared_move_id;

        // 2️⃣ Look up the matching shared move data in the single source of truth
        const sharedMove = this.moveData.shared_moves.find(
          (sm) => sm.id === Number(sharedMoveId)
        );

        // weird/unlikely
        if (!sharedMove) {
          console.error("No matching shared move found for ID:", sharedMoveId);
          this.markErrorBlock(`grouped-move-block-${index}`);
          return;
        }

        // 3️⃣ Build the payload from the found shared move
        const payload = {
          move_ids: grouped_move.move_ids,
          shared_move_data: {
            text: sharedMove.text,
            annotation: sharedMove.annotation,
            alt: sharedMove.alt,
            alt_fail: sharedMove.alt_fail,
            shapes: sharedMove.shapes,
          },
        };

        // 4️⃣ Send to server
        const response = await fetch("/update-grouped-move-values/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        const data = await response.json();

        if (data.status === "success") {
          window.location.reload();
        } else {
          this.markErrorBlock(`grouped-move-block-${index}`);
        }
      } catch (err) {
        console.error(err);
        this.markErrorBlock(`grouped-move-block-${index}`);
      }
    },

    //--------------------------------------------------------------------------------
    async updateSharedMoveLinkForGroup(grouped_move, index) {
      try {
        const payload = {
          move_ids: grouped_move.move_ids,
          shared_move_id: grouped_move.shared_move_id,
        };

        const response = await fetch("/update-shared-move-link/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (response.ok) {
          console.log(
            `Shared move link updated successfully to ${grouped_move.shared_move_id}`
          );
          window.location.reload();
        } else {
          console.log(
            `Error updating shared move link to ${grouped_move.shared_move_id}`
          );
          this.markErrorBlock(`grouped-move-block-${index}`);
        }
      } catch (e) {
        console.error(e);
        this.markErrorBlock(`grouped-move-block-${index}`);
      }
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

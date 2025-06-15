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
      });
    },

    //---------------------------------------------------------------------------------
    buildPayload() {
      const payload = {
        san: this.moveData.san,
        fen: this.moveData.fen,
        color: this.moveData.color,
        moves: [],
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

      return payload;
    },

    //--------------------------------------------------------------------------------
    handleSaveResult(status, index = null) {
      const btn = document.querySelector(".icon-save");
      if (btn) {
        const className = `save-${status}`;
        btn.classList.add(className);
      }

      if (status === "success") window.location.reload();
    },

    //--------------------------------------------------------------------------------
    async saveSharedMove(index) {
      console.log("Saving shared move data...");
      const payload = this.buildPayload();

      try {
        const response = await fetch("/save-shared-move/", {
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
          console.log("Shared move saved successfully");
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
  }; // return { ... }
}

import { Chessground } from "../chessground/chessground.min.js";
import { Chess } from "../chessjs/chess.js";

window.Chessground = Chessground;
window.Chess = Chess;

export function editApp() {
  return {
    boards: [],
    chess: null,
    variationData: variationData,
    moveData: moveData,
    currentMoveIndex: 0,

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
        variation_id: this.variationData.variation_id,
        title: this.variationData.title,
        start_move: this.variationData.start_move, // TODO: validation?
        moves: [],
      };

      payload.moves = this.variationData.moves.map((move, index) => {
        const boardShapes = this.boards[index].state.drawable.shapes;
        const state = this.moveState[index] || {};

        return {
          san: move.san,
          shared_move_id: move.shared_move_id,
          annotation: state.annotation === "none" ? "" : state.annotation,
          text: state.text.trim(),
          alt: state.alt,
          alt_fail: state.alt_fail,
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
    buildAdminMatchingLink(move) {
      if (!move?.fen || !move?.san || !this.variationData?.color) return "#";

      const query = `fen="${move.fen}" and san="${move.san}" and variation.chapter.course.color="${this.variationData.color}"`;
      return "/admin/chesser/move/?q=" + encodeURIComponent(query);
    },
  }; // return { ... }
}

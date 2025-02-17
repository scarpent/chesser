import { Chessground } from "https://cdn.jsdelivr.net/npm/chessground@9.1.1/dist/chessground.min.js";
import { Chess } from "https://cdn.jsdelivr.net/npm/chess.js@1.0.0/dist/esm/chess.js";

window.Chessground = Chessground;
window.Chess = Chess;

export function editApp() {
  return {
    boards: [],
    chess: null,
    variationData: variationData,

    initEditor() {
      console.log("initEditor()");
      document.addEventListener("alpine:initialized", () => {
        console.log("Alpine initialized");
        const chess = new window.Chess();

        this.$nextTick(() => {
          console.log("Running after DOM update");
          this.variationData.moves.forEach((move, index) => {
            const boardElement = document.getElementById(`edit-board-${index}`);
            if (boardElement) {
              const moveResult = chess.move(move.san);
              move.fen = chess.fen();
              this.boards.push(
                window.Chessground(boardElement, {
                  fen: chess.fen(),
                  orientation: this.variationData.color,
                  draggable: false,
                  coordinates: false,
                  movable: { free: false, showDests: false },
                  highlight: { lastMove: true, check: true },
                  lastMove: [moveResult.from, moveResult.to],
                })
              );
            } else {
              console.error(`Board element edit-board-${index} not found`);
            }
          });
          console.log("All boards initialized", this.boards);
        });
      });
    },

    //--------------------------------------------------------------------------------
    saveVariation() {
      console.log("Saving variation data...", this.variationData);
      console.log(this.variationData.start_move);
      this.saveErrors = [];
      const payload = {
        variation_id: this.variationData.variation_id,
        title: this.variationData.title,
        start_move: this.variationData.start_move,
      };

      payload.moves = this.variationData.moves.map((move) => ({
        san: move.san,
        annotation: move.annotation,
        text: move.text,
        alt: move.alt,
        alt_fail: move.alt_fail,
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
  }; // return { ... }
}

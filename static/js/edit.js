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
          // Waits for DOM update to complete
          this.variationData.moves.forEach((move, index) => {
            const boardElement = document.getElementById(`edit-board-${index}`);
            if (boardElement) {
              const moveResult = chess.move(move.san);
              move.fen = chess.fen();
              this.boards.push(
                window.Chessground(boardElement, {
                  fen: chess.fen(),
                  orientation: this.variationData.color,
                  coordinates: false,
                  movable: { free: false, showDests: false },
                  highlight: { lastMove: true, check: true },
                  lastMove: [moveResult.from, moveResult.to],
                  drawable: { shapes: move.shapes },
                })
              );
            } else {
              console.error(`Board element edit-board-${index} not found`);
            }
          });
          // console.log("All boards initialized", this.boards);
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
        start_move: this.variationData.start_move,
      };

      payload.moves = this.variationData.moves.map((move, index) => ({
        san: move.san,
        annotation: move.annotation === "No annotation" ? "" : move.annotation,
        text: move.text,
        alt: move.alt, // TODO: validation here and/or on backend;
        alt_fail: move.alt_fail, // don't let your data get into a bad state!
        shapes: JSON.stringify(this.boards[index].state.drawable.shapes),
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

      const altMoves = alternateMoves
        .split(",")
        .map((m) => m.trim())
        .filter((m, i, arr) => m && arr.indexOf(m) === i); // Remove duplicates
      const bad = [],
        good = [];

      const chess = new window.Chess();
      for (let i = 0; i < index; i++) chess.move(this.variationData.moves[i].san);

      altMoves.forEach((altMove) => {
        if (!altMove || altMove === actualSan) {
          bad.push(altMove);
          return;
        }
        try {
          chess.move(altMove);
          good.push(altMove);
          chess.undo();
        } catch (error) {
          bad.push(altMove);
        }
      });

      console.log("good/bad", good, bad);
      if (bad.length)
        console.error(
          `❌ Invalid alt moves for ${actualMoveVerbose} ➤ ${bad.join(", ")}`
        );

      this.variationData.moves[index][field] = good.join(", ");
    },
  }; // return { ... }
}

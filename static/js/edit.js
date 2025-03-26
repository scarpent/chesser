import { Chessground } from "../chessground/chessground.min.js";
import { Chess } from "../chessjs/chess.js";

window.Chessground = Chessground;
window.Chess = Chess;

export function editApp() {
  return {
    boards: [],
    chess: null,
    variationData: variationData,

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
  }; // return { ... }
}

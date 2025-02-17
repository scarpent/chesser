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
  };
}

## notes...

Looks like chessable getReview endpoint holds spaced repetition "level" data

https://www.chessable.com/api/v1/getReview?uid=118804&bid=51617&lid=23&oid=39269901

lesson, moves,

there is level_b and level_b_origin, where both seem to be the same (tbd: if that's for black specifically)
level_origin is 0

e.g. for above, had +60 on moves which was 6. Overstudied moves had higher numbers, up to +12 in some cases, which would be +120? Is it just level \* 10?

although +60 is really "level 3"
+60 level_b 6

another (white) alapin 2...d5
dxc5 +60 (level_b for white, too)

another (and hope for something other than +60)
Be7 +50
a6 +50
Qa5 +50 level_b = 5

another (a rare case of two numbers!)
Qd7 +160
Nc6 +160 level_b = 16
Ke7 +150 level_b = 15

Qa5+ +40 level_b = 4

## how to embed information in variation info

Search for this prompt in chesser conversation:

I'm not looking for code now but just thinking about how to present the variation view. I'm going to need clickable moves for both the mainline and subvariations. Here's how chessable looks for an example. I'm going to want to navigate through these using buttons and left/right keyboard keys. When a move is reached/selected, it should be highlighted. Since there is a lot of logic around how to construct this, I'm considering building all the html on the backend. What do you think about that?

```html
<span
  class="move"
  data-fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR_b_KQkq_-_0_1"
  >1. e4</span
>

<div id="moves">
  <span class="move mainline-move" data-fen="fen1" data-index="0">1. e4</span>
  <span class="move mainline-move" data-fen="fen2" data-index="1">1... e5</span>
  <span class="move mainline-move" data-fen="fen3" data-index="2">2. Nf3</span>
  <span class="move subvariation-move" data-fen="fen4" data-index="0"
    >2... Nc6</span
  >
  <span class="move mainline-move" data-fen="fen5" data-index="3">3. d4</span>
</div>
```

```css
.move.highlight {
  background-color: #4444aa; /* Example highlight color */
  color: white;
}
```

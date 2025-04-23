## notes...

@@StartBracket@@ @@EndBracket@@
Don't use these -- just put () inside {()}

## todo

variations 778, 1215

- refactor css styles
  ~ create "stylesheet" with samples

- add next review date form input for clone? Or continue using end of time...
- add move normalizer from schess (regex version?) - use it on clone moves string
- 404 page that has buttons... (just the course/castle buttons?)
- use reambiguated moves to check alts, too?
- a way to have "shared reference" moves (share shapes, alts, etc)
  ~ perhaps a checkbox next to the large move number, "use standard ref"
  ~ if clicked and there isn't one, it will use the current text/shapes/alt to create it
  ~ if there is an existing one, show all of its info instead (old move should be untouched, can toggle back to it)
- link to source variation from quiz info? Just one link to the original source var.

## longer term:

- ways to smooth out upcoming reviews
- redistribute related openings so they come more regularly
  - some way to select various openings for this
- an extra study feature for studying level 1 openings or level 1 & 2, etc

## if shared publicly...

- data migration for courses 1, 2
- create bulk import with examples from https://en.wikibooks.org/wiki/Chess_Opening_Theory/1._d4/1...d5/2._c4/2...e6/3._Nf3 can have 10-30 examples with text and demonstrating various features (fenseq, blockquote, source, etc, can demonstrate the source json field to credit wikibooks!) - use separate json and license file
- make sure to use nh3 for sanitizing html!
- might mention that cookies/local storage are either essential or non-PII?
  ~ potentially: Privacy Notice: Chesser uses essential cookies for login and session protection. It also stores non-identifiable progress data locally in the browser for review sessions. No personal data is shared or tracked.

- credit/attributions
  ~ python/django
  ~ chessground and other chess libraries
  ~ alpine
  ~ emoji/images/fonts/etc
  ~ wikibooks openings

## lichess analysis FEN links

### variation.html

```html
<button
  title="Lichess analysis board"
  @click="window.open('https://lichess.org/analysis/standard/' + board.state.fen.replace(/ /g, '_') + '?color=' + variationData.color, '_blank')"
  class="icon-analysis icon-button"
></button>
```

### review.html

```html
<button
  title="Lichess analysis board"
  @click="window.open('https://lichess.org/analysis/standard/' + chess.fen().replace(/ /g, '_') + '?color=' + variationData.color, '_blank')"
  class="icon-analysis icon-button"
></button>
```

### edit.html

```html
<div class="move-fen">
  <a
    :href="'https://lichess.org/analysis/standard/' + move.fen.replace(/ /g, '_') + '?color=' + variationData.color"
    target="_blank"
    x-text="move.fen"
  ></a>
</div>
```

## js libraries

```js
import { Chessground } from "https://cdn.jsdelivr.net/npm/chessground@9.1.1/dist/chessground.min.js";
import { Chess } from "https://cdn.jsdelivr.net/npm/chess.js@1.0.0/dist/esm/chess.js";

import { Chessground } from "../chessground/chessground.min.js";
import { Chess } from "../chessjs/chess.js";

<script
    defer
    src="https://cdn.jsdelivr.net/npm/alpinejs@3.13.5/dist/cdn.min.js"
></script>

<script defer src="{% static 'alpine/cdn.min.js' %}"></script>
```

## getGame

has most things: mainline moves, text, alt moves, and draws

getGame endpoint has lastReviewed/lastUpdated info, but thankfully
we can get this in bulk instead from courseExplorerData

## courseExplorerData

https://www.chessable.com/api/v1/courseExplorerData?bid=51617

this might have what we need...

result ➤ futureReviews
lastUpdated
nextUpdated
oid

nextUpdated is next review due

## getReview

can you only call this on variations that are up for review?

Looks like chessable getReview endpoint holds spaced repetition "level" data

https://www.chessable.com/api/v1/getReview?uid=118804&bid=51617&lid=23&oid=39269901
bid = course
oid = variation

lesson ➤ moves ➤

there is level_b and level_b_origin, where both seem to be the same (\_b has nothing to do with black?)
level_origin is 0

level or level_b can be null or not alternatively -- just use one that is there?

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

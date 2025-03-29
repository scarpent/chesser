## notes...

pgn-safe parens
@@StartBracket@@ @@EndBracket@@
This ⸨is⸩ a test. ⸨This might be best?⸩

## future credit/attributions if open-sourced

- python/django
- chessground and other chess libraries
- alpine
- emoji/images/fonts/etc

## todo

- fix button/click subvar nav
  - left/right buttons not navigating when in subvar?
  - clicking on subvar moves causes the board to first show mainline move and then the subvar, which is jarring
- when going from review/variation to edit, scroll to edit board for that move? maybe if it's later than move 4, so most variations will start at the top
- use reambiguated moves to check alts, too?
- import new lines (manage re-imports for different sets?)
  - maybe try to fix data in place with scripts rather than re-import...
- sort dumpdata output for git check in and diff checking?
- toggle show alt moves on board with a key, say "a" will show them only while holding, then restore other paint or clear
- decide where to do different cleanup/html stuff (e.g. when making the import json or when importing)
- a way to have "shared reference" moves? (share shapes, alts, etc)
- version number for variations? (version 1 is overwritable)
- link to source variation from quiz info? Just one link to the original source var.
- style form components
- turn apple emoji into button graphics?
- a way to send move string to lichess?

## longer term:

- ways to smooth out upcoming reviews
- redistribute related openings so they come more regularly
  - some way to select various openings for this
- an extra study feature for studying level 1 openings or level 1 & 2, etc

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

## notes...

## todo

- toggle show alt moves on board
  - holding down "a" will show them only while holding, then restore other paint or clear
- decide where to do different cleanup/html stuff (e.g. when making the import json or when importing)
- a way to have "shared reference" moves?
- set up railway.app account
- work on django db export/import from sqlite <==> postgres
- work out variation mobile view (stack things: board, buttons, text, other stuff)

longer term:

- ways to smooth out upcoming reviews
- redistribute related openings so they come more regularly

## db import/export

```sh
./manage.py dumpdata chesser --indent 4 --output temp.json --verbosity 1
./manage.py loaddata temp.json
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

getGame endpoint has lastReviewed/lastUpdated info; lastReviewed will be needed along with levels from getReview, in order to set review dates

has most things: mainline moves, text, alt moves, and draws

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

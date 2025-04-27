# header 1

## header 2

### header 3

### Thank you / Attribution

- python/django
- python-chess
- chessground
- chess.js
- alpine
- googlefonts/noto-emoji OFL-1.1
  ~ Emoji icons derived from Noto Emoji, licensed under the SIL Open Font License, Version 1.1.
- wikibooks openings
- "fantasy" piece set for queen logo
  ~ https://github.com/maurimo/chess-art
  ~ https://maurimo.github.io/chess-art/configure.html
  ~ (remember to send note to the author)

## notes...

@@StartBracket@@ @@EndBracket@@
Don't use these -- just put () inside {()}

## todo

`get_simple_move_parsed_block`

- export link from variations table! 📦️

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

## Service Workers

Situation | What Happens
Restart Django server (new deploy) | A new BUILD_TIMESTAMP is generated
Browser loads /service-worker.js?v=newtimestamp | Browser fetches the new service worker
New service worker installs immediately (skipWaiting) | ✅ No "waiting" phase — it activates right away
During activate event | ✅ Old caches are cleaned (except current chesser-cache)
clients.claim() after activate | ✅ New service worker takes control of all open tabs immediately

See browser dev tools ➤ application ➤ (manifest, service workers, storage)

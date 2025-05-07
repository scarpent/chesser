# Chesser

Single user Django web application for managing chess opening
repertoire and practicing with spaced repetition.

It's meant to be simple/fun to work on, using a sqlite db locally,
simple alpine.js setup with no building, and it's easily deployed.
(I use [railway app](https://railway.com/).)

## Thank you / Attribution

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

## Chessable

### getGame

has most things: mainline moves, text, alt moves, and draws

getGame endpoint has lastReviewed/lastUpdated info, but thankfully
we can get this in bulk instead from courseExplorerData

### courseExplorerData

https://www.chessable.com/api/v1/courseExplorerData?bid=51617

result ➤ futureReviews
lastUpdated
nextUpdated
oid

nextUpdated is next review due
(variations not due don't show up here?)

## Service Workers

Situation | What Happens
Restart Django server (new deploy) | A new BUILD_TIMESTAMP is generated
Browser loads /service-worker.js?v=newtimestamp | Browser fetches the new service worker
New service worker installs immediately (skipWaiting) | ✅ No "waiting" phase — it activates right away
During activate event | ✅ Old caches are cleaned (except current chesser-cache)
clients.claim() after activate | ✅ New service worker takes control of all open tabs immediately

See browser dev tools ➤ application ➤ (manifest, service workers, storage)

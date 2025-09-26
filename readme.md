![chesser course covers](docs/images/ice-cream-castles-in-the-sky.png)

# Chesser

A web application for managing your chess opening repertoire and
practicing with spaced repetition.

It's meant to be simple/fun to work on, using a sqlite db locally,
simple alpine.js setup with no build step, and it's easily deployed.
(I use [railway app](https://railway.com/).)

re: gamification

simplicity...

## Bullet Points

- single user -- use it as is or become the lichess chessable...
- responsive -- mobile is tuned to my device but hoping it will be generally reasonable

## "Issues"

(Maybe create actual issues in github?)

- Mobile: Restart/Show move buttons stay highlighted
- Mobile: Scroll to top on edit screen
- Auto reload _mostly_ happens, but not always (but works sorta well and not worth more effort)

## Open / ToDo

Things I'd be willing to work on if important to actual users of the app:

- A light mode (at least, I can see refactoring CSS to better support variables and customization)
- PGN import (I import from stuff I extracted from chessable and haven't worked with PGN examples, but would like to make this as robust as possible.)
- Subvariation rendering: The parser/renderer can be extended to do more. I expected it to do more but I'm happy with the current state of things. I didn't find more patterns from my chessable data to automate more things -- I'd rather manually fix at this point. HOWEVER, if others can show samples of a recurring pattern I'd be curious to see about handling it.

## Thank you / Attribution

Some of the great free software libraries and resources that made chesser possible:

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

## Service Workers

Situation | What Happens
Restart Django server (new deploy) | A new BUILD_TIMESTAMP is generated
Browser loads /service-worker.js?v=newtimestamp | Browser fetches the new service worker
New service worker installs immediately (skipWaiting) | ✅ No "waiting" phase — it activates right away
During activate event | ✅ Old caches are cleaned (except current chesser-cache)
clients.claim() after activate | ✅ New service worker takes control of all open tabs immediately

See browser dev tools ➤ application ➤ (manifest, service workers, storage)

# Chesser

![chesser course covers](docs/images/ice-cream-castles-in-the-sky.png)

A web application for managing your chess opening repertoire and
practicing with spaced repetition.

This is a _hobby_ project. It's a single user application, with white and black repertoires organized by chapters. (At one time it had a course model but I took
that out to keep it simple.)

It's meant to be simple/fun to work on, using a sqlite db locally,
a simple alpine.js setup with no build step, and it's easily deployed.
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

<a id="home-page"></a>

## Home Page

| UI Element                                       | What It Is                                                       |
| ------------------------------------------------ | ---------------------------------------------------------------- |
| ![Chesser](docs/images/chesser-logo-32.png)      | _Logo_ always returns to root homepage.                          |
| ![White Castle](docs/images/castle-white-32.jpg) | _White Book:_ Homepage showing white repertoire chapters.        |
| ![Black Castle](docs/images/castle-black-32.jpg) | _Black Book:_ Same for black repertoire.                         |
| ![Stats](docs/images/noto-32/stats.png)          | _Stats_ for reviews: daily, weekly, etc.                         |
| ![Review](docs/images/noto-32/review.png)        | _Review:_ Start/continue quiz session for currently due reviews. |
| ![Import](docs/images/noto-32/import.png)        | _Import (and Export)_ via miscellaneous formats.                 |
| ![Random](docs/images/noto-32/random.png)        | _Random Review:_ “Extra study” review chosen at random.          |
| ![Puzzles](docs/images/noto-32/puzzles.png)      | _Puzzles:_ Open lichess puzzle training page.                    |
| (text link)                                      | _Admin:_ Open Django admin. (Unavailable in demo mode.)          |

<a id="review-page"></a>

## Review Page

| UI Element                                      | What It Is                                                           |
| ----------------------------------------------- | -------------------------------------------------------------------- |
| ![Home](docs/images/chesser-logo-32.png)        | _Home:_ Return to homepage.                                          |
| ![Restart](docs/images/noto-32/restart.png)     | _Restart_ current variation review. (Resets failure state.)          |
| ![Show Move](docs/images/noto-32/showmove.png)  | _Show Move:_ Reveal correct move. (Fails quiz unless restarted.)     |
| ![Info](docs/images/noto-32/info.png)           | _Variation Info:_ Toggle variation details.                          |
| ![Variation](docs/images/noto-32/variation.png) | _View:_ Open full variation view. (“Book” view.)                     |
| ![Edit](docs/images/noto-32/edit.png)           | _Edit:_ Open variation editor.                                       |
| ![Analysis](docs/images/noto-32/analysis.png)   | _Analysis:_ Open line in Lichess analysis board at the current move. |
| 🟢🟡🔴                                          | TBD (To Be Documented)                                               |

### Review Completion Toolbar

|                                             |                                                                        |
| ------------------------------------------- | ---------------------------------------------------------------------- |
| ![Back](docs/images/noto-32/back.png)       | _Mainline Back:_ Step backward through the variation. (Arrow Left.)    |
| ![Forward](docs/images/noto-32/forward.png) | _Mainline Forward:_ Step forward through the variation. (Arrow Right.) |
| 🟢🔴🔰🌿😬, etc.                            | _Status:_ Result of the review.                                        |
| ![Review](docs/images/noto-32/review.png)   | _Review:_ Start/continue quiz session for currently due reviews.       |

Review session stats are somewhat sticky. You can leave an active session and come back and it will resume if “not too much” time has passed.

“Extra study” text will be red if initiated from failed quiz, green otherwise.

## Service Workers

```
Situation | What Happens
Restart Django server (new deploy) | A new BUILD_TIMESTAMP is generated
Browser loads /service-worker.js?v=newtimestamp | Browser fetches the new service worker
New service worker installs immediately (skipWaiting) | ✅ No "waiting" phase — it activates right away
During activate event | ✅ Old caches are cleaned (except current chesser-cache)
clients.claim() after activate | ✅ New service worker takes control of all open tabs immediately

See browser dev tools ➤ application ➤ (manifest, service workers, storage)
```

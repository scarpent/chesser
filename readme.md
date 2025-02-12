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

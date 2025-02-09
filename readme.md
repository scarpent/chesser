## have "levels" for spaced repetition:
* -1: "not learned" (but can be scheduled for first time)
* 0: missed last time, scheduled for 4 hours after
* 1: 1-day
* 2: 3-day
* etc...

## a couple of different ways to see alt moves:

```
# quiz
"alt": ["Nc3"],
"alt_fail": ["d4"],

# review, use the values to assign annotations to rank them? A, B, C
"alt": {"Nc3": 1},
"alt_fail": {"d4": 2},
```

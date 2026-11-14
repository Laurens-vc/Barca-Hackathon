# More than a Hack 2027: our possession model

This is our team's entry for Phase 1 of [More than a Hack 2027](https://github.com/metrica-sports/more-than-a-hack-2027), organised by Metrica Sports, FC Barcelona and Mobile World Capital. The task is to say, for every frame of FC Barcelona vs Athletic Club, which team has the ball (`H` home, `A` away) or whether the ball is dead (`D`).

The official challenge documents are unchanged in this repo. `OFFICIAL_README.md` is the original README, and CHALLENGE, DATA, EVALUATION, SUBMISSION and RULES are next to it. Our own code is in `solution/`.

## How it works

This is a rule-based state machine on the provided tracking data. There is no training, and no labels from this game are used.

1. **Ball cleaning.** Gaps of up to 0.5 s in the ball track are filled with a straight line. Longer gaps stay empty.
2. **Dead ball.** The ball is dead when it is more than 0.5 m over a line, or when play has visibly stopped: the median player speed is under 1.3 m/s and the ball is resting or unseen for at least 1.5 s. A dead stretch ends at the restart, which is the first kick or throw faster than 5 m/s. Metrica's automatic set-piece tags fill in stoppages the tracking misses.
3. **Possession.** A *touch* is a run of frames where one team is clearly nearest the ball: within 2 m, and at least 0.75 m closer than the nearest opponent. Possession only changes hands on *control*, meaning a touch of at least 0.5 s or two touches in a row by the new team within 4 s (a pass). Brief touches, deflections and duels leave possession where it was, so a loose ball stays with the last team, as CHALLENGE.md defines it.

Every threshold is in `solution/possession.py` with the reason for it. None was fitted to the public 5-minute ground truth. That window is used only to check that frames line up and the file is valid (RULES.md).

## Reproduce the submission

You need Python 3.9 or newer and the match data bundle. The data is gated, so see DATA.md. It is never committed to this repo.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-frozen.txt
# put the data in data/tactical/ and data/broadcast/ (see data/README.md)
.venv/bin/python solution/run.py --team <TeamName>        # -> submissions/<TeamName>.csv
.venv/bin/python evaluation/validate_submission.py submissions/<TeamName>.csv
```

On Windows, use `.venv\Scripts\python` instead of `.venv/bin/python`.

The first run parses the tracking file once and caches it in `data/cache/`, which git ignores. Later runs take a few seconds. The output is deterministic, so the same data always gives the same file.

## Files

| path | what |
|---|---|
| `solution/load.py` | reads the tracking and the set-piece tags into numpy arrays |
| `solution/possession.py` | the method: ball cleaning, dead ball, touches, possession |
| `solution/run.py` | builds the submission CSV and prints a summary |
| `evaluation/` | the official scorer, unchanged |
| `games.py`, `starter/` | the official helpers, unchanged |

## Licence

The official code and docs are MIT-licensed by Metrica Sports (see LICENSE). Our additions in `solution/` are under the same licence. The match data is not covered and is not in this repo.

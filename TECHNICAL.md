# Possession Is Nine: technical document

More than a Hack 2027, Phase 1: ball possession. FC Barcelona vs Athletic Club.

Repository: https://github.com/Laurens-vc/Barca-Hackathon
Submission file: `Possession Is Nine.csv`, produced by `solution/run.py`

## 1. Approach

We built a rule-based state machine on the provided automatic tracking. It has no learned model and no training data.

We chose rules over a learned model for three reasons:

- **No labels to learn from.** The only labelled data for this match is the public 5-minute window, and the rules forbid training or tuning on it. Hand-labelling another match was not realistic in the time available.
- **The ranking metric rewards structure, not per-frame accuracy.** spellF1 scores whole possessions, so the main risk is splitting one real possession into many fragments. A state machine with an explicit "possession only changes on control" rule addresses that directly. A per-frame classifier, even with smoothing, does not.
- **The challenge defines possession in rule terms.** "Possession stays with the last team while the ball is loose" and "a touch without control is not a change" translate one to one into states and transitions.

The pipeline has three stages.

**Stage 1: ball cleaning.** Gaps in the ball track of up to 0.5 s are filled by linear interpolation. Longer gaps are left empty, because at 25 fps a ball can travel 10 to 15 m unseen in a second.

**Stage 2: dead ball.** A frame is dead ball when either:

- **(a) The ball is out.** The ball is more than 0.5 m beyond a touchline or goal line. Dead ball then lasts until the restart.
- **(b) Play has visibly stopped.** The median speed of all tracked players, averaged over 2 s, is below 1.3 m/s, and the ball is resting (under 1 m/s) or not visible, for at least 1.5 s.

A dead stretch ends at the restart. We define the restart as the first frame where the ball is visible, on the pitch, and moving faster than 5 m/s: a kick or a throw, faster than any player carries the ball.

Where neither signal fires, Metrica's automatic Smart Tagging SET PIECES intervals are used as a fallback. The tagged window contains the restart, so the part of the window before the restart kick is marked dead.

Finally, live gaps shorter than 1 s between two dead stretches are closed, because they are tracking flicker.

**Stage 3: possession inside each live stretch.**

- **Touch.** A frame counts towards a touch for team T when the ball is within 2.0 m of T's nearest tracked player and at least 0.75 m closer to that player than to the nearest opponent. Anything closer than that margin is a duel and belongs to neither team. A touch is a run of at least 3 such frames, with gaps of up to 2 frames bridged.
- **Start of a live stretch.** The team of the first touch has possession from the restart onward, because after every stoppage there is a clear possessor.
- **Change of possession.** Possession moves to the other team only on control, meaning either:
  - a single touch of at least 0.5 s, or
  - two consecutive touches by the new team within 4 s with no opposing touch in between, which is a completed pass.
- **When the change starts.** The new possession starts at the start of the controlling touch, not at the moment it is confirmed. This avoids systematic lateness, which spellF1 penalises heavily: a possession 1 s late scores about 0.65 instead of 1.
- **Loose balls.** Brief touches, deflections, duels and frames without a visible ball leave possession where it was.

Frames outside the two halves (before kickoff, halftime, after the final whistle) are written as `X`.

## 2. Assets used

| asset | used? | how |
|---|---|---|
| Tactical ATD (players and ball) | yes | everything in stages 1 to 3 |
| Tactical Smart Tagging | yes | SET PIECES intervals as a dead-ball fallback (stage 2) |
| Tactical homography | no | the ATD is already in pitch coordinates. The homography would only matter if we built our own detection from the video. |
| Tactical video | no | used neither as input nor for labelling |
| Broadcast ATD, homography and video | no | not synchronised to the tactical timeline. We used the broadcast ATD only as a smoke test that the code runs on a second file of the same format. |

Smart Tagging phase codes with a team tag (BUILD UP, PROGRESSION and others) are not used yet. See section 5.

## 3. Training data

None. The method has no trainable parameters.

The thresholds were set from football and tracking reasoning, and each one is documented next to its value in `solution/possession.py`. No labels of any kind on the provided match were used to train, tune or select the method. The public 5-minute ground truth was used only to check that frames are aligned and that the file is valid.

## 4. Possession rules implemented

| situation | our rule |
|---|---|
| loose ball, contested ball | possession stays with the last team that had it |
| single touch without control, deflection | not a change. A touch under 0.5 s that is not followed by a second touch by the same team does not flip possession |
| aerial duel won without control | not a change, by the same rule. The tracked ball position is projected to the ground, so headers rarely produce a long touch |
| interception | a change if the intercepting team keeps the ball 0.5 s or plays it on to a teammate within 4 s |
| ball out of play | `D` from the frame the ball crosses the line until the restart kick or throw |
| foul, offside, injury, goal | `D` when players visibly stop and the ball rests, until the restart |
| restart | the team that touches the ball first after a stoppage has possession from the restart |
| ball not visible | keep the current team. On the ranking metric this is the same as abstaining inside a possession |
| dead-ball ownership | not predicted. Dead ball is always `D`, as the challenge asks |

## 5. Limitations and what we would do next

**The ball is missing on 41% of graded frames, in long stretches.** The ball track drops out 186 times, for about 18 s on average. Only 39 of those gaps are short enough to interpolate. During a long gap we hold the last team, so a possession change that happens while the ball is invisible is detected late or not at all, and a stoppage during a gap is found only if players visibly stop.

**Possessions are probably too short over the full match.** We produce 446 possessions with a mean of 8.9 s, and 134 of them are shorter than 3 s. The public window's true possessions last 14.2 s on average, which suggests some over-splitting in parts of the match we cannot check. Likely causes:

- **Balls in the air.** The ground-projected ball passes near players it never touches, which creates false touches.
- **Identity switches and duplicated tracks** near the ball.
- **Restarts.** A restart is sometimes confirmed by a different team than the one that took it.

**Fouls and offsides are the weakest dead-ball case.** Players do not always slow down immediately, so the start of the stoppage can be late.

**Next steps, in order of expected value:**

1. Use Smart Tagging phases with a team tag (BUILD UP, PROGRESSION, BALL IN FINAL THIRD) as evidence for the possessing team during long ball-invisible stretches.
2. Detect aerial balls from ball speed and trajectory, and ignore touches while the ball is airborne.
3. Require a minimum possession length after a stoppage, so a restart cannot be flipped by one noisy frame.
4. Use team shape as a possession signal when the ball is invisible. The attacking team spreads out and pushes up, and the defending team compacts, which is visible in the ATD without the ball.

## 6. Reproduction

Requirements: Python 3.9 or newer, numpy and pandas (pinned in `requirements-frozen.txt`), and the official data bundle unpacked into `data/` as described in DATA.md.

```bash
git clone https://github.com/Laurens-vc/Barca-Hackathon.git
cd Barca-Hackathon
python3 -m venv .venv
.venv/bin/pip install -r requirements-frozen.txt
# unpack the data bundle into data/tactical/ (see data/README.md)
.venv/bin/python solution/run.py --team "Possession Is Nine"
.venv/bin/python evaluation/validate_submission.py "submissions/Possession Is Nine.csv"
```

A full run takes about 5 seconds on a laptop. The parsed tracking is cached in `data/cache/`, which git ignores. The method is deterministic: the same data produces the same file, byte for byte.

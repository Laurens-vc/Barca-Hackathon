# Onboarding

Welcome to the team. This page gets you from zero to a scored submission on your own laptop in about 20 minutes.

## 1. What we are doing

For each of the 199,319 frames of the FC Barcelona vs Athletic Club video, we say who has the ball: `H` (Barça), `A` (Athletic) or `D` (dead ball). We are ranked on **spellF1**, which counts how many *whole possessions* we get right. Splitting one real possession into many little ones is the most expensive mistake. The baseline to beat is **0.2433**.

**Deadline: Tuesday 17 November 2026, 23:59 CET.** Laurens submits through the form.

Read these, in this order (about 30 minutes in total):
1. `OFFICIAL_README.md`: the challenge on one page
2. `EVALUATION.md`: how scoring works, and why per-frame accuracy is the wrong thing to chase
3. `RULES.md`: especially the rule below
4. `README.md`: our method

## 2. The one rule that can disqualify us

- **No hand labelling of this match, in any form.** Don't write down who has the ball from watching the video. Don't hand-correct the tracking. Don't hard-code anything tied to specific frames.
- **Don't tune on the public 5 minutes.** `evaluation/gt/` holds a 5-minute ground truth, and it's only for checking that the pipeline works. If you change a threshold, the reason has to be football or tracking logic, not "it scored better on the 5 minutes".
- **Never commit the data.** It is licensed to us only, and this repo will be public. `.gitignore` already blocks `data/`. Don't move data files anywhere else in the repo.

## 3. Set up

```bash
git clone https://github.com/Laurens-vc/mtah2027-possession.git
cd mtah2027-possession
python3 -m venv .venv
.venv/bin/pip install -r requirements-frozen.txt
.venv/bin/python evaluation/run_evaluation.py        # scores the 4 official baselines, works without data
```

On Windows, use `.venv\Scripts\python` instead.

## 4. Get the data

The data is shared through the Google Drive folder "More Than A Hack 2027 - Initial Challenge". Ask Laurens to share it with you if you can't see it. Download these files into these folders, and don't rename them:

```
data/tactical/   BAR-ATH_tactical_atd.txt, _atd.xml, _homography.csv, _smart_tagging.xml  (+ .mp4 if you want to watch)
data/broadcast/  optional, not needed for the current method
```

## 5. Run it

```bash
.venv/bin/python solution/run.py --team test
.venv/bin/python evaluation/validate_submission.py submissions/test.csv
cp submissions/test.csv evaluation/results/ && .venv/bin/python evaluation/run_evaluation.py
```

The last command puts our file on the scoreboard next to the baselines (public 5 minutes only, so treat it as a sanity check, not a verdict).

## 6. How to contribute

- Work on a branch, then open a pull request to `main`: `git checkout -b my-idea`, then commit, then `git push -u origin my-idea`.
- Thresholds live at the top of `solution/possession.py`. Each one has a comment saying why it has that value. Keep doing that.
- Good open questions:
  - **Dead ball.** Better detection of fouls and offsides, where the ball is still on the pitch but play has stopped.
  - **Aerial balls.** The tracked ball position is wrong when the ball is in the air. Can its speed or its arc tell us that?
  - **Smart Tagging.** Phases like BUILD UP or PROGRESSION carry a team. Could they settle long stretches where the ball is invisible?
  - **Technical document.** A few pages explaining the method. SUBMISSION.md lists what it must cover.

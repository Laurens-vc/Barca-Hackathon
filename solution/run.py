"""Build the submission file from the provided data.

    python solution/run.py --team <TeamName>             # writes submissions/<TeamName>.csv
    python solution/run.py --source broadcast             # smoke test on the broadcast tracking

Deterministic: same data in, same file out.
"""

import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from games import GAME, GAMES, half_video_blocks  # noqa: E402
from load import load_set_pieces, load_tracking  # noqa: E402
from possession import predict, runs  # noqa: E402


def summary(labels, fps=25):
    graded = labels != "X"
    poss = [(a, b) for lab in "HA" for a, b in runs(labels == lab)]
    dur = [(b - a) / fps for a, b in poss]
    counts = {l: int(np.sum(labels == l)) for l in "HADX"}
    print("labels  H {H}  A {A}  D {D}  X {X}".format(**counts))
    print("possessions {}   mean {:.1f} s   median {:.1f} s   dead share {:.1%}".format(
        len(poss), np.mean(dur) if dur else 0, np.median(dur) if dur else 0,
        counts["D"] / max(1, graded.sum())))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--team", default="submission", help="team name, used as the file name")
    p.add_argument("--source", default="tactical", choices=["tactical", "broadcast"])
    p.add_argument("--out", default=os.path.join(ROOT, "submissions"))
    args = p.parse_args()

    trk = load_tracking(args.source)
    pitch = GAMES[GAME]["pitch"]
    if args.source == "tactical":
        blocks = [(lo, hi) for _, lo, hi in half_video_blocks(GAME)]
        set_pieces = load_set_pieces()
    else:
        # broadcast has no published half boundaries; treat it as one block (smoke test only)
        blocks = [(0, trk["n_frames"] - 1)]
        set_pieces = []

    labels = predict(trk, pitch, blocks, set_pieces)
    summary(labels)

    os.makedirs(args.out, exist_ok=True)
    name = args.team if args.source == "tactical" else "{}_broadcast_smoketest".format(args.team)
    path = os.path.join(args.out, name + ".csv")
    with open(path, "w") as h:
        h.write("frame,label\n")
        h.writelines("{},{}\n".format(i, l) for i, l in enumerate(labels))
    print("wrote", os.path.relpath(path, ROOT))


if __name__ == "__main__":
    main()

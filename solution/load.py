"""Read the ATD tracking into numpy arrays, fast, and cache the result.

The raw line format is "<frame_id>:<x,y,s>;<x,y,s>;...:<x,y,s>" with "NaN" for missing values.
Turning both separators into commas makes every line one flat CSV row, which pandas' C parser
reads in seconds instead of the minutes a Python loop needs.

The cache is written under data/cache/, which .gitignore keeps out of git: it is derived
frame-level tracking, and publishing it would be redistributing the data.
"""

import io
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from games import DATA_DIR, GAME, GAMES, require  # noqa: E402

HOME, AWAY = 0, 1


def slot_teams(meta_path):
    """0/1 per track slot: 0 = home (first team in the metadata), 1 = away."""
    root = ET.parse(meta_path).getroot()
    team_ids = [team.get("id") for team in root.iter("Team")]
    home_id = team_ids[0]
    return np.array([HOME if p.get("teamId") == home_id else AWAY
                     for p in root.iter("Player")], dtype=np.int8)


def load_tracking(source="tactical", game=GAME, use_cache=True):
    """Return dict with players (N,S,2) metres, ball (N,2) metres, teams (S,), n_frames.

    Row i is video frame i (ATD frame_id i+1). Missing values are NaN.
    """
    cache_dir = os.path.join(DATA_DIR, "cache")
    cache = os.path.join(cache_dir, "{}_{}_tracking.npz".format(game, source))
    meta_path, raw_path = require(["atd_meta", "atd_raw"], game, None, source)
    teams = slot_teams(meta_path)

    if use_cache and os.path.isfile(cache) and os.path.getmtime(cache) > os.path.getmtime(raw_path):
        z = np.load(cache)
        return {"players": z["players"], "ball": z["ball"], "teams": teams,
                "n_frames": len(z["ball"])}

    with open(raw_path) as handle:
        text = handle.read().replace(":", ",").replace(";", ",")
    table = pd.read_csv(io.StringIO(text), header=None, na_values=["NaN"],
                        dtype=np.float64, engine="c").to_numpy()
    del text

    n_slots = len(teams)
    expected_cols = 1 + 3 * n_slots + 3
    if table.shape[1] != expected_cols:
        raise ValueError("expected {} columns, got {}".format(expected_cols, table.shape[1]))

    frame_ids = table[:, 0].astype(np.int64)
    n_frames = int(frame_ids.max())
    length, width = GAMES[game]["pitch"]
    scale = np.array([length, width])

    players = np.full((n_frames, n_slots, 2), np.nan)
    groups = table[:, 1:1 + 3 * n_slots].reshape(len(table), n_slots, 3)
    players[frame_ids - 1] = groups[:, :, :2] * scale
    ball = np.full((n_frames, 2), np.nan)
    ball[frame_ids - 1] = table[:, -3:-1] * scale

    os.makedirs(cache_dir, exist_ok=True)
    np.savez_compressed(cache, players=players.astype(np.float32), ball=ball.astype(np.float32))
    return {"players": players, "ball": ball, "teams": teams, "n_frames": n_frames}


def load_set_pieces(game=GAME):
    """Smart Tagging SET PIECES intervals as (start_frame, end_frame, type). Tactical only."""
    try:
        path = require(["smart_tagging"], game)[0]
    except IOError:
        return []
    fps = GAMES[game]["fps"]
    out = []
    for inst in ET.parse(path).iter("instance"):
        if (inst.findtext("code") or "").strip().lower() != "set pieces":
            continue
        tags = {l.findtext("group"): l.findtext("text") for l in inst.findall("label")}
        out.append((int(round(float(inst.findtext("start")) * fps)),
                    int(round(float(inst.findtext("end")) * fps)),
                    (tags.get("Type") or "").strip()))
    return out

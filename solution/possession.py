"""Possession from tracking: a rule-based state machine, no training.

Three steps:

1. Clean the ball track. Fill short gaps (up to 0.5 s) by straight-line interpolation; leave
   longer gaps empty rather than invent a ball.
2. Find dead-ball stretches: the ball is off the pitch, or play has visibly stopped (players
   walking, ball still or invisible). A stretch ends at the restart, the first real kick.
3. Inside each live stretch, decide possession from "touch events": short runs of frames where
   one team is clearly nearest the ball. Possession only changes hands when the other team shows
   *control*: a long touch, or two touches in a row (a pass). A single brief touch, deflection
   or duel does not flip it. Loose balls stay with the last team, as CHALLENGE.md defines.

Every threshold below is chosen from football and tracking common sense and is written down with
its reason. None was fitted to the public ground truth (see RULES.md): the public window is only
used to check that frames line up and the file is valid.
"""

import numpy as np

FPS = 25

# Params
# Ball cleaning
BALL_GAP_FILL = 12          # frames: fill ball gaps up to 0.5 s; a ball cannot do much unseen in that time
# Touches
TOUCH_RADIUS = 2.0          # m: ball within this of a player's tracked position counts as at his feet
TOUCH_MARGIN = 0.75         # m: the nearest opponent must be this much further away, else it is a duel
TOUCH_GAP = 2               # frames: tolerate this many missing frames inside one touch
TOUCH_MIN = 3               # frames: shorter than 0.12 s is a ricochet, not a touch
CONTROL_FRAMES = 12         # frames: a 0.5 s touch is controlled possession by itself
PASS_WINDOW = 4 * FPS       # frames: two touches by the same team within 4 s count as a pass
# Dead ball
OUT_MARGIN = 0.5            # m: ball this far over a line is out
SLOW_PLAYERS = 1.3          # m/s: median player speed below this means play has stopped
SLOW_BALL = 1.0             # m/s: ball slower than this is resting
MIN_DEAD = int(1.5 * FPS)   # frames: a stoppage shorter than 1.5 s is a lull, not a dead ball
RESTART_SPEED = 5.0         # m/s: a restart is a kick or throw, faster than anyone carries the ball
MAX_RESTART_WAIT = 90 * FPS # frames: give up looking for a restart after 90 s
SPEED_CLIP = 12.0           # m/s: faster than any sprinter means a tracker identity switch


def runs(mask):
    """[(start, end)) for each run of True in a boolean array."""
    m = np.concatenate(([False], mask, [False]))
    d = np.diff(m.astype(np.int8))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def rolling_mean(x, w):
    """Centred moving average ignoring NaN, window 2w+1."""
    valid = ~np.isnan(x)
    c = np.concatenate(([0], np.cumsum(np.where(valid, x, 0.0))))
    n = np.concatenate(([0], np.cumsum(valid)))
    i = np.arange(len(x))
    lo, hi = np.maximum(0, i - w), np.minimum(len(x), i + w + 1)
    cnt = n[hi] - n[lo]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(cnt > 0, (c[hi] - c[lo]) / np.maximum(cnt, 1), np.nan)


def fill_ball(ball, max_gap=BALL_GAP_FILL):
    """Linear interpolation over gaps of at most max_gap frames. Returns (ball, observed_or_filled)."""
    ball = ball.copy()
    seen = ~np.isnan(ball[:, 0])
    for a, b in runs(~seen):
        if a == 0 or b == len(ball) or b - a > max_gap:
            continue
        t = (np.arange(a, b) - (a - 1)) / float(b - (a - 1))
        ball[a:b] = ball[a - 1] + t[:, None] * (ball[b] - ball[a - 1])
    return ball, ~np.isnan(ball[:, 0])


def features(trk, pitch):
    players, teams = trk["players"].astype(np.float64), trk["teams"]
    ball, ball_ok = fill_ball(trk["ball"].astype(np.float64))

    dist = np.linalg.norm(players - ball[:, None, :], axis=2)          # (N, S), NaN if missing
    big = 1e9
    d_home = np.min(np.where(np.isnan(dist[:, teams == 0]), big, dist[:, teams == 0]), axis=1)
    d_away = np.min(np.where(np.isnan(dist[:, teams == 1]), big, dist[:, teams == 1]), axis=1)

    # ball speed, m/s, from the cleaned track
    v = np.full(len(ball), np.nan)
    v[1:-1] = np.linalg.norm(ball[2:] - ball[:-2], axis=1) * FPS / 2.0
    ball_speed = rolling_mean(v, 2)

    # median player speed per frame, from positions
    step = np.linalg.norm(players[1:] - players[:-1], axis=2) * FPS
    step[step > SPEED_CLIP] = np.nan
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            med = np.nanmedian(step, axis=1)
    team_speed = rolling_mean(np.concatenate(([np.nan], med)), FPS)   # 2 s window

    length, width = pitch
    x, y = ball[:, 0], ball[:, 1]
    out = ball_ok & ((x < -OUT_MARGIN) | (x > length + OUT_MARGIN) |
                     (y < -OUT_MARGIN) | (y > width + OUT_MARGIN))
    return {"ball_ok": ball_ok, "d_home": d_home, "d_away": d_away, "ball_speed": ball_speed,
            "team_speed": team_speed, "out": out}


def dead_mask(f, n, set_pieces=()):
    """Boolean per frame: True where the ball is judged dead."""
    ball_ok, speed, out = f["ball_ok"], f["ball_speed"], f["out"]
    restart_ok = ball_ok & ~out & (np.nan_to_num(speed) > RESTART_SPEED)
    restart_idx = np.flatnonzero(restart_ok)

    def next_restart(t):
        k = np.searchsorted(restart_idx, t)
        if k < len(restart_idx) and restart_idx[k] - t <= MAX_RESTART_WAIT:
            return int(restart_idx[k])
        return None

    dead = np.zeros(n, dtype=bool)

    # (a) ball off the pitch: dead from the moment it crosses until the restart
    for a, b in runs(out):
        if b - a < 3:
            continue
        r = next_restart(b)
        dead[a:(r if r is not None else b)] = True

    # (b) play visibly stopped: players walking and the ball resting or unseen
    slow = (np.nan_to_num(f["team_speed"], nan=0.0) < SLOW_PLAYERS) & \
           (~ball_ok | (np.nan_to_num(speed) < SLOW_BALL))
    for a, b in runs(slow):
        if b - a < MIN_DEAD:
            continue
        r = next_restart(a + MIN_DEAD)
        end = r if (r is not None and r <= b + 5 * FPS) else b
        dead[a:end] = True

    # (c) automatic set-piece tags: the restart lies inside the tagged window, so the window
    #     before the restart kick is dead ball. Only used where (a)/(b) found nothing.
    for s, e, _type in set_pieces:
        s, e = max(0, s), min(n, e)
        if s >= e or dead[s:e].any():
            continue
        k = np.searchsorted(restart_idx, s)
        if k < len(restart_idx) and restart_idx[k] < e:
            dead[s:restart_idx[k]] = True

    # close live gaps shorter than 1 s between two dead stretches (tracking flicker)
    for a, b in runs(~dead):
        if a > 0 and b < n and b - a < FPS:
            dead[a:b] = True
    return dead


def touch_events(f, lo, hi):
    """[(start, end, team)] inside [lo, hi): runs where one team is clearly nearest the ball."""
    dh, da = f["d_home"][lo:hi], f["d_away"][lo:hi]
    ok = f["ball_ok"][lo:hi]
    near = np.minimum(dh, da)
    team = np.where(dh < da, 0, 1)
    clear = ok & (near <= TOUCH_RADIUS) & (np.abs(dh - da) >= TOUCH_MARGIN)
    code = np.where(clear, team, -1)

    events = []
    for t in (0, 1):
        m = code == t
        # bridge tiny gaps
        for a, b in runs(~m):
            if a > 0 and b < len(m) and b - a <= TOUCH_GAP and m[a - 1] and m[b]:
                m[a:b] = True
        for a, b in runs(m):
            if b - a >= TOUCH_MIN:
                events.append((lo + a, lo + b, t))
    events.sort()
    return events


def label_live(events, lo, hi, out):
    """Write 0/1 codes into out[lo:hi] for one live stretch."""
    if not events:
        return False
    current = events[0][2]
    out[lo:hi] = current
    switch_at = []
    for i, (s, e, t) in enumerate(events):
        if t == current:
            continue
        controlled = (e - s) >= CONTROL_FRAMES
        if not controlled:
            # a pass: next event is the same team, soon, with no opponent touch in between
            nxt = events[i + 1] if i + 1 < len(events) else None
            controlled = nxt is not None and nxt[2] == t and nxt[0] - e <= PASS_WINDOW
        if controlled:
            current = t
            switch_at.append((s, t))
    for s, t in switch_at:
        out[s:hi] = t
    return True


def predict(trk, pitch, half_blocks, set_pieces=()):
    """Per-frame labels H/A/D/X for every frame of the source."""
    n = trk["n_frames"]
    f = features(trk, pitch)
    dead = dead_mask(f, n, set_pieces)

    code = np.full(n, -1, dtype=np.int8)        # -1 = no idea yet
    for h_lo, h_hi in half_blocks:
        h_hi += 1
        prev_team = None
        for a, b in runs(~dead[h_lo:h_hi]):
            a, b = a + h_lo, b + h_lo
            if label_live(touch_events(f, a, b), a, b, code):
                prev_team = int(code[b - 1])
            elif prev_team is not None:
                code[a:b] = prev_team           # nothing seen: keep the last team

    labels = np.full(n, "X", dtype="<U1")
    in_play = np.zeros(n, dtype=bool)
    for h_lo, h_hi in half_blocks:
        in_play[h_lo:h_hi + 1] = True
    labels[in_play & dead] = "D"
    labels[in_play & ~dead & (code == 0)] = "H"
    labels[in_play & ~dead & (code == 1)] = "A"
    return labels

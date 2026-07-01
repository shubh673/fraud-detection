"""
Small shared helpers for the Step 3 detection modules
(BIN attack + same-IP repetitive authorisation).
"""

import numpy as np
import pandas as pd

import config


def severity_from_score(score):
    """Map a 0-1000 risk score to a severity band (config.SEVERITY_BANDS)."""
    for threshold, label in config.SEVERITY_BANDS:
        if score >= threshold:
            return label
    return "LOW"


def parse_event_time(df, col=None):
    """Return a copy of df with a parsed datetime column '_event_time', sorted."""
    col = col or config.EVENT_TIME_COL
    out = df.copy()
    out["_event_time"] = pd.to_datetime(out[col], errors="coerce")
    out = out.dropna(subset=["_event_time"]).sort_values("_event_time")
    return out.reset_index(drop=True)


def declined_flag(df):
    """
    Boolean Series marking declined / failed authorisations.

    Uses the raw EHI status field when present (Txn_Stat_Code == 'D'); falls back
    to a populated decline response code (Resp_Code_DE39 not null).
    """
    flag = pd.Series(False, index=df.index)
    if "Txn_Stat_Code" in df.columns:
        flag = flag | (df["Txn_Stat_Code"].astype("string").str.upper() == "D")
    if "Resp_Code_DE39" in df.columns:
        flag = flag | df["Resp_Code_DE39"].notna()
    return flag


def forward_window_counts(times_epoch, window_seconds):
    """
    For each index i, count transactions in the window [t_i, t_i + window].
    Returns (counts, end_indices) where end_indices[i] is the exclusive end.
    `times_epoch` must be a sorted numpy array of epoch seconds.
    """
    n = len(times_epoch)
    counts = np.zeros(n, dtype=int)
    ends = np.zeros(n, dtype=int)
    end = 0
    for i in range(n):
        if end < i + 1:
            end = i + 1
        limit = times_epoch[i] + window_seconds
        while end < n and times_epoch[end] <= limit:
            end += 1
        counts[i] = end - i
        ends[i] = end
    return counts, ends


def segment_indices(flagged_positions, times_epoch, max_gap_seconds):
    """
    Split a sorted list of flagged row positions into contiguous clusters.
    A new cluster starts when the time gap to the previous flagged row exceeds
    max_gap_seconds. Returns a list of lists of positions.
    """
    if len(flagged_positions) == 0:
        return []
    clusters = []
    current = [flagged_positions[0]]
    for pos in flagged_positions[1:]:
        if times_epoch[pos] - times_epoch[current[-1]] > max_gap_seconds:
            clusters.append(current)
            current = [pos]
        else:
            current.append(pos)
    clusters.append(current)
    return clusters

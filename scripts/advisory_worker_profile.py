"""Isolated read-only profile for ordinary Recommend workers; no launcher or I/O.

The existing atomic issue-workflow connector supplies Recommend mode and durable
launch receipts. This profile cannot replace the compiled vk_delegate correction.
"""
from copy import deepcopy

NAME = "RECOMMEND_READ_ONLY"


def prepare(current):
    candidate = deepcopy(current)
    codex = candidate["executors"]["CODEX"]
    base = codex["DEFAULT"]["CODEX"]
    if base.get("model") != "gpt-6.1-sol":
        raise ValueError("Default model changed; review before adding the profile")
    worker = deepcopy(base)
    worker["sandbox"] = "read-only"
    worker["ask_for_approval"] = "never"
    profile = {"CODEX": worker}
    if NAME in codex and codex[NAME] != profile:
        raise ValueError("Profile name already has different settings; preserve it")
    codex[NAME] = profile
    return candidate


def verify(before, after):
    expected = prepare(before)
    if after != expected:
        raise ValueError("Readback differs; preserve evidence, do not overwrite intervening settings")
    return True

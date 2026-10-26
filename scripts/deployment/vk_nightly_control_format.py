"""Portable recovery member-key validation shared by MCP and native B code."""
from pathlib import PurePosixPath


def key(value):
    if (not isinstance(value,str) or not value or '\0' in value
            or PurePosixPath(value).is_absolute()
            or any(p in ('','.','..') for p in value.split('/'))):
        raise ValueError('invalid recovery member/selector')
    return value

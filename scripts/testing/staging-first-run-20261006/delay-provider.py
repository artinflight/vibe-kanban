"""Deterministic pre-native interruption window, confined by reviewed fixture isolation."""
import os
import runpy
import time

if '/vk-continuation-http-' not in os.environ.get('CODEX_HOME', ''):
    raise RuntimeError('Synthetic home required')
time.sleep(5)
runpy.run_path('/mnt/vk-storage/vk-combined-release-20261007/source/scripts/testing/codex_goal_provider.py', run_name='__main__')

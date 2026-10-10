"""Measure fixed offline release builds without clearing any existing cache.

Source-only benchmark, never deployment. A cold cache is a NEW task directory.
Production-size builds require explicit space above the preserved 8GiB reserve.
"""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time


RESERVE = 8 * 1024**3


def benchmark(source, source_head, warm_cache, cold_cache, output, *, timeout=600,
              cold_space_bytes=16 * 1024**3, fixture_only=False):
    source, warm_cache, cold_cache, output = map(Path, (source, warm_cache, cold_cache, output))
    if not os.path.ismount('/mnt/vk-storage'):
        raise ValueError('mounted SSD required')
    for path in (warm_cache, cold_cache, output):
        if not path.resolve().is_relative_to('/mnt/vk-storage'):
            raise ValueError('build caches/evidence must remain on mounted SSD')
    if (cold_cache.exists() or cold_cache.is_symlink() or not warm_cache.is_dir()
            or not output.is_dir() or source.resolve().is_relative_to(warm_cache.resolve())
            or warm_cache.resolve().is_relative_to(source.resolve())
            or cold_cache.resolve().is_relative_to(warm_cache.resolve())
            or warm_cache.resolve().is_relative_to(cold_cache.resolve())):
        raise ValueError('cold cache must be fresh and separate; preserve existing source/cache')
    if type(timeout) not in (int, float) or not 0 < timeout <= 600 or type(cold_space_bytes) is not int or cold_space_bytes < 0:
        raise ValueError('finite build time and cold capacity bounds required')
    actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != source_head or subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain']):
        raise ValueError('benchmark needs exact clean FIX READY source')
    free = shutil.disk_usage(output).free
    floor = 0 if fixture_only else RESERVE
    report = {'source_head': source_head, 'fixture_only': fixture_only, 'warm_cache_preserved': True,
              'cold_cache_new': True, 'production_changed': False, 'full_pipeline_measured': False,
              'space_available_bytes': free, 'required_bytes': floor + cold_space_bytes, 'builds': {}}
    if free < floor + cold_space_bytes:
        return {**report, 'passed': False, 'blocked': 'cold build capacity; do not clear caches or protected evidence'}
    cold_cache.mkdir(mode=0o700)
    scratch = output / 'compiler-scratch'
    scratch.mkdir(mode=0o700)
    for kind, cache in (('warm', warm_cache), ('cold', cold_cache)):
        started = time.monotonic()
        log = output / (kind + '-release-build.log')
        env = dict(os.environ, CARGO_TARGET_DIR=str(cache), CARGO_INCREMENTAL='0', TMPDIR=str(scratch))
        with log.open('xb') as stream:
            process = subprocess.Popen(['cargo', 'build', '--offline', '--locked', '--release', '--bin', 'server'],
                                       cwd=source, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            reason = None
            while process.poll() is None:
                if time.monotonic() - started > timeout:
                    reason = 'release build exceeded FIX READY pipeline budget'
                elif shutil.disk_usage(output).free < floor:
                    reason = 'preserved storage reserve reached'
                elif log.stat().st_size > 64 * 1024**2:
                    reason = 'build log bound reached'
                if reason:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                    break
                time.sleep(0.05)
        report['builds'][kind] = {'seconds': time.monotonic() - started,
                                 'exit_code': process.returncode, 'blocked': reason}
        if process.returncode or reason:
            return {**report, 'passed': False, 'blocked': reason or kind + ' release build failed'}
    return {**report, 'passed': True}

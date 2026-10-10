"""Own user-cron adoption/rollback; no root files, data deletion or service action.

The authenticated controller supplies verify_ready(). Cron is a timezone-neutral
wake-up pulse; the fixed Toronto calendar owns daily timing and retry decisions.
Same-account source callbacks are operational gates, not security walls.
"""
import hashlib
import re
import subprocess


BEGIN = '# BEGIN VK_NORMAL_NIGHTLY_V1\n'
END = '# END VK_NORMAL_NIGHTLY_V1\n'


def block(package, config, config_sha256, log):
    for path in (package, config, log):
        if not re.fullmatch('/[A-Za-z0-9_./-]+', str(path)) or '..' in str(path).split('/'):
            raise ValueError('fixed absolute package/config/log paths required')
    if not re.fullmatch('[0-9a-f]{64}', config_sha256):raise ValueError('configuration hash required')
    command = ('/usr/bin/systemd-run --user --scope --quiet --collect '
               '--property=CPUQuota=25\\% --property=MemoryHigh=2G --property=MemoryMax=3G '
               '/usr/bin/nice -n 19 /usr/bin/ionice -c 3 /usr/bin/python3 -B -S '
               + str(package) + '/vk_nightly_calendar.py --config ' + str(config)
               + ' --config-sha256 ' + config_sha256 + ' >> ' + str(log) + ' 2>&1')
    return BEGIN + '*/15 * * * * ' + command + '\n' + END


def add_owned(existing, owned, *, timezone):
    if not isinstance(timezone,str) or not timezone:
        raise ValueError('actual host cron timezone must be observed')
    if BEGIN in existing or END in existing:raise ValueError('existing nightly block needs exact adoption reconciliation')
    if existing and not existing.endswith('\n'):raise ValueError('unexpected unterminated existing crontab')
    if not owned.startswith(BEGIN) or not owned.endswith(END):raise ValueError('exact owned block missing')
    return existing + owned


def remove_owned(existing, owned):
    if existing.count(owned) != 1 or existing.count(BEGIN) != 1 or existing.count(END) != 1:
        raise ValueError('nightly block changed; preserve unrelated schedule and reconcile')
    return existing.replace(owned, '', 1)


def apply(owned, verify_ready, *, timezone, rollback=False, runner=subprocess.run):
    """verify_ready raises unless exact acceptance/config/action are authenticated.

    Caller serializes this one-time update with other crontab editors. Existing
    CLI has no global compare-and-swap; recheck and post-readback are mandatory.
    Never persist/print other crontab contents (they can contain credentials).
    Rollback disables ONLY our exact cron block; payloads/evidence/data survive.
    """
    if verify_ready() is not None:raise ValueError('trusted readiness gate must raise on failure')
    def read():
        result=runner(['crontab','-l'],capture_output=True,text=True)
        if result.returncode == 0:return result.stdout
        if result.returncode == 1 and 'no crontab for' in result.stderr:return ''
        raise ValueError('user crontab cannot be read; no update')
    previous=read()
    updated=remove_owned(previous,owned) if rollback else add_owned(previous,owned,timezone=timezone)
    if read()!=previous:raise ValueError('concurrent user crontab change; no update')
    result=runner(['crontab','-'],input=updated,capture_output=True,text=True)
    if result.returncode:raise ValueError('user crontab installation rejected')
    if read()!=updated:raise ValueError('user crontab readback differs; reconcile without overwriting it')
    return {'own_nightly_enabled':not rollback,'previous_sha256':hashlib.sha256(previous.encode()).hexdigest(),
            'installed_sha256':hashlib.sha256(updated.encode()).hexdigest(),
            'other_jobs_preserved':True,'root_security_changed':False,'backup_data_deleted':False}

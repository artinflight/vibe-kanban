"""Local-only fixture settings; never apply these to serving readers."""
from pathlib import Path
import socket

# Isolated readers may discover optional CLIs at startup. A fixture must not
# download packages or wait for npm's network retries before helpers drain.
OFFLINE_NPM = {
    'npm_config_offline': 'true',
    'npm_config_fetch_retries': '0',
    'npm_config_update_notifier': 'false',
}


def reserve_ports(*, candidates=range(16000, 30000, 2), ephemeral=None):
    """Reserve adjacent API/preview ports outside the host's outgoing range.

    Caller retains these sockets until immediately before its single dispatch.
    No listener is displaced and a failed dispatch must still be reconciled.
    """
    if ephemeral is None:
        ephemeral = tuple(map(int, Path('/proc/sys/net/ipv4/ip_local_port_range').read_text().split()))
    low, high = ephemeral
    if not 1 <= low <= high <= 65535:
        raise ValueError('Invalid ephemeral port range')
    for port in candidates:
        if not 1024 <= port < 65535 or any(low <= p <= high for p in (port, port + 1)):
            continue
        sockets = []
        try:
            for p in (port, port + 1):
                sock = socket.socket()
                sockets.append(sock)
                sock.bind(('127.0.0.1', p))
            return port, sockets
        except OSError:
            for sock in sockets:
                sock.close()
    raise OSError('No unoccupied private reader port pair outside ephemeral range')

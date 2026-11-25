import socket
import unittest

from private_reader_runtime import reserve_ports


class PrivatePortsTests(unittest.TestCase):
    def test_ephemeral_candidates_are_excluded(self):
        with self.assertRaisesRegex(OSError, 'outside ephemeral'):
            reserve_ports(candidates=[40000, 49999], ephemeral=(40001, 50000))

    def test_occupied_port_is_preserved_and_not_reused(self):
        with socket.socket() as existing:
            existing.bind(('127.0.0.1', 0))
            port = existing.getsockname()[1]
            with self.assertRaisesRegex(OSError, 'unoccupied'):
                reserve_ports(candidates=[port], ephemeral=(1024, 1025))
            self.assertEqual(existing.getsockname()[1], port)

    def test_reservations_hold_both_ports_until_release(self):
        port, sockets = reserve_ports()
        try:
            for p in (port, port + 1):
                with socket.socket() as other:
                    with self.assertRaises(OSError):
                        other.bind(('127.0.0.1', p))
        finally:
            for sock in sockets:
                sock.close()


if __name__ == '__main__':
    unittest.main()

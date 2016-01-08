import tempfile
import socket
import threading
import os
import io
import pytest

from .. import server
from .. import protocol
from .. import util


def test_socket():
    path = tempfile.mktemp()
    with server.unix_domain_socket_server(path):
        pass
    assert not os.path.isfile(path)


class FakeSocket(object):

    def __init__(self, data=b''):
        self.rx = io.BytesIO(data)
        self.tx = io.BytesIO()

    def sendall(self, data):
        self.tx.write(data)

    def recv(self, size):
        return self.rx.read(size)

    def close(self):
        pass


def test_handle():
    handler = protocol.Handler(keys=[], signer=None)
    conn = FakeSocket()
    server.handle_connection(conn, handler)

    msg = bytearray([protocol.SSH_AGENTC_REQUEST_RSA_IDENTITIES])
    conn = FakeSocket(util.frame(msg))
    server.handle_connection(conn, handler)
    assert conn.tx.getvalue() == b'\x00\x00\x00\x05\x02\x00\x00\x00\x00'

    msg = bytearray([protocol.SSH2_AGENTC_REQUEST_IDENTITIES])
    conn = FakeSocket(util.frame(msg))
    server.handle_connection(conn, handler)
    assert conn.tx.getvalue() == b'\x00\x00\x00\x05\x0C\x00\x00\x00\x00'

    with pytest.raises(AttributeError):
        server.handle_connection(conn=None, handler=None)


def test_server_thread():

    connections = [FakeSocket()]
    quit_event = threading.Event()

    class FakeServer(object):
        def accept(self):  # pylint: disable=no-self-use
            if connections:
                return connections.pop(), 'address'
            quit_event.set()
            raise socket.timeout()

        def getsockname(self):  # pylint: disable=no-self-use
            return 'fake_server'

    server.server_thread(server=FakeServer(),
                         handler=protocol.Handler(keys=[], signer=None),
                         quit_event=quit_event)


def test_spawn():
    obj = []

    def thread(x):
        obj.append(x)

    with server.spawn(thread, dict(x=1)):
        pass

    assert obj == [1]


def test_run():
    assert server.run_process(['true'], environ={}) == 0
    assert server.run_process(['false'], environ={}) == 1
    assert server.run_process(
        command='exit $X',
        environ={'X': '42'},
        use_shell=True) == 42

    with pytest.raises(OSError):
        server.run_process([''], environ={})


def test_serve_main():
    with server.serve(public_keys=[], signer=None, sock_path=None):
        pass


def test_remove():
    path = 'foo.bar'

    def remove(p):
        assert p == path

    server.remove_file(path, remove=remove)

    def remove_raise(_):
        raise OSError('boom')

    server.remove_file(path, remove=remove_raise, exists=lambda _: False)

    with pytest.raises(OSError):
        server.remove_file(path, remove=remove_raise, exists=lambda _: True)

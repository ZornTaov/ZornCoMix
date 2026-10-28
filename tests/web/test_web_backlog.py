#the page asks for a dozen scripts at once beside its state polls. a server slow to take connections in - a busy
#nas, or a test run measuring every line - kept only five waiting, and on windows refused the rest: a script never
#loaded, and the page came up broken. this holds the server back from taking any, as a slow one is, and asks.
import socket
import threading

from comiclib.web.server import PageServer
from http.server import BaseHTTPRequestHandler

AT_ONCE = 20


def test_a_page_full_of_scripts_is_not_refused_by_a_server_slow_to_take_them():
    server = PageServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    port = server.server_address[1]
    refused, held = [], []
    try:
        #nothing is taken in yet: every connection has to wait its turn in the queue
        def connect():
            one = socket.socket()
            one.settimeout(3)
            try:
                one.connect(("127.0.0.1", port))
                held.append(one)
            except OSError as error:
                refused.append(error)
                one.close()
        threads = [threading.Thread(target=connect) for _ in range(AT_ONCE)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert not refused, "{0} of {1} connections refused: {2}".format(len(refused), AT_ONCE, refused[:2])
    finally:
        for one in held:
            one.close()
        server.server_close()

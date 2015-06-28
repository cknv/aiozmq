
'''
This example demonstrates how to use the ZMQ socket monitor to receive
socket events.
'''

import asyncio
import aiozmq
import zmq


ZMQ_EVENTS = {
    getattr(zmq, name): name.replace('EVENT_', '').lower().replace('_', ' ')
    for name in [i for i in dir(zmq) if i.startswith('EVENT_')]}


def event_description(event):
    ''' Return a human readable description of the event '''
    return ZMQ_EVENTS.get(event, 'unknown')


class Protocol(aiozmq.ZmqProtocol):

    def __init__(self):
        self.wait_ready = asyncio.Future()
        self.wait_done = asyncio.Future()
        self.wait_closed = asyncio.Future()
        self.count = 0

    def connection_made(self, transport):
        self.transport = transport
        self.wait_ready.set_result(True)

    def connection_lost(self, exc):
        self.wait_closed.set_result(exc)

    def msg_received(self, data):
        # This protocol is used by both the Router and Dealer sockets in
        # this example. Router sockets prefix messages with the identity
        # of the sender and hence contain two frames in this simple test
        # protocol.
        if len(data) == 2:
            identity, msg = data
            assert msg == b'Hello'
            self.transport.write([identity, b'World'])
        else:
            msg = data[0]
            assert msg == b'World'
            self.count += 1
            if self.count >= 4:
                self.wait_done.set_result(True)

    def event_received(self, event):
        event['description'] = event_description(event['event'])
        print(event)


@asyncio.coroutine
def go():

    st, sp = yield from aiozmq.create_zmq_connection(
        Protocol, zmq.ROUTER, bind='tcp://127.0.0.1:*')
    yield from sp.wait_ready
    addr = list(st.bindings())[0]

    ct, cp = yield from aiozmq.create_zmq_connection(
        Protocol, zmq.DEALER, connect=addr)
    yield from cp.wait_ready

    # Enable the socket monitor on the client socket. Socket events
    # are passed to the 'event_received' method on the client protocol.
    yield from ct.enable_monitor()

    # Trigger some socket events while also sending a message to the
    # server. When the client protocol receives 4 response it will
    # fire the wait_done future.
    for i in range(4):
        yield from asyncio.sleep(0.1)
        yield from ct.disconnect(addr)
        yield from asyncio.sleep(0.1)
        yield from ct.connect(addr)
        yield from asyncio.sleep(0.1)
        ct.write([b'Hello'])

    yield from cp.wait_done

    # The socket monitor can be explicitly disabled if necessary.
    # ct.disable_monitor()

    # If a socket monitor is left enabled on a socket being closed,
    # the socket monitor will be closed automatically.
    ct.close()
    yield from cp.wait_closed

    st.close()
    yield from sp.wait_closed


def main():
    asyncio.get_event_loop().run_until_complete(go())
    print("DONE")


if __name__ == '__main__':
    # import logging
    # logging.basicConfig(level=logging.DEBUG)

    main()

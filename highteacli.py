"""
A command line interface for the high energy theory database.
"""
import argparse
import sys
import json
import time
import threading

import requests
import urllib3

__version__ = '0.2'

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ENDPOINT = 'https://www.hep.phy.cam.ac.uk:5443/api/'


FIBO = [0, 1, 1, 2, 3, 5, 8, 13, 21]

GLOBAL_SESSION = requests.Session()


def saturate(it):
    for val in it:
        yield val
    while True:
        yield val


class Spinner:
    """ Context manager to provide a spinning cursor
    while validphys performs some other task silently.
    Example
    -------
    >>> from validphys.renametools import Spinner
    >>> with Spinner():
    ...     import time
    ...     time.sleep(5)
    """

    def __init__(self, delay=0.1):
        self.spinner_generator = self.spinning_cursor()
        self.delay = delay

    def spinner_task(self):
        while not self.event.isSet():
            sys.stdout.write(next(self.spinner_generator))
            sys.stdout.flush()
            time.sleep(self.delay)
            sys.stdout.write('\b')
            sys.stdout.flush()

    def __enter__(self):
        self.event = threading.Event()
        threading.Thread(target=self.spinner_task).start()

    def __exit__(self, exception, value, tb):
        self.event.set()

    @staticmethod
    def spinning_cursor():
        while True:
            for cursor in '|/-\\':
                yield cursor


def simple_req(method, url, data=None):
    try:
        resp = GLOBAL_SESSION.request(
            method, f'{ENDPOINT}{url}', verify=False, json=data
        )
    except requests.RequestException as e:
        print("Error making request: ", e, file=sys.stderr)
        sys.exit(1)
    try:
        resp.raise_for_status()
    except requests.RequestException as e:
        try:
            errdata = f'{e}. {resp.json()}'
        except Exception:
            errdata = str(e)

        print("Server returned error: ", errdata, file=sys.stderr)
        sys.exit(1)
    return resp.json()


def list_pdfs():
    lpdfs = simple_req('get', 'available_pdfs')
    print('\n'.join(lpdfs))


def list_processes():
    lproc = simple_req('get', 'processes')
    print('\n'.join(lproc))


def make_hist(proc, fname):
    if fname == '-':
        data = json.load(sys.stdin)
    else:
        with open(fname) as f:
            data = json.load(f)
    resp = simple_req('post', f'processes/{proc}/hist', data=data)
    token = resp['token']
    print(f"Processing request. The token is {token}.", file=sys.stderr)
    print(f"Wait for the result here or run\nhighteacli token {token}", file=sys.stderr)
    wait_token(token)


def check_status(token):
    res = simple_req('get', f'token/{token}')
    st = res['status']
    if st in ('pending', 'runnung'):
        print(f'\bstatus: {st}', file=sys.stderr)
    elif st == 'errored':
        print("Token errored", file=sys.stderr)
        sys.exit(1)
    elif st == 'completed':
        print("Token completed", file=sys.stderr)
        print(res['result'])
        sys.exit(0)


def wait_token(token):
    with Spinner():
        for timeout in saturate(FIBO):
            check_status(token)
            time.sleep(timeout)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(title='commands', dest='command')
    commands.add_parser('lproc', help='List available processes')
    commands.add_parser('lpdf', help='List available pdfs')
    hist = commands.add_parser('hist', help='make and histogram')
    hist.add_argument('process', help='process to compute the histogram for')
    hist.add_argument('file', help='JSON file with the hisogram specification')
    token_cmd = commands.add_parser('token', help='query the status of a token')
    token_cmd.add_argument('token', help='a token that has been requested')
    ns = parser.parse_args()
    cmd = ns.command
    if cmd == 'lpdf':
        list_pdfs()
    elif cmd == 'lproc':
        list_processes()
    elif cmd == 'hist':
        pname = ns.process
        fname = ns.file
        make_hist(pname, fname)
    elif cmd == 'token':
        wait_token(ns.token)


def main():
    with GLOBAL_SESSION:
        parse_args()


if __name__ == '__main__':
    main()

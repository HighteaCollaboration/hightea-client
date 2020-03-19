"""
A command line interface for the high energy theory database.
"""
import argparse
import sys
import json
import time

import requests
import urllib3

__version__ = '0.1'

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ENDPOINT = 'https://www.hep.phy.cam.ac.uk:5443/api/'


FIBO = [0, 1, 1, 2, 3, 5, 8, 13, 21]


def simple_req(method, url, data=None):
    try:
        resp = requests.request(method, f'{ENDPOINT}{url}', verify=False, json=data)
    except requests.RequestException as e:
        print("Error making request: ", e)
        sys.exit(1)
    try:
        resp.raise_for_status()
    except requests.RequestException as e:
        try:
            errdata = f'{e}. {resp.json()}'
        except Exception:
            errdata = str(e)

        print("Server returned error: ", errdata)
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
    for timeout in FIBO:
        check_status(token)
        time.sleep(timeout)

    while True:
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
    parse_args()


if __name__ == '__main__':
    main()

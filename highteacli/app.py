import argparse
import sys
import json
import time
import threading

from highteacli import apiactions


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


class CommandLineApp:
    def __init__(self):
        self.api = apiactions.API()

    def list_pdfs(self):
        lpdfs = self.api.list_pdfs()
        print('\n'.join(lpdfs))

    def list_processes(self):
        lproc = self.api.list_processes()
        print('\n'.join(lproc))

    def make_hist(self, proc, fname):
        if fname == '-':
            data = json.load(sys.stdin)
        else:
            with open(fname) as f:
                data = json.load(f)
        resp = self.api.request_hist(proc, data)
        token = resp['token']
        print(f"Processing request. The token is {token}.", file=sys.stderr)
        print(
            f"Wait for the result here or run\n\n    highteacli token {token}\n",
            file=sys.stderr,
        )
        self.wait_token(token)

    def check_status(self, token):
        res = self.api.check_token(token)
        self.handle_token_result(res)

    def handle_token_result(self, res):
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

    def wait_token(self, token):
        with Spinner():
            for res in self.api.wait_token_impl(token):
                self.handle_token_result(res)


def main():
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
    app = CommandLineApp()
    if cmd == 'lpdf':
        app.list_pdfs()
    elif cmd == 'lproc':
        app.list_processes()
    elif cmd == 'hist':
        pname = ns.process
        fname = ns.file
        app.make_hist(pname, fname)
    elif cmd == 'token':
        app.wait_token(ns.token)


if __name__ == '__main__':
    main()

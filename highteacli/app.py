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


class ErrorPrintAPI(apiactions.API):
    """Wrap request method to print the error nicely"""

    def simple_req_no_json(self, *args, **kwargs):
        try:
            return super().simple_req_no_json(*args, **kwargs)
        except apiactions.RequestProblem as e:
            cause = e.__cause__
            print(cause, file=sys.stderr)
            try:
                msg = cause.response.json()['detail'][0]['msg']
                print(msg, file=sys.stderr)
            except Exception:
                pass
            sys.exit(1)


class CommandLineApp:
    def __init__(self):
        self.api = ErrorPrintAPI()

    def list_pdfs(self):
        lpdfs = self.api.list_pdfs()
        print('\n'.join(lpdfs))

    def list_processes(self):
        lproc = self.api.list_processes()
        print('\n'.join(lproc))

    def make_hist(self, proc, fname, do_plot):
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
        self.wait_token(token, do_plot)

    def check_status(self, token):
        res = self.api.check_token(token)
        self.handle_token_result(res, token, do_plot=False)

    def _wait_token_impl(self, res):
        st = res['status']
        if st in ('pending', 'runnung'):
            print(f'\bstatus: {st}', file=sys.stderr)
            return False
        elif st == 'errored':
            print("Token errored\n", res['error_string'], file=sys.stderr)
            sys.exit(1)
        elif st == 'completed':
            print("Token completed", file=sys.stderr)
            return True

    def handle_token_result(self, res, token, do_plot):
        if self._wait_token_impl(res):
            print(res['result'])
            if do_plot:
                self._handle_token_plot(token)
            sys.exit(0)

    def _handle_token_plot(self, token):
        bts = self.api.get_plot(token)
        fname = f'{token}.png'
        with open(fname, 'wb') as f:
            f.write(bts)
        print("\nHistogram plot writen to", fname, file=sys.stderr)

    def wait_token(self, token, do_plot):
        with Spinner():
            for res in self.api.wait_token_impl(token):
                self.handle_token_result(res, token, do_plot)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(title='commands', dest='command')
    commands.add_parser('lproc', help='List available processes')
    commands.add_parser('lpdf', help='List available pdfs')
    hist = commands.add_parser('hist', help='make and histogram')
    hist.add_argument('process', help='process to compute the histogram for')
    hist.add_argument('file', help='JSON file with the hisogram specification')
    hist.add_argument(
        '--plot', '-p', action='store_true', help="Save a simple plot for 1D histograms"
    )
    token_cmd = commands.add_parser('token', help='query the status of a token')
    token_cmd.add_argument('token', help='a token that has been requested')
    token_cmd.add_argument(
        '--plot', '-p', action='store_true', help="Save a simple plot for 1D histograms"
    )
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
        do_plot = ns.plot
        app.make_hist(pname, fname, do_plot)
    elif cmd == 'token':
        do_plot = ns.plot
        app.wait_token(ns.token, do_plot)


if __name__ == '__main__':
    main()

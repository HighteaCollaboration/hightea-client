import time
import json

import requests

ENDPOINT = 'https://www.hep.phy.cam.ac.uk:5443/api/'

FIBO = [0, 1, 1, 2, 3, 5, 8, 13, 21]


def saturate(it):
    for val in it:
        yield val
    while True:
        yield val


class RequestProblem(Exception):
    pass


class API:
    def __init__(self):
        self.session = requests.Session()

    def simple_req(self, method, url, data=None):
        try:
            resp = self.session.request(method, f'{ENDPOINT}{url}', json=data)
        except requests.RequestException as e:
            raise RequestProblem(f"Error making request: {e}") from e
        try:
            resp.raise_for_status()
        except requests.RequestException as e:
            try:
                errdata = f'{e}. {resp.json()}'
            except Exception:
                errdata = str(e)

            raise RequestProblem(f"Server returned error: {errdata}") from e
        return resp.json()

    def wait_token_impl(self, token):
        for timeout in saturate(FIBO):
            res = self.check_token(token)
            yield res
            st = res["status"]
            if st in ('pending', 'running'):
                time.sleep(timeout)
            elif st in ('errored', 'completed'):
                return

    def wait_token(self, token):
        for token_res in self.wait_token_impl(token):
            st = token_res['status']
            if st == 'errored':
                raise RuntimeError("Bad status")
            elif st == 'completed':
                return json.loads(token_res['result'])

    def list_pdfs(self):
        return self.simple_req('get', 'available_pdfs')

    def list_processes(self):
        return self.simple_req('get', 'processes')

    def request_hist(self, proc, data):
        return self.simple_req('post', f'processes/{proc}/hist', data=data)

    def check_token(self, token):
        return self.simple_req('get', f'token/{token}')

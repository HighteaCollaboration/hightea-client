import requests

ENDPOINT = 'https://www.hep.phy.cam.ac.uk:5443/api/'


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

    def list_pdfs(self):
        return self.simple_req('get', 'available_pdfs')

    def list_processes(self):
        return self.simple_req('get', 'processes')

    def request_hist(self, proc, data):
        return self.simple_req('post', f'processes/{proc}/hist', data=data)

    def check_token(self, token):
        return self.simple_req('get', f'token/{token}')

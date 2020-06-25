import requests

ENDPOINT = 'https://www.hep.phy.cam.ac.uk:5443/api/'
GLOBAL_SESSION = requests.Session()


class RequestProblem(Exception):
    pass


def simple_req(method, url, data=None, session=None):
    if session is None:
        session = GLOBAL_SESSION
    try:
        resp = session.request(method, f'{ENDPOINT}{url}', json=data)
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


def list_pdfs():
    return simple_req('get', 'available_pdfs')


def list_processes():
    return simple_req('get', 'processes')


def request_hist(proc, data):
    return simple_req('post', f'processes/{proc}/hist', data=data)


def check_token(token):
    return simple_req('get', f'token/{token}')

import time
import json

import requests
from requests.exceptions import ConnectionError
from urllib3.exceptions import ProtocolError
import urllib.parse

DEFAULT_ENDPOINT = 'https://www.hep.phy.cam.ac.uk/hightea/api/'

__all__ = ('RequestProblem', 'DEFAULT_ENDPOINT', 'API')


FIBO = [0, 1, 1, 2, 3, 5, 8, 13, 21]


def saturate(it):
    for val in it:
        yield val
    while True:
        yield val


class RequestProblem(Exception):
    """Base error that will be raised in case of problematic interactions with
    the API. Use the ``__cause__`` attribute of the error to inspect the
    underlying problem."""


class API:
    """Helper class to interact with the HighTEA API.
    """

    def __init__(self, *, auth=None, endpoint=DEFAULT_ENDPOINT):
        self.session = requests.Session()
        if not endpoint.endswith('/'):
            endpoint = endpoint + '/'
        self.endpoint = endpoint
        self.set_auth(auth)


    @property
    def auth(self):
        """Return authentication token.

        Returns
        -------
        token: str
            A string containing the authentication token.
        """
        return self._auth


    def set_auth(self, auth):
        """Set authentication token to be used in requests in current session.
        If authentication has already been set, remove it.

        Parameters
        ----------
        auth: str
            A string containing an authentication token.
        """
        self._auth = auth
        if auth:
            self.session.headers["Authorization"] = f"Bearer {auth}"
        else:
            if "Authorization" in self.session.headers:
                del self.session.headers["Authorization"]


    def _root_url_replace(self, **kwargs):
        """Helper method to complete the API URL.

        Returns
        -------
        url: str
            A URL locating the correct endpoint.
        """
        return urllib.parse.urlparse(self.endpoint)._replace(**kwargs).geturl()


    def simple_req_no_json(self, method, url, data=None, form_data=None):
        """Call the endpoint with the specified parameters and return the
        response object. Raise a ``RequestProblem`` error in case of failure.
        The ``method`` and ``url`` parameters are passed to
        :py:func:`requests.Request.request`. The ``data`` object is encoded as
        JSON.

        Parameters
        ----------
        method: str
            Specifying the request method, i.e. "GET", "POST" etc.

        url: str
            Request destination.

        data: dict
            The data to be transmitted in form of a dictionary.

        form_data: dict
            Additional information to added to the request. Used for authentication.

        Returns
        -------
        response: Response object
            A object containing the response information. See requests implementation.
        """
        try:
            resp = self.session.request(
                method, f'{self.endpoint}{url}', json=data, data=form_data
            )
        except requests.RequestException as e:
            # https://github.com/urllib3/urllib3/pull/1911
            if isinstance(e, ConnectionError) and e.args:
                if isinstance(e.args[0], ProtocolError):
                    if e.args[0].args and e.args[0].args[0] == 'Connection aborted.':
                        return self.simple_req_no_json(method, url, data)
            raise RequestProblem(f"Error making request: {e}") from e
        try:
            resp.raise_for_status()
        except requests.RequestException as e:
            if resp.status_code == 401:
                raise RequestProblem(
                    f"Unauthorized. Obtain an authentication code from "
                    f"{self._root_url_replace(path='/login')}"
                ) from e
            try:
                errdata = f'{e}. {resp.json()}'
            except Exception:
                errdata = str(e)

            raise RequestProblem(f"Server returned error: {errdata}") from e
        return resp


    def simple_req(self, method, url, data=None, form_data=None):
        """Call the endpoint with the specified parameters and return the JSON response.
        See :py:func:`API.simple_req_no_json`.

        Returns
        -------
        response: dict
            Returns the response to the request in JSON/dict format.

        """
        return self.simple_req_no_json(method, url, data, form_data).json()


    def auth_code(self, username, password, admin=False):
        """Implementation of the authentication request.

        Parameters
        ----------
        username: str
            A string containing the username

        password: str
            A string containing the password

        admin: bool
            Request admin login (requires admin privileges) (optional).

        Returns
        -------
        token: str
            The authentication token to be used in requests.
        """
        data = {"username": username, "password": password}
        if admin:
            data["scope"] = "admin"
        return self.simple_req("post", "userauthtoken",form_data=data)


    def login(self, username, password, admin=False):
        """Perform login, i.e. submit username and password and store authentication token.

        Parameters
        ----------
        username: str
            A string containing the username

        password: str
            A string containing the password

        admin: bool
            Request admin login (requires admin privileges) (optional).

        """
        res = self.auth_code(username, password, admin)
        self.set_auth(res["access_token"])


    def anonymous_login(self):
        """A method to anonymously login. This functionality might be removed in the future.
        """
        res = self.simple_req("post", "anonymousauthtoken")
        self.set_auth(res["access_token"])


    def make_invitation_url(self, admin: bool = False):
        """Generate a URL that can be used to register a new user.

        Parameters
        ----------
        admin : bool
           Whether the new user will be able to claim admin privileges.

        Returns
        -------
        url: str
            A URL to send to the user
        """
        resp = self.simple_req_no_json("get", "invite", data={"admin": admin})
        return resp.headers["Content-Location"]


    def wait_token_impl(self, token):
        """Block for the specified token until it is completed.
        Use this method to implement interactive behaviours while the
        computation is in progress. Otherwise use higher level methods such as
        :py:func:`API.wait_token_json` or :py:func:`API.wait_token_plot`.

        Parameters
        ------
        token: str
            A token representing a previous result, to wait for.

        Yields
        ------
        token_status: dict
            A dictionary containing information relative to the token.
        """
        for timeout in saturate(FIBO):
            res = self.check_token(token)
            yield res
            st = res["status"]
            if st in ('pending', 'running'):
                time.sleep(timeout)
            elif st in ('errored', 'completed'):
                return


    def get_plot(self, token):
        """Return an histogram plot for a computed token.

        Parameters
        ----------
        token: str
            A token representing a previous result, to wait for.

        Returns
        -------
        plot: bytes
            A byte string representing a figure in the PNG format.

        Notes
        -----
        If the computation corresponding to the token is not finalized, this
        method will fail. Use :py:func:`API.wait_token_plot` to block until the
        result is ready.
        """
        resp = self.simple_req_no_json('get', f'token/{token}/plot')
        return resp.content


    def wait_token_json(self, token):
        """Block for the specified token and return a JSON result.

        Parameters
        ----------
        token: str
            A token representing a previous result, to wait for.

        Returns
        -------
        result: dict
            A dictionary representing the result of the computation.
        """
        for token_res in self.wait_token_impl(token):
            st = token_res['status']
            if st == 'errored':
                raise RuntimeError("Bad status")
            elif st == 'completed':
                return json.loads(token_res['result'])


    def wait_token_plot(self, token):
        """Block until the specified token is available. When it is, return an
        histogram representation.

        Parameters
        ----------
        token: str
            A token representing a previous result, to wait for.

        Returns
        -------
        plot: bytes
            A byte string representing a figure in the PNG format.
        """
        for token_res in self.wait_token_impl(token):
            st = token_res['status']
            if st == 'errored':
                raise RuntimeError("Bad status")
            elif st == 'completed':
                return self.get_plot(token)


    def list_pdfs(self):
        """List the available PDF for central value computations.

        Returns
        -------
        pdfs: list
            A list of LHAPDF ids.
        """
        return self.simple_req('get', 'available_pdfs')


    def list_processes(self):
        """
        List the processes available in the server.

        Returns
        -------
        processes: list
            A list of processes
        """
        return self.simple_req('get', 'processes')


    def request_hist(self, proc, data):
        """Submit histogram request to server.

        Parameters
        ----------
        proc: str
            A tag specifying a process. See :py:func:`API.list_processes`.

        data: dict
            A dictionary defining the details of the request. For information
            about the expected structure and possible options please refer to
            the README (https://github.com/HighteaCollaboration/hightea-client)

        Returns
        -------
        token: str
            A token representing the request. Results can be obtained with
            :py:func:`API.wait_token_json` or  :py:func:`API.wait_token_plot`.
        """
        return self.simple_req('post', f'processes/{proc}/hist', data=data)


    def check_token(self, token):
        """
        Check information

        Parameters
        ----------
        token: str
            A token representing a previous result, to wait for.

        Returns
        -------
        info: dict
            A dictionary with the information on a specific token.
        """
        return self.simple_req('get', f'token/{token}')
import json
import requests
from . import _util, _exception

class State:
    def __init__(self):
        self._config = {}
        self._headers = _util.HEADERS
        self._cookies = _util.COOKIES
        self._session = requests.Session()
        self.user_id = None
        self.user_imei = None
        self._loggedin = False

    def get_cookies(self):
        return self._cookies

    def set_cookies(self, cookies):
        self._cookies = cookies

    def get_secret_key(self):
        return self._config.get("secret_key")

    def set_secret_key(self, secret_key):
        self._config["secret_key"] = secret_key

    def _get(self, *args, **kwargs):
        return self._session.get(*args, **kwargs, headers=self._headers, cookies=self._cookies)

    def _post(self, *args, **kwargs):
        return self._session.post(*args, **kwargs, headers=self._headers, cookies=self._cookies)

    def is_logged_in(self):
        return self._loggedin

    def login(self, phone, password, imei, session_cookies=None, user_agent=None):
        if self._cookies and self._config.get("secret_key"):
            self._loggedin = True
            print("Already logged in, no need to log in again.")
            return

        if user_agent:
            self._headers["User-Agent"] = self._encode_safe_string(user_agent)

        if self._cookies:
            params = {"imei": imei}
            try:
                response = self._get("https://wpa.zaloapp.com/api/login/getLoginInfo", params=params)
                data = response.json()
                if data.get("error_code") == 0 and data.get("data"):
                    self._config = data.get("data")
                    if self._config.get("zpw_enk"):
                        self._config["secret_key"] = self._config.get("zpw_enk")
                        self._loggedin = True
                        self.user_id = self._config.get("send2me_id")
                        self.user_imei = imei
                        print(f"User ID: {self.user_id}, IMEI: {self.user_imei}, Secret Key: {self._config.get('secret_key')}")
                    else:
                        raise _exception.ZaloLoginError("Unable to retrieve `secret key`.")
                else:
                    error = data.get("error_code")
                    content = data.get("error_message", "Undefined error")
                    raise _exception.ZaloLoginError(f"Error #{error} during login: {content}")
            except requests.RequestException as e:
                raise _exception.ZaloLoginError(f"An error occurred during login: {str(e)}")
            except _exception.ZaloLoginError as e:
                raise _exception.ZaloLoginError(str(e))
        else:
            raise _exception.LoginMethodNotSupport("Login Method Not Supported.")

    def _encode_safe_string(self, input_string):
        return input_string.encode('latin-1', 'ignore').decode('latin-1')

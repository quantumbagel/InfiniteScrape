import ipaddress
import json
import fake_useragent
import requests

ua = fake_useragent.UserAgent()


def verify_ip(ip: str):
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def verify_port(port: str | int):
    if type(port) is int:
        return port > 0
    else:
        return port.isnumeric()


def craft(one: str, two: str, proxy=None, timeout: int = 15, session: requests.Session | None = None):
    """
    This function, using the proxy IP passed, will attempt to craft two elements together
    :param session:
    :param one:
    :param two: The second element to craft
    :param proxy: The proxy IP
    :param timeout: The amount of time to wait (maximum)
    :return: None if the attempt failed, or the JSON if it succeeded.
    """

    headers = {
        'User-Agent': ua.random,
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://neal.fun/infinite-craft/',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-GPC': '1',
    }

    params = {
        'first': one,
        'second': two,
    }

    proxy_argument = {"https": proxy.parsed}

    try:
        if session is None:
            getter = requests
        else:
            getter = session

        response: requests.Response = getter.get('https://neal.fun/api/infinite-craft/pair', params=params, headers=headers,
                                    proxies=proxy_argument, verify=False, timeout=(timeout, timeout * 2))

    except requests.exceptions.ConnectTimeout:
        return {"status": "error", "type": "connection"}  # Failure
    except requests.exceptions.ConnectionError as e:
        return {"status": "error", "type": "connection"}  # Failure
    except requests.exceptions.ReadTimeout:
        return {"status": "error", "type": "read"}  # Failure
    string_response: str = response.content.decode('utf-8')  # Format byte response
    if "Retry-After" in response.headers:
        return {"status": "error", "type": "ratelimit", "penalty": int(response.headers["Retry-After"])}
    try:
        json_resp: dict = json.loads(string_response)
    except json.JSONDecodeError:  # If the response received was invalid return a ReadTimeout penalty
        return {"status": "error", "type": "read"}  # Failure

    json_resp.update({"status": "success", "time_elapsed": response.elapsed.total_seconds()})  # Add success field before returning

    return json_resp



def score_proxy(p):
    """

    :param p:
    :return:
    """
    proxy_avg_response = p.average_response  # Example value: 3
    # total_req = p["total_calls"]  # Example value: 12
    is_functional = p.status
    if not is_functional:
        return -1
    if proxy_avg_response == 0:
        return 0
    return 1 / proxy_avg_response


def rank_proxies(proxy_id=None):
    """
    Rank the proxies from best to worst
    :return:
    """
    ranked = sorted(proxies, key=score_proxy, reverse=True)

    if proxy_id is None:
        return ranked
    else:
        return ranked

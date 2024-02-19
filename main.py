import itertools
import json
import time
from concurrent.futures import ProcessPoolExecutor
import js2py
import requests
from fake_useragent import UserAgent
import random
from bs4 import BeautifulSoup

ua = UserAgent()
proxies = []  # Will contain proxies [ip, port, parsed]


requests_total = 0
def craft(one, two):
    global requests_total
    global proxies
    to_use = random.choice([p['parsed'] for p in proxies])
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
        "X-Client-IP": "104.22.28.82",  # Cloudflare bypass
        "X-Originating-IP": "104.22.28.82",
        "X-Remote-IP": "104.22.28.82",
        # "X-Remote-Addr": "104.22.28.82",
        # "X-Host": "104.22.28.82",
        # "X-Forwarded-Host": "127.0.0.1",
        # "X-Forwarded-For": "104.22.28.82"
    }

    params = {
        'first': one,
        'second': two,
    }
    response = requests.get('https://neal.fun/api/infinite-craft/pair', params=params, headers=headers, proxies={"https": "socks5h://142.54.237.34:4145"}, verify=False)
    string_response = response.content.decode('utf-8')  # Format byte response
    print("STR", string_response)
    try:
        json_resp = json.loads(string_response)
    except json.JSONDecodeError:
        print("Ratelimit reached, restarting IP")
        return craft(one, two)
    requests_total += 1
    return json_resp

def cpu_heavy(x, y):
    print('I am', x, y)
    time.sleep(10)

def multiprocessing(func, args, workers):
    with ProcessPoolExecutor(workers) as ex:
        combin = list(itertools.combinations(base_depth, 2))
        things_per = len(combin) // workers
        remaining_extra = len(combin) % workers
        res = ex.map(func, args, )
        ex.submit(func, args, )
    return list(res)

def evolve(word_set):

    combinations = list(itertools.combinations(word_set, 2))
    print(combinations)
    next_generation = []
    for index, combination in enumerate(combinations):
        print(index + 1, "/", len(combinations))
        if combination[0] + "+" + combination[1] in base_tree.keys():
            print("Combination", combination, "has already been crafted! Avoiding API call")
            craft_out = base_tree[combination[0] + "+" + combination[1]]
            if craft_out != "Nothing":  # valid
                next_generation.append(craft_out)
        elif combination[1] + "+" + combination[0] in base_tree.keys():
            craft_out = base_tree[combination[1] + "+" + combination[0]]
            if craft_out != "Nothing":  # valid
                next_generation.append(craft_out)
        else:
            out = craft(combination[0], combination[1])
            if out["result"] != "Nothing":  # valid
                next_generation.append(out["result"])
    return next_generation


base_depth = json.load(open('depth.json'))
base_tree = json.load(open('tree.json'))

# Retrieve latest proxies
def update_proxies():
    """
    This function is really complex. Here's how it works:

    1. gets the proxy list from spys
    2. obtains the randomly generated variables used for the hidden port numbers
    3. goes through each proxy and gets the calculation for the port number
    4. performs the calculation
    5. saves data

    This monstrosity could have been avoided if they had just let me scrape


    This is what you get.
    :return:
    """
    proxies_doc = requests.get('https://spys.one/en/socks-proxy-list', headers={"User-Agent": ua.random, "Content-Type": "application/x-www-form-urlencoded"}).text
    soup = BeautifulSoup(proxies_doc, 'html.parser')
    tables = list(soup.find_all("table"))  # Get ALL the tables

    # Variable definitions
    variables_raw = str(soup.find_all("script")[6]).replace('<script type="text/javascript">', "").replace('</script>', '').split(';')[:-1]
    variables = {}
    for var in variables_raw:
        name = var.split('=')[0]
        value = var.split("=")[1]
        if '^' not in value:
            variables[name] = int(value)
        else:
            prev_var = variables[var.split("^")[1]]
            variables[name] = int(value.split("^")[0]) ^ int(prev_var)  # Gotta love the bit math


    trs = tables[2].find_all("tr")[2:]
    for tr in trs:
        address = tr.find("td").find("font")

        if address is None:  # Invalid rows
            continue

        raw_port = [i.replace("(", "").replace(")", "") for i in str(address.find("script")).replace("</script>", '').split("+")[1:]]

        port = ""
        for partial_port in raw_port:
            first_variable = variables[partial_port.split("^")[0]]
            second_variable = variables[partial_port.split("^")[1]]
            port += "("+str(first_variable) + "^" + str(second_variable) + ")+"
        port = js2py.eval_js('function f() {return "" + ' + port[:-1] + '}')()
        proxies.append({"ip": address.get_text(), "port": port, "parsed": f"socks5h://{address.get_text()}:{port}"})
    return proxies

# proxies = update_proxies()
# evolved = evolve(base_depth)
#
# print(evolved)

if __name__ == "__main__":
    multiprocessing(cpu_heavy, range(50), 50)


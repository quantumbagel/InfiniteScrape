import itertools
import json
import time
from concurrent.futures import ThreadPoolExecutor

import js2py
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

ua = UserAgent()
proxies = []  # Will contain proxies [ip, port, parsed]
spare_crafts = []
calculated_crafts = {}
requests_total = 0


def craft(one, two, proxy, timeout=15):
    """
    This function, using the proxy IP passed, will attempt to craft two elements together
    :param one:
    :param two: The second element to craft
    :param proxy: The proxy IP
    :param timeout: The amount of time to wait (maximum)
    :return: None if the attempt failed, or the JSON if it succeeded.
    """
    global requests_total
    global proxies

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
        "X-Client-IP": "104.22.28.82",  # confuse cloudflare a bit
        "X-Originating-IP": "104.22.28.82",
        "X-Remote-IP": "104.22.28.82",
    }

    params = {
        'first': one,
        'second': two,
    }
    response = requests.get('https://neal.fun/api/infinite-craft/pair', params=params, headers=headers,
                            proxies={"https": proxy}, verify=False, timeout=timeout)
    string_response = response.content.decode('utf-8')  # Format byte response
    try:
        json_resp = json.loads(string_response)
    except json.JSONDecodeError:
        return None
    requests_total += 1
    return json_resp


def handle(crafts, identification, proxy, proxy_id_if_different=None):
    current_proxy = identification
    if proxy_id_if_different is not None:
        current_proxy = proxy_id_if_different
    proxies[current_proxy]['used'] = True

    for current_craft, c in enumerate(crafts):
        print("Worker", identification, "now crafting", c)
        start = time.time()
        done = False
        while not done:
            try:
                out = craft(c[0], c[1], proxy)
                if out is None:
                    proxies[current_proxy]['status'] = -1
                    proxies[current_proxy]['used'] = False  # Let go
                    found = False
                    for ind, p in enumerate(proxies):
                        if p['used'] is False and p['status'] > -1:
                            current_proxy = ind
                            proxy = proxies[current_proxy]["parsed"]
                            proxies[current_proxy]['used'] = True  # Grab on
                            found = True
                            break
                    if not found:  # There are no working not-in-use proxies :(
                        spare_crafts.extend(crafts[current_craft:])
                        print("No other proxies exist, worker", identification, "is finished")
                        return
                    handle(crafts[current_craft:], identification, proxy['parsed'], proxy_id_if_different=current_proxy)
                    return
            except Exception as e:
                proxies[current_proxy]['status'] = -1
                proxies[current_proxy]['used'] = False  # Let go
                found = False
                for ind, p in enumerate(proxies):
                    if p['used'] is False and p['status'] > -1:
                        current_proxy = ind
                        proxy = proxies[current_proxy]
                        proxies[current_proxy]['used'] = True  # Grab on
                        found = True
                        break
                if not found:  # There are no working not-in-use proxies :(
                    spare_crafts.append(crafts[current_craft:])
                    print("No other proxies exist, worker", identification, "is finished")
                    return
                handle(crafts[current_craft:], identification, proxy['parsed'], proxy_id_if_different=current_proxy)
                return
            done = True
        calculated_crafts[c[0]+"+"+c[1]] = out
        if out['result'] not in list(base_tree.keys()):
            print(c, out)
            base_tree.update({out['result']: [[c[0], c[1]]]})
        else:
            base_tree[out['result']].append([c[0], c[1]])
        save_tree_and_depth()
        proxies[current_proxy]['status'] = 1
        proxies[current_proxy]['total_calls'] += 1
        if proxies[current_proxy]['total_calls'] == 1:
            proxies[current_proxy]['average_resp_time'] = time.time() - start
        else:
            proxies[current_proxy]['average_resp_time'] = ((proxies[current_proxy]['average_resp_time'] *
                                                            (proxies[current_proxy]['total_calls'] - 1)) +
                                                           (time.time() - start)) / proxies[current_proxy][
                                                              'total_calls']
        print("Worker", identification, "outputted", out, "time=", time.time() - start)

    # Check if there's any spare crafts left for us

    if len(spare_crafts):
        our_crafts = spare_crafts[:]
        print("Worker", identification, "is restarting to run", len(spare_crafts), "more tasks")
        handle(our_crafts, identification, proxy['parsed'], proxy_id_if_different=current_proxy)
    proxies[current_proxy]['used'] = False  # Disconnect
    print("Worker", identification, "finished.")


def schedule(workers, word_set):
    global spare_crafts
    global calculated_crafts
    spare_crafts = []
    calculated_crafts = {}
    futures = []
    with ThreadPoolExecutor(workers) as ex:
        combin = list(itertools.combinations(word_set, 2))
        crafts_to_perform = []
        for c in combin:
            if [c[0], c[1]] not in existing_recipes or [c[1], c[0]] not in existing_recipes:
                crafts_to_perform.append([c[0], c[1]])

        things_per = len(crafts_to_perform) // workers
        remaining_extra = len(crafts_to_perform) % workers
        start = 0
        for worker_index in range(workers):
            #print(handle, crafts_to_perform[start:start + things_per], worker_index, proxies[worker_index]['parsed'])
            if (worker_index + 1) <= remaining_extra:
                ft = ex.submit(handle, crafts_to_perform[start:start + things_per + 1], worker_index, proxies[worker_index]['parsed'])
                start += things_per + 1
                futures.append(ft)
            else:
                ft = ex.submit(handle, crafts_to_perform[start:start + things_per], worker_index, proxies[worker_index]['parsed'])
                start += things_per
                futures.append(ft)
    print(spare_crafts)
    return calculated_crafts


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
existing_recipes = []
def save_tree_and_depth():
    json.dump(base_depth, open('depth.json', 'w'))
    json.dump(base_tree, open('tree.json', 'w'))

def update_existing_recipes():
    global existing_recipes
    values = []
    for val in base_tree.values():
        values.extend(val)
    existing_recipes = values[:]

update_existing_recipes()
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
    proxies = []
    proxies_doc = requests.get('https://spys.one/en/socks-proxy-list', headers={"User-Agent": ua.random,
                                                                                "Content-Type": "application/x-www-form-urlencoded"}).text
    soup = BeautifulSoup(proxies_doc, 'html.parser')
    tables = list(soup.find_all("table"))  # Get ALL the tables

    # Variable definitions
    variables_raw = str(soup.find_all("script")[6]).replace('<script type="text/javascript">', "").replace('</script>',
                                                                                                           '').split(
        ';')[:-1]
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

        raw_port = [i.replace("(", "").replace(")", "") for i in
                    str(address.find("script")).replace("</script>", '').split("+")[1:]]

        port = ""
        for partial_port in raw_port:
            first_variable = variables[partial_port.split("^")[0]]
            second_variable = variables[partial_port.split("^")[1]]
            port += "(" + str(first_variable) + "^" + str(second_variable) + ")+"
        port = js2py.eval_js('function f() {return "" + ' + port[:-1] + '}')()
        proxies.append(
            {"ip": address.get_text(), "port": port, "parsed": f"socks5h://{address.get_text()}:{port}", "status": 0,
             "total_calls": 0, "average_response": 0, "used": False})
    return proxies


# proxies = update_proxies()
# evolved = evolve(base_depth)
#
# print(evolved)

if __name__ == "__main__":
    proxies = update_proxies()
    print(schedule(30, base_depth))


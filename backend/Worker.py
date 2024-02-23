import logging
import random
import warnings

from backend.Proxy import Proxy
from backend.tools import *

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
MAXIMUM_REQUESTS_PER_SECOND = 5
NEW_PROXY_SLEEP = 10


class Worker:
    """
    A class that handles:

    Batch processing of crafts
    Auto rescheduling of proxies when they break


    Scheduler class will be able to add crafts to the Worker when it determines there is rebalancing required

    This class will NOT
    check for already computed crafts
    run error checking
    """

    def __init__(self, all_proxies: list, worker_crafts: list, proxy: Proxy, worker_id: str | int,
                 log_level=logging.INFO):
        self.kill = False
        self.thread = ReturnValueThread(target=Worker.run, args=[self])
        self.all_proxies = all_proxies
        self.worker_crafts = worker_crafts
        self.proxy = proxy
        self.session = requests.Session()
        self.id = worker_id
        self.logger = logging.getLogger(f"Worker({self.id})")
        self.logger.setLevel(log_level)
        self.crafts = []
        self._current_craft_index = 0
        self.batch_size = 5

    def begin_working(self):
        self.thread = ReturnValueThread(target=Worker.run, args=[self])
        self.thread.start()

    def finish_working(self):
        if self.thread.ident is None:
            return False  # Not started
        self.thread.join()
        return True

    def forfeit_tasks(self, how_many):
        if not self.is_working():
            stolen = self.worker_crafts[:how_many+1]
            self.worker_crafts = self.worker_crafts[how_many+1:]
            return stolen
        else:
            available_to_steal = self.worker_crafts[self._current_craft_index+self.batch_size:]
            stolen = available_to_steal[:how_many + 1]
            self.worker_crafts = available_to_steal[how_many + 1:]
            return stolen

    def is_working(self):
        return self.thread.is_alive()

    def run(self):
        s = time.time()

        self._current_craft_index = 0  # Keep track of the current index

        grab_attempt = self.proxy.grab(self)  # Attempt to re

        if not grab_attempt:
            return
        while self._current_craft_index < len(self.worker_crafts):
            batch_start = time.time()
            if self.kill:
                return self.worker_crafts[self._current_craft_index:]

            batch_number = (self._current_craft_index // self.batch_size) + 1  # Current batch number
            total_batch_number = len(self.worker_crafts) // self.batch_size  # Total batches we have to process

            if len(self.worker_crafts) % self.batch_size:  # If there is a remainder, we have to add one.
                total_batch_number += 1

            self.logger.info(f"Now executing batch {batch_number}/"
                             f"{total_batch_number} (Current exec time: {round(time.time() - s, 2)}s)")
            current_crafts = self.worker_crafts[self._current_craft_index:self._current_craft_index + self.batch_size]
            batch_threads = []
            for index, current_craft in enumerate(current_crafts):
                self.logger.debug(f"Job {index + 1} of batch {batch_number} is starting with craft {current_craft}...")
                t = ReturnValueThread(target=craft,
                                      args=[current_craft[0], current_craft[1], self.proxy, 10, self.session])
                t.start()
                batch_threads.append(t)
            results = []
            found_proxy_update = False
            failed_crafts = []
            for index, thread in enumerate(batch_threads):
                result: dict = thread.join()
                self.logger.debug(f"Job {index + 1} of batch {batch_number} returned value: {result}")
                if result["status"] == "success":
                    self.crafts.append([current_crafts[index], result])
                    results.append(result)
                    self.proxy.submit(True, result["time_elapsed"])
                elif result["type"] == "read":
                    self.proxy.submit(False, None, True, False)
                elif result["type"] == "connection":
                    self.proxy.submit(False, None, False, False)
                elif result["type"] == "ratelimit":
                    self.proxy.submit(False, None, True, False,
                                      retry_after=result["penalty"])
                if result["status"] != "success":
                    failed_crafts.append(current_crafts[index])
                    found_proxy_update = True

            if len(failed_crafts) and found_proxy_update:  # One (or more) crafts failed, and we have a new proxy
                self.logger.warning(f"{len(failed_crafts)}/{len(current_crafts)} of batch"
                                    f" {batch_number} failed. (Current proxy: {str(self.proxy)})"
                                    f" Attempting to locate new proxy.")
                self.proxy.withdraw(self)  # Our proxy doesn't work! Get RID OF IT
                self.find_new_proxy()  # Get a new proxy. This function returns when it's found one
                # Needed two lines here because .extend doesn't seem to return anything.
                # The crafts we haven't seen yet
                self.worker_crafts = self.worker_crafts[self._current_craft_index + len(current_crafts):]
                # Add the ones we've seen that just failed
                self.worker_crafts.extend(failed_crafts)

                self._current_craft_index = 0  # Back to the beginning :( not really tho
                continue  # Don't need to run rate limit code here.

            time_total: float = time.time() - batch_start

            delta: float = (len(current_crafts) / MAXIMUM_REQUESTS_PER_SECOND) - time_total

            self._current_craft_index += len(current_crafts)

            if delta > 0 and self._current_craft_index < len(self.worker_crafts):
                # If we are too fast for the rate limit, sleep it off
                time.sleep(delta)
        self.logger.info(f"Finished processing of {len(self.worker_crafts)} jobs.")
        self.proxy.withdraw(self)  # Give our proxy back
        return []

    def find_new_proxy(self):
        grabbed = False
        while not grabbed:
            for proxy in rank_proxies(self.all_proxies):  # Rank proxies so we start with the BEST ONES FIRST
                if proxy.disabled_until <= time.time():  # Ready to TRY AGAIN
                    self.logger.debug(f"Attempting to grab suitable proxy {str(proxy)}...")
                    attempt_to_grab = proxy.grab(self)  # Try to connect to the proxy
                    if attempt_to_grab:  # WE GOT EM BOIS
                        self.logger.info(f"Found new proxy: {str(proxy)}.")
                        grabbed = True
                        self.proxy = proxy
                        break
                    else:
                        self.logger.debug(f"Failed to grab proxy {str(proxy)}")

            if not grabbed:
                self.logger.error(
                    f"Unable to find available, functional proxy! Retrying in {NEW_PROXY_SLEEP} seconds...")
                time.sleep(NEW_PROXY_SLEEP)  # Keep on fruiting for a proxy ig

        return True

    def update_proxies(self, new_proxies: list[Proxy]):
        self.all_proxies = new_proxies

    def update_crafts(self, new_crafts: list[tuple[str] | list[str]]):
        self.worker_crafts = new_crafts

    def __str__(self):
        return self.id

    def __repr__(self):
        return f"Worker({self.id})"


if __name__ == "__main__":  # A short test of Worker (you can mess around with it here :D)
    pick_from = ["Fire", "Water", "Earth", "Ground", "Mars", "Pluto", "Forest", "Rainbow Dash", "Frog", "9/11"]

    to_calculate = []

    for i in range(25):
        to_calculate.append(random.sample(pick_from, 2))

    proxy_1 = Proxy(ip="51.38.50.249", port=9224, protocol="socks5h")
    proxy_2 = Proxy(ip="68.1.210.163", port=4145, protocol="socks5h")
    proxy_3 = Proxy(ip="195.39.233.14", port=44567, protocol="socks5h")

    proxy_3.submit(True, 0.01)
    proxy_3.submit(True, 0.01)
    proxy_3.submit(True, 0.01)
    proxy_3.submit(True, 0.01)

    proxy_2.grab(Worker([], [], proxy_2, "Johnson"))
    proxy_3.grab(Worker([], [], proxy_2, "Johnson"))
    w = Worker([proxy_1, proxy_2, proxy_3], to_calculate, proxy=proxy_1, worker_id="Tyler",
               log_level=logging.DEBUG)

    w.begin_working()
    # w.kill = True
    w.finish_working()
    print(w.crafts)
    print(w.proxy.average_response, w.proxy.total_submissions, w.proxy.total_successes, w.proxy.status,
          w.proxy.disabled_until)

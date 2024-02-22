import logging
import random
import sys
import threading
import time
import warnings

from backend.Proxy import Proxy
from backend.tools import *

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO)
MAXIMUM_REQUESTS_PER_SECOND = 5


class ReturnValueThread(threading.Thread):
    """
    A very similar version of threading.Thread that returns the value of the thread process
    with Thread.join().
    This allows for batch processing to work.
    """

    def __init__(self, *args, **kwargs):
        """
        Initalize the ReturnValueThread
        :param args:
        :param kwargs:
        """
        super().__init__(*args, **kwargs)
        self.result = None

    def run(self):
        """
        Run the ReturnValueThread
        :return:
        """
        if self._target is None:
            return  # could alternatively raise an exception, depends on the use case
        try:
            self.result = self._target(*self._args, **self._kwargs)
        except Exception as exc:
            print(f'{type(exc).__name__}: {exc}', file=sys.stderr)  # properly handle the exception

    def join(self, *args, **kwargs):
        """
        The highlight of the class. Returns the thread result upon ending.
        :param args:
        :param kwargs:
        :return:
        """
        super().join(*args, **kwargs)
        return self.result


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

    def __init__(self, all_proxies: list, worker_crafts: list, proxy: Proxy, worker_id: str | int):
        self.thread = ReturnValueThread(target=Worker.run, args=[self])
        self.all_proxies = all_proxies
        self.worker_crafts = worker_crafts
        self.proxy = proxy
        self.session = requests.Session()
        self.id = worker_id
        self.logger = logging.getLogger(f"Worker({self.id})")
        self.crafts = []

    def begin_working(self):
        self.thread = ReturnValueThread(target=Worker.run, args=[self])
        self.thread.start()

    def finish_working(self):
        if self.thread.ident is None:
            return False  # Not started
        self.thread.join()
        return True

    def is_working(self):
        return self.thread.is_alive()

    def run(self):
        s = time.time()

        current_craft_index = 0  # Keep track of the current index
        total_waited_time = 0  # How long have we slept for?
        total_requested = 0
        batch_size = 5  # The batch processing size

        grab_attempt = self.proxy.grab(self)  # Attempt to re

        if not grab_attempt:
            return
        while current_craft_index < len(self.worker_crafts):
            self.logger.info(f"Now executing batch {(current_craft_index // batch_size) + 1}/"
                             f"{round(len(self.worker_crafts) / batch_size)} (Current exec time: {round(time.time() - s, 2)}s)")
            current_crafts = self.worker_crafts[current_craft_index:current_craft_index + batch_size]
            batch_threads = []
            for current_craft in current_crafts:
                t = ReturnValueThread(target=craft,
                                      args=[current_craft[0], current_craft[1], self.proxy, 15, self.session])
                t.start()
                batch_threads.append(t)
            results = []
            for index, thread in enumerate(batch_threads):
                result: dict = thread.join()
                if result["status"] == "success":
                    self.crafts.append([current_crafts[index], result])
                    results.append(result)
                    self.proxy.submit(True, result["time_elapsed"])
                elif result["status"] == "read":
                    self.proxy.submit(False, None, True, False)
                elif result["status"] == "connection":
                    self.proxy.submit(False, None, False, False)
                elif result["status"] == "ratelimit":
                    self.proxy.submit(False, None, True, False,
                                      retry_after=result["penalty"] )

            time_total: float = time.time() - s

            delta: float = (total_requested / MAXIMUM_REQUESTS_PER_SECOND) - time_total

            current_craft_index += batch_size

            if delta > 0 and current_craft_index < len(self.worker_crafts):
                # If we are too fast for the rate limit, sleep it off
                time.sleep(delta)
                total_waited_time += delta

        print("TOTAL ELAPSED TIME", time.time() - s)
        print("SLEPT FOR", total_waited_time)
        print("PROCESSING TIME", time.time() - s - total_waited_time)

    def find_new_proxy(self):
        pass

    def update_proxies(self, new_proxies: list[Proxy]):
        self.all_proxies = new_proxies

    def update_crafts(self, new_crafts: list[tuple[str] | list[str]]):
        self.worker_crafts = new_crafts



if __name__ == "__main__":
    pick_from = ["Fire", "Water", "Earth", "Ground", "Mars", "Pluto", "Forest", "Rainbow Dash", "Frog", "9/11"]

    to_calculate = []

    for i in range(25):
        to_calculate.append(random.sample(pick_from, 2))

    w = Worker([], to_calculate, proxy=Proxy(ip="68.1.210.163", port=4145, protocol="socks5h"), worker_id="Tyler")
    w.begin_working()
    w.finish_working()
    print(w.crafts)
    print(w.proxy.average_response, w.proxy.total_submissions, w.proxy.total_successes, w.proxy.status, w.proxy.disabled_until)

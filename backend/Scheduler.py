import logging
from backend.Proxy import Proxy
from backend.Worker import Worker
from backend.tools import *


class Scheduler:
    def __init__(self, crafts: list[list[str] | tuple[str]], proxies: list[Proxy], name: str = "Default", log_level: str = logging.INFO):
        self.proxies = proxies
        self.crafts = crafts
        self.workers = []
        self.max_workers = 5
        self.minimum_jobs_per_worker = 10
        self.kill = False
        self.name = name
        self.logger = logging.getLogger(f"Scheduler({name})")
        self.logger.setLevel(log_level)

    def start(self):
        total_amount_of_crafts = len(self.crafts)

        crafts_per_worker = total_amount_of_crafts // self.max_workers

        remaining_crafts = total_amount_of_crafts % self.max_workers
        current_craft_index = 0
        rank = rank_proxies(self.proxies)
        for id in range(self.max_workers):
            if remaining_crafts:
                extra = 1
            else:
                extra = 0

            addendum = crafts_per_worker+extra

            self.workers.append(Worker(self.proxies, self.crafts[current_craft_index:current_craft_index+addendum], rank[id], f"Tyler-{id}"))

            if remaining_crafts:
                remaining_crafts -= 1

            current_craft_index += addendum

        raw_crafts = []
        start_time = time.time()
        for w in self.workers:
            w.begin_working()
        base_completed = 0
        while True:
            completed = base_completed
            remove_these = []
            for w in self.workers:
                completed += len(w.crafts)
                if not w.is_working():
                    raw_crafts.extend(w.crafts)
                    remove_these.append(w)
            for w in remove_these:
                base_completed += len(w.crafts)
                self.workers.remove(w)

            complete_percentage = 100 * completed / total_amount_of_crafts

            if complete_percentage:
                current_time = time.time() - start_time

                total_time = (100 / complete_percentage) * current_time

                remaining_time = round(total_time - current_time, 2)

            else:
                remaining_time = "inf"

            self.logger.info(f"Current overall progress: {completed}/{total_amount_of_crafts} ({round(complete_percentage, 2)}%, ETA: {remaining_time}s)")
            time.sleep(1)  # Reduced CPU usage by 78% on my computer
            if not len(self.workers):
                break



        out = {}

        for c in raw_crafts:
            input_craft = c[0]

            output_result = c[1]
            key = output_result["result"] + "`" + output_result["emoji"]
            if key not in out.keys():
                out.update({key: [input_craft]})
            else:
                if input_craft not in out[key] and [input_craft[1], input_craft[0]] not in out[key]:
                    out[key].append(input_craft)

        return out



import pickle
import json
import os
import config
import pendulum as pm
import random


class WorkStack():
    """
    Stack of Tasks that represents work over time
    """
    ws_dir = config.ws_dir

    def __init__(self, ago=0, init_type=None):
        self.meta = self._load_metafile()
        self.__init_emojis__()
        if self._init_json_and_log():
            init = Task("init", ago)
            self.array = [init]
            self.stack = [self.array[-1]]
            self.yyyymmdd = self.top().start.format("YYYYMMDD")
            self.log("🚀 workstack initialized 🚀", ago)
        else:
            self._load_json()
        wl = self.log

    # i should have functions that track some data points for the day
    # units of alcohol consumed, mood, times I ate out, time spent watching tv,
    # time spent on internet, what kind of food did i purchase, happy vs sad
    # did I

    def _init_json_and_log(self):
        month_dir = self.ws_dir / pm.now().format("YYYYMM")
        if not month_dir.exists():
            month_dir.mkdir()
            print(
                f"created: {month_dir} {self.meta['emoji']['all']['calendar']}")
        self.json_path = month_dir / f'{pm.now().format("DD")}.json'
        self.log_path = month_dir / f'{pm.now().format("DD")}.log'
        self.pickle_path = month_dir / f'{pm.now().format("DD")}.pickle'
        if self.json_path.exists() == False:
            self.json_path.touch()
            self.log_path.touch()
            self.pickle_path.touch()
            return True
        else:
            return False

    def top(self):
        return self.stack[-1]

    def push(self, work_type, ago=0):
        #assert work_type in self.meta['types']
        task = Task(work_type, ago=ago)
        self.array.append(task)
        self.stack.append(self.array[-1])
        self.log(
            f"💯 pushed {task.type} on to stack 💯 [{self.roll_emoji()}]", ago=ago)
        self.save()
        return self

    def log(self, msg, ago=0):
        with open(self.log_path, 'a') as fh:
            line = f'[{pm.now().subtract(minutes=ago).format("HH:mm:ss")}][{self.emoji()}][{self.top().type}] {msg}'
            fh.write(f"{line}\n")
            print(line)
        self.top().worklog.append(line)

    def save(self):
        with open(self.json_path, 'w') as fh:
            json.dump(self.__to_dict__(), fh, ensure_ascii=False)
        with open(self.pickle_path, 'wb') as fh:
            pickle.dump(self, fh)

    def pop(self, ago=0):
        end_time = pm.now().subtract(minutes=ago)
        self.top().end = end_time
        if self.top().type == 'init':
            self.log(f"closing workstack {self.roll_emoji()}")
            self.save()
        else:
            self.log(
                f"pop! done with {self.top().type}! {self.roll_emoji()}", ago)
            self.stack.pop()
            self.log(f"returned to {self.top().type}", ago)
            self.save()
        return self

    def pushpop(self, work_type, push_ago, pop_ago=0, msg=None, tags=[]):
        task = Task(work_type, ago=push_ago, tags=[])
        task.end = pm.now().subtract(minutes=pop_ago)
        # task.work_log - should be able to pass some notes
        self.array.append(task)
        self.stack.append(self.array[-1])
        self.log(
            f"💯 pushed {task.type} on to stack 💯 [{self.roll_emoji()}]", ago=push_ago)
        if msg:
            assert isinstance(msg, str)
            self.log(msg, ago=int((push_ago+pop_ago)/2))
        self.log(
            f"pop! (via pushpop at {pm.now().format('HH:mm')})", ago=pop_ago)
        self.stack.pop()
        self.save()
        return self

    def pushpopfromlast(self, pop_ago=0, msg=None):
        return self.pushpop(mago(self.array[-1].end.format("HH:mm")), pop_ago, msg)

    def tag(self, t):
        t = str(t)
        assert isinstance(t, str)
        assert " " not in t
        self.top().tags.append(t)
        return self

    def mdlog(self, cell=-1, ago=0):
        import nbformat
        nb = get_notebook_name()
        cells = [c for c in nbformat.read(
            nb, 4).cells if c.get("cell_type") == "markdown"]
        self.log(cells[cell].get('source'), ago)

    def poppush(self, work_type, ago=0, tags=[]):
        self.log(f"pop! done with {self.top().type}! {self.roll_emoji()}", ago)
        self.top().end = pm.now().subtract(minutes=ago)
        self.stack.pop()
        task = Task(work_type, ago, tags=tags)
        self.array.append(task)
        self.stack.append(self.array[-1])
        self.log(
            f"💯 pushed {task.type} on to stack 💯 [{self.roll_emoji()}]", ago)
        return self

    def calculate_task_duration(self):
        t_now = pm.now()
        for t in self.array:
            t.duration = None
            t.rank = None
            if t.end == None:
                t._end = t_now
            else:
                t._end = t.end
        completed = [t for t in self.array if t._end != None]
        rank = 1
        while (None in [t.duration for t in completed]):
            for t in completed:
                above_tasks = [
                    task for task in self.array if task.start > t.start and task.start < t._end]
                above_duration = [task.duration for task in above_tasks]
                for above in above_tasks:
                    assert above._end <= t._end
                if len(above_tasks) == 0 and t.duration == None:
                    t.duration = (t._end - t.start).total_hours()
                    t.rank = rank
                elif None not in above_duration and t.duration == None:
                    t.duration = (t._end - t.start).total_hours() - \
                        sum(above_duration)
                    t.rank = rank
            rank += 1

        for t in self.array:
            other_tasks = [task for task in self.array if task != t]
            below_tasks = [below for below in other_tasks if
                           below.start < t.start and below._end >= t._end]
            t.rank = len(below_tasks)

    def graph(self):
        import matplotlib.pyplot as plt
        from matplotlib import cm

        def get_color(n):
            """
            https://matplotlib.org/tutorials/colors/colormaps.html
            """
            # return cm.tab20c(n*2)
            return cm.Set3(n)

        graph_start = pm.datetime(self.array[0].start.year, self.array[0].start.month,
                                  self.array[0].start.day, self.array[0].start.hour, tz=self.array[0].start.timezone)
        type_list = list(set([t.type for t in self.array]))

        ranks = [[] for _ in list(set([t.rank for t in self.array]))]
        rank_colors = [[] for _ in list(set([t.rank for t in self.array]))]

        bar_height = 6
        bar_width = 5

        self.calculate_task_duration()
        fig, ax = plt.subplots(figsize=(20, 10))
        # plt.figure()
        for t in self.array:
            bar = ((t.start - graph_start).in_seconds(),
                   (t._end-t.start).in_seconds())
            color = get_color(type_list.index(t.type))
            ranks[t.rank].append(bar)
            rank_colors[t.rank].append(color)

        for i, r in enumerate(ranks):
            ax.broken_barh(r, (bar_height, bar_width),
                           facecolors=rank_colors[i], ec="black")
            bar_height += 6

        ticks = []
        labels = []
        starts = [t.start for t in self.array]
        ends = [t.end for t in self.array]
        tick = graph_start
        if None not in ends:
            latest_time = max(ends)
        else:
            latest_time = pm.now()
        while True:
            ticks.append((tick-graph_start).in_seconds())
            labels.append(tick.format("hh:mm"))
            tick = tick.add(minutes=30)
            if (tick - latest_time).in_minutes() >= 45:
                break

        ax.set_xticks(ticks)
        ax.set_xticklabels(labels)
        ax.grid(True)

        import matplotlib.patches as mpatch
        proxy_artists = [mpatch.Rectangle(
            (0, 0), 1, 1, fc=get_color(i)) for i, v in enumerate(type_list)]
        legend_labels = [t for t in type_list]
        ax.legend(proxy_artists, legend_labels)

        plt.show()

    def worklog_notebook_markdowncell(): pass
    def to_json(self): pass
    def write_log(self): pass
    def from_json(self): pass

    def _ask_for_type(self):
        self.print_types()
        type_num = input("--> ")
        return self.meta["types"][int(type_num)-1]

    def print_types(self, limit=10):
        ty = self.meta["types"]
        for i, t in enumerate(ty):
            print(f"{i+1}) {t}")
            if i + 1 == limit:
                break

    def _load_json(self):
        with open(self.json_path, "r") as fh:
            data = json.load(fh)
        self.yyyymmdd = data["yyyymmdd"]
        self.array = [Task.from_json(json.dumps(task))
                      for task in data["array"]]
        self.stack = []
        for pointer in data["stack"]:
            for i in range(len(self.array)):
                if pointer == self.array[i].start.format("YYYYMMDD-HH:mm:ss.SSSSSS-z"):
                    self.stack.append(self.array[i])
                    break

    def __json__(self):
        return json.dumps(self.__to_dict__())

    def __to_dict__(self):
        return {
            "array": [i.__to_dict__() for i in self.array],
            # timestamp of task should serve as a unique id
            # for the task and can be used to track
            # what is on the stack
            "stack": [i.start.format("YYYYMMDD-HH:mm:ss.SSSSSS-z") for i in self.stack],
            "yyyymmdd": self.yyyymmdd
        }

    def backup(self):
        pass

    def __repr__(self):
        return f"WorkStack({[i for i in self.stack]})"

    def emoji(self, name=None):
        if name:
            return self.meta["emoji"]["all"][name]
        else:
            return random.choice(self.meta["emoji"]["list"])

    def roll_emoji(self, count=None):
        output = ''
        if count == None:
            count = random.choice([1, 2, 3])
        for _ in range(count):
            output += self.emoji()
        return output

    def _load_metafile(self):
        metafile = str(config.meta_file)  # contains a list of emojis
        with open(metafile, "r") as mf:
            return json.load(mf)

    def __init_emojis__(self):
        self.rocket = self.meta['emoji']['all']['rocket']
        self.beers = self.meta['emoji']['all']['clinking beer mugs']
        self.atom = self.meta['emoji']['all']['atom symbol']
        self.onehundred = self.meta['emoji']['all']['hundred points']
        self.old_key = self.meta['emoji']['all']['old key']

    def name_x_emoji(self, x=10, return_list=False, category='all'):
        while category not in list(self.meta['emoji'].keys()):
            print("enter a valid emoji category")
            print(self.meta['emoji'].keys())
            category = input()
        names = random.sample(list(self.meta['emoji'][category].keys()), x)
        if return_list:
            return names
        else:
            print(''.join(map(lambda x: str(x)+'\n', names))[:-1])
            return None

    def name_x_people_emoji(self, x=10, return_list=False):
        return self.name_x_emoji(x, return_list, category='people')

    def name_x_nature_emoji(self, x=10, return_list=False):
        return self.name_x_emoji(x, return_list, category='nature')

    def name_x_activity_emoji(self, x=10, return_list=False):
        return self.name_x_emoji(x, return_list, category='activity')

    def name_x_objects_emoji(self, x=10, return_list=False):
        return self.name_x_emoji(x, return_list, category='objects')

    def name_x_places_emoji(self, x=10, return_list=False):
        return self.name_x_emoji(x, return_list, category='places')

    def name_x_symbols_emoji(self, x=10, return_list=False):
        return self.name_x_emoji(x, return_list, category='symbols')

    def name_x_food_emoji(self, x=10, return_list=False):
        return self.name_x_emoji(x, return_list, category='food')


def get_notebook_name():
    """
    Return the full path of the jupyter notebook.
    """
    import json
    import os.path
    import re
    import ipykernel
    import requests
    from requests.compat import urljoin
    try:  # Python 3 (see Edit2 below for why this may not work in Python 2)
        from notebook.notebookapp import list_running_servers
    except ImportError:  # Python 2
        import warnings
        from IPython.utils.shimmodule import ShimWarning
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=ShimWarning)
            from IPython.html.notebookapp import list_running_servers
    ###
    kernel_id = re.search('kernel-(.*).json',
                          ipykernel.connect.get_connection_file()).group(1)
    servers = list_running_servers()
    for ss in servers:
        response = requests.get(urljoin(ss['url'], 'api/sessions'),
                                params={'token': ss.get('token', '')})
        for nn in json.loads(response.text):
            if nn['kernel']['id'] == kernel_id:
                relative_path = nn['notebook']['path']
                return os.path.join(ss['notebook_dir'], relative_path)


class Task():
    def __init__(self, work_type, ago=0, tags=[]):
        self.type = work_type
        self.start = pm.now().subtract(minutes=ago)
        self.worklog = []
        assert isinstance(tags, list)
        for tag in tags:
            assert isinstance(tag, str)
            assert " " not in tag
        self.tags = tags
        self.duration = None
        self.rank = None
        self.end = None

    def __json__(self):
        return json.dumps(self.__to_dict__())

    def from_json(json_str):
        data = json.loads(json_str)
        task = Task(data["type"])
        task.start = pm.from_format(
            data["start"], "YYYYMMDD-HH:mm:ss.SSSSSS-z")
        if data["end"] != None:
            task.end = pm.from_format(
                data["end"], "YYYYMMDD-HH:mm:ss.SSSSSS-z")
        else:
            task.end = None
        task.worklog = data["worklog"]
        task.tags = data["tags"]
        task.duration = data["duration"]
        task.rank = data["rank"]
        return task

    def __repr__(self):
        return f"Task('{self.type}')"

    def __str__(self):
        return f"Task('{self.type}')"

    def __to_dict__(self):
        if self.end == None:
            end = None
        else:
            end = self.end.format("YYYYMMDD-HH:mm:ss.SSSSSS-z")
        return {
            "type": self.type,
            "start": self.start.format("YYYYMMDD-HH:mm:ss.SSSSSS-z"),
            "worklog": self.worklog,
            "tags": self.tags,
            "duration": self.duration,
            "rank": self.rank,
            "end": end
        }


ws = WorkStack

import multiprocessing
import threading


class TaskProxy(threading.Thread):
    def __init__(self, fn, args=tuple()):
        super(TaskProxy, self).__init__()
        self.daemon = True
        self.fn = fn
        self.args = args

    def run(self):
        p = multiprocessing.Process(target=self.fn, args=self.args)
        p.start()
        p.join()

from concurrent.futures import ThreadPoolExecutor
from threading import Lock


def decrement_num_active_threads(future, ctpe):
    ctpe.num_active_threads_lock.acquire()
    ctpe.num_active_threads -= 1
    ctpe.num_active_threads_lock.release()


class ConsumerThreadPoolExecutor(ThreadPoolExecutor):
    def __init__(self, max_workers):
        super().__init__(max_workers)

        self.max_workers = max_workers
        self.num_active_threads = 0
        self.num_active_threads_lock = Lock()

    def get_num_active_threads(self):
        self.num_active_threads_lock.acquire()
        num_active_threads = self.num_active_threads
        self.num_active_threads_lock.release()
        return num_active_threads

    def _increment_num_active_threads(self):
        self.num_active_threads_lock.acquire()
        self.num_active_threads += 1
        self.num_active_threads_lock.release()

    def _decrement_num_active_threads(self):
        self.num_active_threads_lock.acquire()
        self.num_active_threads -= 1
        self.num_active_threads_lock.release()

    def submit(self, fn, *args, **kwargs):
        future = super().submit(fn, *args, **kwargs)
        future.add_done_callback(
            lambda fut: self._decrement_num_active_threads())
        self._increment_num_active_threads()
        return future

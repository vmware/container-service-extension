from concurrent.futures import ThreadPoolExecutor
from threading import Lock

# import container_service_extension.logger as logger


class ConsumerThreadPoolExecutor(ThreadPoolExecutor):
    def __init__(self, max_workers):
        super().__init__(max_workers=max_workers,
                         initializer=lambda: self.increment_num_total_threads())  # noqa: E501

        self.max_workers = max_workers
        self.num_active_threads = 0
        self.num_active_threads_lock = Lock()
        self.num_total_threads = 0
        self.num_total_threads_lock = Lock()

    def increment_num_total_threads(self):
        self.num_total_threads_lock.acquire()
        try:
            self.num_total_threads += 1
        finally:
            self.num_total_threads_lock.release()

    def get_num_total_threads(self):
        self.num_total_threads_lock.acquire()
        try:
            num_total_threads = self.num_total_threads
        finally:
            self.num_total_threads_lock.release()
        return num_total_threads

    def get_num_active_threads(self):
        self.num_active_threads_lock.acquire()
        try:
            num_active_threads = self.num_active_threads
        finally:
            self.num_active_threads_lock.release()
        return num_active_threads

    def _increment_num_active_threads(self):
        self.num_active_threads_lock.acquire()
        try:
            self.num_active_threads += 1
        finally:
            self.num_active_threads_lock.release()

    def _decrement_num_active_threads(self):
        self.num_active_threads_lock.acquire()
        try:
            self.num_active_threads -= 1
        finally:
            self.num_active_threads_lock.release()

    def submit(self, fn, *args, **kwargs):
        future = super().submit(fn, *args, **kwargs)
        future.add_done_callback(
            lambda fut: self._decrement_num_active_threads())
        self._increment_num_active_threads()
        return future

    def max_threads_busy(self):
        """Return bool to indicate if max_workers are busy."""
        return self.get_num_active_threads() == self.max_workers

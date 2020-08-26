from concurrent.futures import ThreadPoolExecutor
from threading import Lock

# import container_service_extension.logger as logger


class ConsumerThreadPoolExecutor(ThreadPoolExecutor):
    def __init__(self, max_workers):
        super().__init__(max_workers)

        self.max_workers = max_workers
        self.num_active_threads = 0
        # logger.SERVER_LOGGER.info(f'num_active_threads: '
        #                           f'{self.num_active_threads}')
        self.num_active_threads_lock = Lock()

    def get_num_active_threads(self):
        self.num_active_threads_lock.acquire()
        num_active_threads = self.num_active_threads
        self.num_active_threads_lock.release()
        return num_active_threads

    def _increment_num_active_threads(self):
        self.num_active_threads_lock.acquire()
        self.num_active_threads += 1
        # logger.SERVER_LOGGER.info(f'increment, num_active_threads: '
        #                           f'{self.num_active_threads}')
        self.num_active_threads_lock.release()

    def _decrement_num_active_threads(self):
        self.num_active_threads_lock.acquire()
        self.num_active_threads -= 1
        # logger.SERVER_LOGGER.info(f'decrement, num_active_threads: '
        #                           f'{self.num_active_threads}')
        self.num_active_threads_lock.release()

    def submit(self, fn, *args, **kwargs):
        future = super().submit(fn, *args, **kwargs)
        future.add_done_callback(
            lambda fut: self._decrement_num_active_threads())
        self._increment_num_active_threads()
        return future

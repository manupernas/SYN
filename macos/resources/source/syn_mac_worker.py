"""Daemon-only short-lived UI thumbnail workers for SYN-Mac.

Only channel artwork and posters use this pool; DVR and mpv are untouched.
A running HTTP logo request must not hold the Python process open after
its GTK window has closed. Queued jobs can be cancelled on exit.
"""
from concurrent.futures import Future
from queue import Queue, Empty
from threading import Lock, Thread


class DaemonWorkerPool:
    def __init__(self, max_workers=4, thread_name_prefix='syn-asset'):
        self._queue = Queue()
        self._lock = Lock()
        self._closed = False
        self._threads = []
        for index in range(max_workers):
            thread = Thread(target=self._run, daemon=True,
                            name=f'{thread_name_prefix}-{index}')
            thread.start()
            self._threads.append(thread)

    def submit(self, fn, *args, **kwargs):
        future = Future()
        with self._lock:
            if self._closed:
                raise RuntimeError('Worker pool cerrado')
            self._queue.put((future, fn, args, kwargs))
        return future

    def _run(self):
        while True:
            task = self._queue.get()
            if task is None:
                self._queue.task_done()
                return
            future, fn, args, kwargs = task
            try:
                if future.set_running_or_notify_cancel():
                    try:
                        future.set_result(fn(*args, **kwargs))
                    except BaseException as exc:
                        future.set_exception(exc)
            finally:
                self._queue.task_done()

    def shutdown(self, wait=False, cancel_futures=True):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if cancel_futures:
                while True:
                    try:
                        task = self._queue.get_nowait()
                    except Empty:
                        break
                    if task is not None:
                        task[0].cancel()
                    self._queue.task_done()
            for _ in self._threads:
                self._queue.put(None)
        if wait:
            for thread in self._threads:
                thread.join()

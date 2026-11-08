"""Single-process bounded CPU work with cooperative response deadlines."""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException


class Deadline:
    def __init__(self, seconds):
        self.end = time.monotonic() + seconds
        self.cancelled = threading.Event()
        self.guard = None

    def check(self):
        if self.cancelled.is_set() or time.monotonic() >= self.end:
            raise HTTPException(504, "Operation timed out. Refresh the collection before retrying.")
        if self.guard:
            self.guard()


class BoundedExecutor:
    def __init__(self, queue_size, timeout):
        self.timeout = timeout
        self.slots = threading.BoundedSemaphore(1 + queue_size)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="semantic-analysis")
        self.lock = threading.Lock()
        self.outstanding = 0

    async def run(self, operation, pin=lambda: None, release=lambda: None):
        if not self.slots.acquire(blocking=False):
            raise HTTPException(503, "Analysis capacity is full. Try again shortly.", headers={"Retry-After": "2"})
        control = Deadline(self.timeout)
        try:
            pin()
        except BaseException:
            self.slots.release()
            raise
        with self.lock:
            self.outstanding += 1

        def work():
            control.check()
            value = operation(control)
            control.check()
            return value

        def finished(future):
            try:
                release()
            finally:
                with self.lock:
                    self.outstanding -= 1
                self.slots.release()

        try:
            future = self.pool.submit(work)
        except BaseException:
            finished(None)
            raise
        future.add_done_callback(finished)
        wrapped = asyncio.wrap_future(future)
        # Consume late exceptions after an HTTP timeout/disconnection.
        wrapped.add_done_callback(lambda f: f.exception() if not f.cancelled() else None)
        try:
            return await asyncio.wait_for(asyncio.shield(wrapped), self.timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError) as error:
            control.cancelled.set()
            future.cancel()  # Queued jobs stop; running native inference cannot be killed.
            if isinstance(error, asyncio.CancelledError):
                raise
            raise HTTPException(504, "Operation timed out. Refresh the collection before retrying.") from error

    def close(self):
        self.pool.shutdown(wait=True, cancel_futures=True)

"""Ported from scheduler.h, scheduler.c, and scheduler.wren.

The original manages a queue of suspended Wren `Fiber`s and resumes them
from native (libuv) callbacks when an asynchronous operation completes --
`schedulerResume()` / `schedulerFinishResume()` / `schedulerResumeError()` in
scheduler.c, mirrored by `resume_()` / `await_()` / `runNextScheduled_()` in
scheduler.wren.

Python's `asyncio` provides fiber-style suspend/resume natively via
coroutines, so this port keeps the same class name and method names but
implements them on top of `asyncio` instead of hand-rolled fiber transfers.
"""

import asyncio


class Scheduler:
    """Ported from `Scheduler` in scheduler.wren."""

    # Originally: `__scheduled` module-level list in scheduler.wren.
    _scheduled = []

    @staticmethod
    def add(callable_):
        """Schedules [callable_] (a zero-arg callable returning a coroutine
        or awaitable) to run as a new task.

        Originally:
            static add(callable) {
              if (__scheduled == null) __scheduled = []
              __scheduled.add(Fiber.new {
                callable.call()
                runNextScheduled_()
              })
            }
        """
        Scheduler._scheduled.append(asyncio.ensure_future(Scheduler._run(callable_)))

    @staticmethod
    async def _run(callable_):
        await callable_()

    @staticmethod
    async def await_(fn):
        """Runs [fn] and waits for it to complete.

        Originally:
            static await_(fn) {
              fn.call()
              return Scheduler.runNextScheduled_()
            }
        In the original, this suspended the current fiber until native code
        resumed it. With asyncio, awaiting the coroutine *is* the suspend.
        """
        return await fn()

    @staticmethod
    async def run_all():
        """Waits for every task scheduled via `add()` to finish.

        Not present in the original (which relied on the C-side event loop
        driving fiber resumption); added so a Python entry point has a way
        to drain scheduled work.
        """
        while Scheduler._scheduled:
            pending = Scheduler._scheduled
            Scheduler._scheduled = []
            await asyncio.gather(*pending)

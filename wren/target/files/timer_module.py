"""Ported from timer.c and timer.wren.

The original used a libuv timer (timerStartTimer() in timer.c) resumed
through the Scheduler once it fired. Python's asyncio has sleeping built
in, so `Timer.sleep()` awaits `asyncio.sleep()` directly instead of going
through a native timer + fiber resume.
"""

import asyncio

from scheduler_module import Scheduler


class Timer:
    """Ported from `Timer` in timer.wren."""

    @staticmethod
    async def sleep(milliseconds):
        """Originally:
            static sleep(milliseconds) {
              if (!(milliseconds is Num)) Fiber.abort("Milliseconds must be a number.")
              if (milliseconds < 0) Fiber.abort("Milliseconds cannot be negative.")
              return Scheduler.await_ { startTimer_(milliseconds, Fiber.current) }
            }
        """
        if not isinstance(milliseconds, (int, float)):
            raise ValueError("Milliseconds must be a number.")
        if milliseconds < 0:
            raise ValueError("Milliseconds cannot be negative.")

        async def start_timer():
            # Originally: startTimer_() -> foreign call into timerStartTimer()
            # in timer.c, which used uv_timer_start().
            await asyncio.sleep(milliseconds / 1000.0)

        return await Scheduler.await_(start_timer)

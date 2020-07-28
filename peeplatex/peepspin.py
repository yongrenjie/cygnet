"""
peepspin.py
-----------

Asynchronous context manager that provides spinner functionality.
"""

import sys
import asyncio
from itertools import cycle


class Spinner():
    """
    Context manager that can start and stop a spinner.

    async with Spinner(message, total, ...) as spinner:
        # code goes here
        spinner.increment()   # if needed
    """

    def __init__(self, message, total, units="", fstr=None):
        """
        message (str) - the message to display to the user while it's running
        total (float) - the number of tasks to run, or the number that it
                        should show when completed
        units (str)   - the units by which progress is measured
        fstr (str)    - a format string (to be fleshed out...)
        """
        self.message = message
        self.total = total
        self.units = units
        self.fstr = fstr
        self.done = 0      # running counter of tasks done
        self.time = 0      # time taken to run the tasks

    async def __aenter__(self):
        self.task = asyncio.create_task(self.run())
        return self

    async def run(self):
        write = sys.stdout.write
        flush = sys.stdout.flush
        try:
            for c in cycle("|/-\\"):
                full_message = (f"{c} {self.message} "
                                f"({self.done}/{self.total}{self.units})")
                write(full_message)
                flush()
                await asyncio.sleep(0.1)
                self.time += 0.1
                write('\x08' * len(full_message))
                flush()
        except asyncio.CancelledError:
            write('\x08' * len(full_message))
            flush()
            full_message = (f"- {self.message} "
                            f"({self.total}/{self.total}{self.units})")
            write(full_message)
            print()

    def increment(self, inc):
        """
        Increments the spinner's progress counter.
        """
        self.done += inc

    async def __aexit__(self, exc_type, exc_value, traceback):
        self.task.cancel()
        # We make sure that self.task is really cancelled before exiting, or
        # else it can mess up subsequent output quite badly.
        try:
            await self.task
        except asyncio.CancelledError:  # ok, it's really done
            pass

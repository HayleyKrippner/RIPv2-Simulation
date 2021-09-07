# ----------------------------------- COSC364 Assignment 1 --------------------------------
# This is the Timer class. It does the following:
#   1. initializing a timer
#   2.

# Authors: Hayley Krippner, Sarah Bealing

import asyncio


class Timer:
    """
    Timer class

    Used by Router class for storing time since an entry was updated.
    Counts DOWN from start time and triggers Router method when reaches zero.
    """

    def __init__(self, start_time, router, destination, is_periodic_update=False):

        self.current_time = start_time
        self.router = router
        self.destination = destination  # The destination for the entry we are timing
        self.is_periodic_update = is_periodic_update

        if self.is_periodic_update:
            print(f"[Periodic Update Timer] initialized timer to {start_time}")
        else:
            # either garbage or route timeout timer
            print(f"[Routing Entry Timer] initialized timer to {start_time}")

    def reset(self, new_time):
        """
        Resets a timer to the new time, new_time

        INPUTS: new_time, the time that the Timer will be reset to.
        OUTPUTS: N/A
        """

        if self.is_periodic_update:
            print(f"[Periodic Update Timer] Resetting timer to {new_time} seconds")
        else:
            # either garbage or route timeout timer
            print(f"[Routing Entry Timer] Resetting timer to {new_time} seconds")
        self.current_time = new_time

    async def countdown(self):
        """
        Reduces the timer of the timer in increments of 1 second, until it reaches 0 seconds.
        Informs the Router that the timer belongs to when the timer ends.

        INPUTS: N/A
        OUTPUTS: N/A
        """

        while self.current_time > 0:
            self.current_time -= 1
            await asyncio.sleep(1)  # Block by 1 second

        # tells Router that this timer has timed out
        self.router.timeout_occurred(self.destination, self.is_periodic_update)

    async def start(self):
        """
        Creates and starts an asynchronous timer countdown task.

        INPUTS: N/A
        OUTPUTS: N/A
        """

        countdown_task = asyncio.create_task(self.countdown())
        # async entry into timer class
        await asyncio.wait({countdown_task}, return_when=asyncio.FIRST_COMPLETED)

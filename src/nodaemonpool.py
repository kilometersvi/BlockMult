# multiprocessing with daemon (from https://stackoverflow.com/questions/6974695/python-process-pool-non-daemonic)
# allows child processes to create more children
# modified by miles for use with multiprocess library (over multiprocessing library)

import multiprocess
# We must import this explicitly, it is not imported by the top-level
# multiprocessing module.
import multiprocess.pool

import time
from random import randint


class NoDaemonProcess(multiprocess.Process):
    # make 'daemon' attribute always return False
    # daemon gets set to get_context, unless in init as kw argument context=
    # but this overrides that instance variable
        
    def _get_daemon(self):
        return False
    def _set_daemon(self, value):
        pass
    daemon = property(_get_daemon, _set_daemon)



# We sub-class multiprocessing.pool.Pool instead of multiprocessing.Pool
# because the latter is only a wrapper function, not a proper class.
class NoDaemonPool(multiprocess.pool.Pool):
    #Process = NoDaemonProcess # old solution

    #with multiprocess, need to manually remove ctx, which is used for other purposes in multiprocess (compared to multiprocessing)
    @staticmethod
    def Process(ctx, *args, **kwds):
        #print(f"discarded ctx: {ctx}")
        return NoDaemonProcess(*args, **kwds)

"""
# other idea for a fix, but didnt work
# Custom Pool class using the NoDaemonProcess
class NoDaemonPool(multiprocess.pool.Pool):
    def __init__(self, *args, **kwargs):
        kwargs['context'] = multiprocess.pool.get_context()
        super(NoDaemonPool, self).__init__(*args, **kwargs)
        self.Process = NoDaemonProcess  # Set our custom Process class
"""

def sleepawhile(t):
    print("Sleeping %i seconds..." % t)
    time.sleep(t)
    return t

def work(num_procs):
    print("Creating %i (daemon) workers and jobs in child." % num_procs)

    with NoDaemonPool(num_procs) as pool:
        result = pool.map(sleepawhile,
        [randint(1, 5) for _ in range(num_procs)])

    return result

def test():
    print("Creating 5 (non-daemon) workers and jobs in main process.")
    
    with NoDaemonPool(5) as pool:
        result = pool.map(work, [randint(1, 5) for _ in range(5)])

    print(result)

if __name__ == '__main__':
    test()
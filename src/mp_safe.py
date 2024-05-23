import threading
import time
from ipywidgets import IntProgress
from IPython.display import display

class Counter:
    def __init__(self, manager):
        self.val = manager.Value('i', 0)
        self.lock = manager.Lock()

    def increment(self, amount=1):
        with self.lock:
            self.val.value += amount

    @property
    def count(self):
        with self.lock:
            return self.val.value

class SafeInt:
    #a little jank
    def __init__(self,manager):
        self._value = manager.Value('i',0)
        self.lock = manager.Lock()

    def __iadd__(self, other):
        with self.lock:
            print('iadd ', self._value.value, other)
            self._value.value += other
            return self._value.value
    def __isub__(self, other):
        with self.lock:
            self._value.value -= other
            return self._value.value
    def __imul__(self, other):
        with self.lock:
            self._value.value *= other
            return self._value.value
    def __itruediv__(self, other):
        with self.lock:
            self._value.value /= other
            return self._value.value
    def __imod__(self, other):
        with self.lock:
            self._value.value %= other
            return self._value.value
    def increment(self):
        with self.lock:
            self._value.value += 1
    def decrement(self):
        with self.lock:
            self._value.value -= 1
    @property
    def value(self):
        with self.lock:
            return self._value.value
    @value.setter
    def value(self, other):
        with self.lock:
            self._value.value = other

class SafeProgress:
    #multiprocess-safe IntProgress bar. update_freq is in seconds.
    def __init__(self, manager, min_val=0, max_val=1000, update_freq=1):
        self.widget = IntProgress(min=0, max=max_val)
        display(self.widget)
        self.value_handler = SafeInt(manager)
        self.update_freq = update_freq
        self.update_thread = None
        self.running = False
    
    @property
    def value(self):
        return self.value_handler.value
    
    @value.setter
    def value(self,other):
        self.value_handler.value = other
    
    def __enter__(self):
        self.running = True
        self.update_thread = threading.Thread(target=self.update_progress)
        self.update_thread.start()
        return self
    
    def update_progress(self):
        try:
            while self.running:
                self.widget.value = self.value_handler._value.value
                time.sleep(self.update_freq)
        except Exception as e:
            print("Error during progress update:", e)
            raise e

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.running = False
        if self.update_thread:
            self.update_thread.join()

    def stop(self):
        self.__exit__(None, None, None)

#example
if __name__ == "__main__":
    from multiprocessing import Manager
    manager = Manager()

    with SafeProgress(manager, min_val=0, max_val=1000, update_freq=0.5) as progress:
        #simulate work
        for i in range(10):
            progress.value += 100
            time.sleep(0.25)

    print("Progress bar update thread has been cleanly stopped.")

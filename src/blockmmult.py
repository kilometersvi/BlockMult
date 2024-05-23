import numpy as np

from multiprocess import Manager

import warnings
from mp_safe import Counter, SafeProgress
from nodaemonpool import NoDaemonPool


class BlockMMultFactory:
    def __init__(self, scatter_targets, gather_tasks, threshold=1, max_thread_depth=2, count_predictor=None):
        self.scatter_targets = scatter_targets
        self.gather_tasks = gather_tasks
        self.threshold = threshold
        self.max_thread_depth = max_thread_depth
        
        if count_predictor is None:
            self.count_predictor = lambda n, t: 100
        else:
            self.count_predictor = count_predictor
    
    @staticmethod
    def next_power_of_2(x):
        #calculate lowest power of 2 greater than x
        return 1 if x == 0 else 2**(x - 1).bit_length()

    #recursively calculate block matrix mult using desired mult targets & gather tasks
    #could use my library easytools on git for FlexMethod to make this both static and instance in future impl
    def mmult_recursive(self, A, B, threshold=None, max_thread_depth=None, counter=None, progress_value_handler=None):
        # strassen mult
        # threshold = min dim size to use strassen, else revert to np.dot
        # max thread depth = depth to parallelize
        
        if threshold is None: threshold = self.threshold
        if max_thread_depth is None: max_thread_depth = self.max_thread_depth
        
        n = A.shape[0]
        if n <= threshold:
            if counter:
                #warnign prone to race conditions but whatever
                if threshold > 1 and counter.count == 0:
                    warnings.warn("Since threshold > 1, multiplication steps not properly tracked for 2x2 matrices. Multiplication steps only match calculated amount with thresh = 0.")
                counter.increment()
                if progress_value_handler:
                    progress_value_handler.increment()
            return np.dot(A, B)

        #recursive block mult only works with powers of 2, so matrix must be padded for use, if necessary. 
        #(this overhead contributes to strassen being more effective with larger dim matrices)
        #to do this, find nearest correct dim of matrix
        n = self.next_power_of_2(max(A.shape[0], A.shape[1], B.shape[1]))
        A_pad = np.pad(A, [(0, n - A.shape[0]), (0, n - A.shape[1])], mode='constant')
        B_pad = np.pad(B, [(0, n - B.shape[0]), (0, n - B.shape[1])], mode='constant')

        #break into chunks
        mid = n // 2
        A11, A12 = A_pad[:mid, :mid], A_pad[:mid, mid:]
        A21, A22 = A_pad[mid:, :mid], A_pad[mid:, mid:]
        B11, B12 = B_pad[:mid, :mid], B_pad[:mid, mid:]
        B21, B22 = B_pad[mid:, :mid], B_pad[mid:, mid:]

        A_quads = [[A11, A12], [A21, A22]]
        B_quads = [[B11, B12], [B21, B22]]
        
        child_thread_depth = max_thread_depth - 1 if max_thread_depth > 0 else 0
        # kw_args = {'threshold':threshold, 'max_thread_depth':child_thread_depth, 'counter':counter, 'progress_value_handler':progress_value_handler}
        
        additional_args = (threshold, child_thread_depth, counter, progress_value_handler)
        next_mmult_args = [(self, l[0](A_quads, B_quads), l[1](A_quads, B_quads)) + additional_args for l in self.scatter_targets]
        
        #print(next_mmult_args[0])
        
        if max_thread_depth > 0: #parallelize

            def mmult_wrapper(args):
                #Unpack all arguments, including 'self'
                return args[0].mmult_recursive(*args[1:])
            
            with NoDaemonPool(processes=7) as pool:
                results = pool.map(mmult_wrapper, next_mmult_args)

        else: #keep serial
            results = [t[0].mmult_recursive(*t[1:]) for t in next_mmult_args]

        C = np.vstack([np.hstack([self.gather_tasks[0][0](results), self.gather_tasks[0][1](results)]),
                       np.hstack([self.gather_tasks[1][0](results), self.gather_tasks[1][1](results)])])

        return C

    def __call__(self, A, B, threshold=None, max_thread_depth=None, verbose=0, return_count=False):
        
        if threshold is None: threshold = self.threshold
        if max_thread_depth is None: max_thread_depth = self.max_thread_depth
        
        assert threshold > 0
        assert A.shape[0] == A.shape[1]
        assert A.shape == B.shape
        
        manager = Manager()

        counter = Counter(manager)
        
        max_calls = int(self.count_predictor(A.shape[0], threshold))
        #max_calls = int(self.calculate_total_mult_operations(A.shape[0], threshold))
        if verbose==3:
            print("Predicted number of calls to np.dot (multiplying 2x2 matrix):", max_calls)
        
        if verbose>=1:
            with SafeProgress(manager, min_val=0, max_val=max_calls, update_freq=0.01) as progress:
                result = self.mmult_recursive(A, B, threshold, max_thread_depth, counter, progress.value_handler)
        else:
            result = self.mmult_recursive(A, B, threshold, max_thread_depth, counter, None)

        #if padding was needed, get result for non-power of 2 matrix by removing padded rows/cols
        result_unpadded = result[:A.shape[0],:A.shape[1]]

        if verbose>=2: print("Total multiplications:", counter.count)
        
        if return_count:
            return result_unpadded, counter.count
        return result_unpadded
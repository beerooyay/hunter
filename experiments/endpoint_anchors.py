"""Lossless finite-window pruning relative to a frozen record table and PRP oracle."""
import bisect
from fractions import Fraction

def all_pairs(a,isprime,minimum):
    primes=[x for x in a if isprime(x)]
    return [(x,y) for x,y in zip(primes,primes[1:]) if y-x>=minimum]

def anchor_pairs(a,isprime,minimum):
    """Known-prime anchors partition the window; short partitions cannot qualify."""
    if not a:return []
    stack=[(0,len(a)-1,None,None)];found=[];cache={}
    def prime(x):
        if x not in cache:cache[x]=isprime(x)
        return cache[x]
    while stack:
        lo,hi,left,right=stack.pop()
        if lo>hi:
            if left is not None and right is not None and right-left>=minimum:found.append((left,right))
            continue
        lower=left if left is not None else a[lo]
        upper=right if right is not None else a[hi]
        if upper-lower<minimum:continue
        mid=bisect.bisect_left(a,(lower+upper)//2,lo,hi+1)
        mid=min(hi,max(lo,mid));anchor=None
        for delta in range(max(mid-lo,hi-mid)+1):
            indices=(mid,) if delta==0 else (mid-delta,mid+delta)
            for i in indices:
                if lo<=i<=hi and prime(a[i]):anchor=i;break
            if anchor is not None:break
        if anchor is None:
            if left is not None and right is not None and right-left>=minimum:found.append((left,right))
        else:
            stack.append((anchor+1,hi,a[anchor],right));stack.append((lo,anchor-1,left,a[anchor]))
    return sorted(found)

class RecordFrontier:
    def __init__(self,text,max_gap,target=25):
        self.records={int(f[0]):Fraction(f[1]) for line in text.splitlines() if len(f:=line.split())>=2}
        self.max_gap=max_gap;self.target=target;self.cache={}
    def minimum(self,log_floor):
        # log_floor <= log(left endpoint). Exact rational arithmetic avoids pruning
        # a qualifying gap because of floating-point boundary rounding.
        if log_floor not in self.cache:
            threshold=self.target*log_floor
            if threshold%2:threshold+=1
            for gap in range(2,min(self.max_gap,threshold)+1,2):
                merit=self.records.get(gap,Fraction(0))
                if gap*merit.denominator>merit.numerator*log_floor:
                    threshold=min(threshold,gap);break
            self.cache[log_floor]=threshold
        return self.cache[log_floor]

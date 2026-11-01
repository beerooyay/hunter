import itertools,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from bridge_lab import words, offsets, admissible
W=words(2)

def merge(A,B,g):return A+tuple(A[-1]+g+b for b in B)
def greedy(A,B,C,lim=210):
 for g in range(2,lim+1,2):
  AB=merge(A,B,g)
  if not admissible(AB):continue
  for h in range(2,lim+1,2):
   if admissible(merge(AB,C,h)):return g,h
 return None

def optimal(A,B,C,cap):
 # total bridge length increasing; only even values
 for total in range(4,cap,2):
  for g in range(2,total,2):
   h=total-g
   if admissible(merge(merge(A,B,g),C,h)):return g,h
 return None

if __name__=='__main__':
 cases=0
 for i,j,k in itertools.product(range(len(W)),repeat=3):
  A,B,C=(offsets(W[t]) for t in (i,j,k))
  grd=greedy(A,B,C)
  if grd is None:continue
  opt=optimal(A,B,C,sum(grd))
  cases+=1
  if opt:
   print('counterexample',W[i],W[j],W[k],'greedy',grd,'opt',opt,'saving',sum(grd)-sum(opt),'cases',cases,flush=True)
   break
 else:print('none',cases)
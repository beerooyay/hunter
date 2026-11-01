"""Independent bridge survey: local allowed residue sets, not prime-set merging.
This is logically and algorithmically distinct from frontier.min_bridge.
"""
from collections import Counter
from frontier import admissible_words, word_offsets


def via_allowed_residues(A,B,limit=160):
    primes=(2,3,5,7)
    allowed=[]
    for p in primes:
        ra={a%p for a in A};rb={b%p for b in B}
        good=set()
        for g in range(p):
            shifted={(A[-1]+g+b)%p for b in rb}
            if len(ra|shifted)<p:good.add(g)
        allowed.append((p,good))
    for g in range(2,limit+1,2):
        if all(g%p in good for p,good in allowed):return g
    return None


def run():
    ws=admissible_words(4)
    hist=Counter();mx=0;champions=[]
    for w in ws:
        A=word_offsets(w)
        for v in ws:
            g=via_allowed_residues(A,word_offsets(v))
            if g is None:raise AssertionError((w,v))
            hist[g]+=1
            if g>mx:mx=g;champions=[(w,v)]
            elif g==mx:champions.append((w,v))
    return {'pairs':sum(hist.values()),'max_bridge':mx,'max_pairs':[(list(a),list(b)) for a,b in champions],'histogram':dict(hist)}

if __name__=='__main__':
    import json
    print(json.dumps(run(),indent=2))
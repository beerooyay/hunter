"""Reversal involution on admissible gap-word pairs.
A bridge for (A,B) is equivalent under reflection to one for (reverse B,reverse A).
"""
from frontier import admissible_words, word_offsets, min_bridge

def orbit_audit(k=4):
    ws=admissible_words(k)
    words=set(ws)
    reps={}; fixed=0
    for a in ws:
        for b in ws:
            pair=(a,b);rev=(b[::-1],a[::-1])
            if rev[0] not in words or rev[1] not in words:raise AssertionError('admissibility not invariant under reflection')
            if pair==rev:fixed+=1
            key=min(pair,rev)
            reps.setdefault(key,0)
            reps[key]+=1
    if len(reps)!=(len(ws)**2+len(ws))//2:raise AssertionError('bad orbit count')
    if fixed!=len(ws):raise AssertionError('bad fixed count')
    assert set(reps.values())<={1,2}
    first={}
    for (a,b),mult in reps.items():
        g=min_bridge(word_offsets(a),word_offsets(b))
        if g is None:raise AssertionError('no bridge')
        first[g]=first.get(g,0)+mult
    return {'source_words':len(ws),'full_pairs':len(ws)**2,'orbits':len(reps),'fixed_pairs':fixed,'pair_evaluations_saved':len(ws)**2-len(reps),'distribution':dict(sorted(first.items()))}

if __name__=='__main__':
    import json
    x=orbit_audit()
    from frontier import sharp_bridge_survey
    assert x['distribution']==sharp_bridge_survey()['distribution']
    print(json.dumps({k:v for k,v in x.items() if k!='distribution'},indent=2))
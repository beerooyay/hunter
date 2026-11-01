"""Human-readable obstruction paths for bridge-150 extremizers."""
from pathlib import Path
import json
from frontier import word_offsets, primes_upto, admissible, verify_bridge, sharp_bridge_survey


def explain(w,v,upper):
    A=word_offsets(w);B=word_offsets(v)
    witnesses=[]
    for g in range(2,upper+1,2):
        H=A+tuple(A[-1]+g+b for b in B)
        if g==upper:
            assert admissible(H)
            witnesses.append({'bridge':g,'outcome':'admissible','offsets':list(H),'local_residue_sizes':{str(p):len({h%p for h in H}) for p in primes_upto(len(H))}})
        else:
            obstruction=next((p for p in primes_upto(len(H)) if len({h%p for h in H})==p),None)
            assert obstruction is not None
            witnesses.append({'bridge':g,'outcome':'obstructed','prime':obstruction,'residues':sorted({h%obstruction for h in H})})
    assert verify_bridge(A,B,upper)
    return {'left':list(w),'right':list(v),'results':witnesses}

if __name__=='__main__':
    survey=sharp_bridge_survey();m=survey['sharp_maximum_shortest_bridge']
    rows=[explain(e['left'],e['right'],m) for e in survey['extremizers']]
    Path(__file__).with_name('extremal_certificates.json').write_text(json.dumps(rows,indent=2)+'\n')
    print('verified',len(rows),'extremizers with',len(rows[0]['results'])-1,'failed shorter even bridges each')
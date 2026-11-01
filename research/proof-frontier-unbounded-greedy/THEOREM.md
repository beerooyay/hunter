# Unbounded greedy overhead in admissible prime-pattern concatenation

**Status:** a proved general theorem in ordinary mathematical argument, backed by two independent computational checkers. **Not yet Lean-kernel formalized. Historical originality not established.** The claim concerns *prime-tuple admissibility*, not actual simultaneous prime occurrences.

## Definitions

A *motif* is a finite set of nonnegative even integer offsets containing 0. A motif is *admissible* if, for each prime `q`, its offsets omit at least one residue modulo `q`. For motifs `A,B,C` let `a=max A`, `b=max B` and positive even bridge lengths `g,h`. Define

    W(A,B,C;g,h) = A ∪ (a+g+B) ∪ (a+g+b+h+C).

A *sequential greedy constructor* first chooses the smallest positive even `g` making `A∪(a+g+B)` admissible, then the smallest positive even `h` making `W` admissible. The total added bridge cost is `g+h`. A globally optimal constructor jointly minimizes `g+h`. This objective is **added bridge length**, not the total diameter of all motifs.

## Theorem (unbounded greedy bridge overhead)

For every prime `p≥13` with `p≡1 (mod 3)`, there exist three explicit individually admissible motifs `A_p,B_p,C_p` such that:

1. Sequential greedy chooses `(g,h)=(2,2p-2)` and incurs bridge cost `2p`.
2. The global optimum is `(g,h)=(4,2)` and has bridge cost `6`.
3. Consequently, the greedy approximation ratio equals `p/3`, and no finite uniform approximation ratio holds across all admissible motifs.

Infinitely many primes satisfy `p≡1 (mod 3)` (an elementary fact, also following from Dirichlet's theorem), hence ratios are unbounded.

## Construction

Let `N=3p-2` and let `Q` be the product of all primes `q≤N` except `p`. In particular, `Q` is even and coprime to `p`. Write `D=pQ`.

For a residue set `U⊆Z/pZ` containing `0`, define `S(U)` to be the set containing:

* `0` and `D`,
* for each nonzero residue `r∈U`, the unique integer `Q t_r` in `(0,D)` with `t_r∈{1,...,p-1}` and `Q t_r ≡r (mod p)`.

Then `S(U)` has residue set exactly `U` modulo `p`, all its offsets are `0` modulo every other prime `q≤N`, and it contains `0` and has maximum `D`. There are `|U|+1` elements, since residue `0` is represented twice by `0,D`.

Set

    A = S((Z/pZ) \ {1,7})
    B = S((Z/pZ) \ {-1,3})
    C = S((Z/pZ) \ {1}).

The cardinalities are `p-1,p-1,p`, respectively, summing to `N=3p-2`. Individually all three motifs are admissible: they miss at least one residue modulo `p`, all offsets vanish modulo any other prime `q≤N`, and primes `q>N` have more classes than offsets. All offsets are even.

## Proof

Any union of these motifs uses at most `N` positions, so primes `q>N` cannot obstruct. For primes `q≤N` other than `p`, all original motif offsets are `0 (mod q)` and only the translation phases `0,g,g+h` matter. At `q=2`, all three phases are even. At `q=3`, the phases need to omit one of the three residues. For every `q≥5` other than `p`, at most three residues are occupied, so they cannot cover all `q` classes.

At the special modulus `p`, let `M(S)` denote the complement of the occupied residue set. Since each motif's maximum is `D≡0 (mod p)`, bridge translations are simply `g` and `g+h (mod p)`.

* `M(A)={1,7}` and `M(B)={-1,3}`. With first bridge `g=2`, the missing set of the joined pair is `{1,7}∩({-1,3}+2)={1}`. This pair is admissible modulo every prime, and `2` is the smallest positive even bridge. Greedy must therefore choose `g=2`.
* `M(C)={1}`. With `g=2`, preserving the sole missing residue `1` after adding `C` requires `1+(2+h)≡1 (mod p)`, i.e. `h≡−2 (mod p)`. Since `p` is odd, the smallest positive even solution is `h=2p−2`. At `q=3` the phases are `0,2,2p`, and `p≡1 (mod 3)` makes them `0,2,2`, so the resulting union is admissible. Thus the greedy cost is `2p`.
* With first bridge `g=4`, the missing set of the joined pair is `{1,7}∩({-1,3}+4)={7}`. Taking second bridge `h=2`, the missing residue of `C` becomes `1+4+2=7`, so the three-way union is admissible modulo `p`. At `q=3`, the phases are `0,4,6`, giving only residues `0,1`, and all other primes are harmless as above. Hence `(4,2)` is feasible and costs `6`.
* Every pair of positive even bridges has total cost at least `4`. The only pair of cost `4` is `(2,2)`, which is inadmissible already modulo `3` (the phases `0,2,4` cover all three residues), and also modulo `p`. Consequently the optimum is **exactly 6**.

The approximation ratio is therefore `(2p)/6=p/3`. Since the set of primes `p≡1 (mod 3)` is unbounded, there is no uniform approximation factor. **QED.**

### Elementary infinitude of primes p≡1 (mod 3)

Suppose there are only finitely many such primes `p_1,...,p_k`. Put `M=3p_1...p_k` and `V=M²+M+1>1`. No listed prime divides `V`, and `3` does not divide `V`. Choose a prime `r|V`. Then `M³≡1 (mod r)` and `M≠1 (mod r)`: otherwise `V≡3 (mod r)` would imply `r=3`. Hence `M` has multiplicative order exactly `3` modulo `r`, so `3 | r−1` and `r≡1 (mod 3)`. But `r` is not among the listed primes, a contradiction.

## Important limitations

* The theorem is unconditional and **does not prove that any constructed motif ever occurs among actual primes**. Prime k-tuple occurrence is conjectural in general.
* `Q` is a huge primorial-like integer; these are **adversarial mathematical examples**, not practical short-gap hunting inputs.
* The approximation ratio is for **bridge overhead**. The ratio of full diameters need not be large.
* This strengthens the familiar warning that greedy k-tuple extension can be suboptimal, but an existing proof of this exact unbounded-overhead result has **not** been conclusively ruled out. Treat originality as a hypothesis for expert review.
* This proof has **not yet been Lean-kernel verified**. The scripts check many instances, not infinitely many parameter values.

## Independent reproducibility

    python3 test_theorem.py
    cc -O2 -std=c11 -Wall -Wextra independent.c -o independent
    ./independent
    python3 construction.py > examples.json

The `construction.py` checker builds literal large-integer offset sets and tests every relevant prime. The `independent.c` checker uses only the residue-complement description (no shared code or large-integer construction), for 79 primes `13≤p≤997`, `p≡1 (mod 3)`.
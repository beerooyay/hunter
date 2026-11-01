# proof-frontier calculus v0.1

**status:** exact Python arithmetic experiments pass locally. **No Lean kernel-check, neural model, historical-newness certificate, or blockchain consensus is claimed.** Research extension of Praetor's `research/verification-frontier-v04` work, isolated from the live miner.

## experimental aim

A typed proof graph that accepts **incomplete or false research claims**, records failures, generates nearby repair candidates with explicit changes of meaning, and distinguishes (a) exact certificates, (b) open modular frontiers, (c) bounded exhaustive facts, and (d) algebraic identities. This is **not** a natural-language-to-Lean engine yet: four structured examples are hand-authored inputs, symbolic checking uses SymPy, and the Lean draft has not been compiled.

Run from the folder:

```bash
python3 -m pip install sympy==1.14.0
sh run_lab.sh
```

The lab writes `repairs.json`, `crt_audit.json`, `bridge_survey.json`, `proof_graph.json`, and `extremal_certificates.json`. `verify_bundle.py` regenerates each frozen result from the Python implementations, rather than trusting JSON hashes. `test_frontier.py` runs two independent implementations of the bridge search and 2,900 tamper cases.

## experiments

1. **Quantifier repair:** Euler's polynomial `n²+n+41` is prime for 0..39, but at n=40 it is `41²`. The repair **explicitly changes the original universal claim to a bounded one**. All 40 instances independently checked using trial division, no infinite extrapolation.
2. **Arithmetic fudge repair:** `sum(first n odd integers) = n² + 1` fails at n=1. The suggested `=n²` is checked with symbolic summation and the algebraic formula `2·n(n+1)/2−n=n²`. This is a classical identity.
3. **Construction repair:** the direct gap-word join `(2,4)+(2,6)` is inadmissible modulo 5. Inserting gap 6 yields an admissible combined pattern. **Admissible != actually occurring as consecutive primes.**
4. **Logical consequence extraction:** `H={0,2,6,12,14,20}` forces all 15 unspecified interior offsets to be composite **if** designated positions are prime and larger than the witness primes. Witness receipts select a minimal `p−1` subset of the source positions at each constraining modulus.

## result a: exact modular-frontier dichotomy (classical CRT)

Let `P` be a finite set of distinct primes; `H` is a finite offset set missing at least one residue mod every `p∈P`; let `b` be an additional offset.

**Either:** for some `p∈P`, `H∪{b}` covers every residue class modulo `p`. Then whenever every `n+h` for `h∈H` is prime and greater than `p`, `n+b` is a multiple of `p`; if `n+b>p`, it is composite.

**Or:** for each `p∈P`, `H∪{b}` leaves at least one residue class uncovered. Choose a permissible `n mod p` independently for each `p`; by CRT they combine into one `n mod Q` (`Q=∏P`) for which every `n+h` and `n+b` is coprime to `Q`.

These alternatives are mutually exclusive and exhaustive. **The second case proves only absence of an obstruction from these moduli, NOT primality, actual prime occurrences, or a global proof of incompositeness.**

Implementation: `modular_frontier` produces a fully checkable `forced` certificate or `open_modular` CRT witness. Verified against exhaustive base-residue enumeration in **8,120 cases**: 4,630 forced and 3,490 open. The theorem itself is elementary CRT reasoning, not asserted novel.

## result b: new-to-our-registry finite extremal proposition

Take **every** admissible four-gap word over the alphabet `{2,4,6,8,10}` and then every **ordered pair**. For each, append a positive even gap `g` between the two words. Define the bridge length to be the smallest such `g` that makes the resulting ten-offset tuple admissible.

- 154 admissible source words;
- 23,716 ordered pairs;
- each pair has a bridge no larger than **150**;
- exactly 2 pairs require 150:
  - `(2,4,6,6)` and `(2,10,6,6)`;
  - `(6,6,10,2)` and `(6,6,4,2)`.

The two extremizers are reversals of each other, so there is one case up to reversal. The trace explicitly certifies that each smaller positive even bridge 2..148 is inadmissible, and bridge 150 is admissible. Two independent algorithms (full offset-set merging and local allowed-residue-set comparison) agreed on **every one of the 23,716 minimum bridges and their frequency distribution**. This is an **exhaustively verified finite result for a specified alphabet**, not a proof that the bound holds for arbitrary gap lengths, and not confirmed historical novelty.

For the corresponding lower levels the same implementation recovers `(k=2 -> 18)` and `(k=3 -> 48)`, matching the preceding research.

Why the finite check is complete: the merged tuples contain exactly 10 positions; for every prime `p>10`, at most 10 residue classes can be occupied, so it suffices to check `p∈{2,3,5,7}`. See an established Lean formalization of this reduction: [Axiom Math: admissibility is a finite check](https://primegaps.axiommath.ai/paper/).

## integrity versus mathematical validity

`proof_graph.json` has 28 content-addressed nodes, 22 edges, and a canonical state root. Its `verify_graph` checks document structure, hashes, witness receipts, and graph connections. **Arbitrary narrative repair nodes are not thereby proven mathematically valid.** The `verify_bundle` audit regenerates the four frozen test cases and sharp finite enumeration to check the content. A general trusted rule checker plus Lean integration are future work.

## trust ledger

| claim | status |
|---|---|
| modular CRT dichotomy | pencil-and-paper proof + exhaustive finite tests |
| sharp 150 finite proposition | two independent exact exhaustive Python algorithms, not Lean |
| 2,900 corruptions | rejected by local verification tests |
| structural graph and reproducible state | passes local tests |
| generic prime-gap Lean theorem file | draft only, no compiler/kernel run |
| semantic alignment between natural words and formal claims | human review outstanding |
| globally new theorem in number theory | not established |
| decentralized blockchain or secure finality | not implemented |
| genuine ML model or automatic open-ended theorem invention | not implemented |
| live Praetor language/compiler integration | not implemented |

## next research gates

1. Pin Lean/Mathlib, compile the draft, and formalize the CRT dichotomy as a generic theorem.
2. Export the 23,716 finite cases and witnesses in a format a Lean verifier can recheck without trusting Python or a native oracle.
3. Add a typed DSL with proof-generating constructors rather than storing unverified narrative graph edges.
4. Trial with mathematicians: compare semantic fidelity and human review time against raw AI prose or standalone Lean proofs.
5. Only after that, evaluate whether the immutable evidence graph requires external time-stamping or consensus at all.
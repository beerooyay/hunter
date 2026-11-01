# human review packet: proof frontier calculus v0.1

**IMPORTANT:** an output from the Python test harness is not a Lean-kernel check or a priority claim about mathematics.

## proposition 1: local modular-frontier completeness

Given a finite prime basis P and an offset set H that misses one or more residues modulo every p∈P, an added offset b is forced composite by this finite modular basis precisely when H∪{b} covers every residue modulo at least one p∈P, assuming the H positions are primes >p and n+b>p. If no such p exists, CRT constructs a congruence class modulo Q=∏P in which all the H positions and b avoid every p∈P. This says nothing about divisibility by other primes.

**proof:** for each prime modulus, avoiding all selected offsets requires choosing n outside finitely many forbidden residues. The extra b removes the last permissible residue at some modulus exactly in the forced case. If no modulus has exhausted its choices, independently choose an allowed residue for each prime and invoke the Chinese remainder theorem.

**experiment:** `crt_audit.json` records 8120 tests; 4630 forced and 3490 CRT-open. Tests compare against brute-force enumeration of all residues modulo Q, not merely the generating formula.

## proposition 2: sharp bridge threshold 150

For each pair of admissible 4-gap words in `{2,4,6,8,10}⁴`, joining by a positive even bridge up to 150 always yields an admissible 10-position tuple. Exactly two ordered pairs require 150:

* `(2,4,6,6)` / `(2,10,6,6)`
* `(6,6,10,2)` / `(6,6,4,2)`

They are mirror images. The complete histogram lives in `bridge_survey.json`; per-bridge obstructions for both extremizers live in `extremal_certificates.json`. `independent.py` separately computes admissibility by allowed shift residues, and its histogram agrees exactly with `frontier.py`.

**what to review:** is the restricted source alphabet of mathematical interest? Are there published finite pattern-splicing bounds that subsume 150? Can the maximal-bridge phenomenon be characterized asymptotically in word length or as a function of alphabet width?

## non-theorems and limits

The Euler polynomial and odd-number sum are known examples intentionally used to exercise repair operators. Selecting the bound `0..39` changes the original theorem; an LLM should never silently call that a proof of the universal claim. `PrimeGap` in the Lean draft is not compiled, and no formal certificates for big Praetor gaps are produced.

The research graph currently distinguishes **mathematical evidence** from **proposed repairs** in its node types, but it does not provide general verified semantics for the latter. A digest is not a proof. Human review of natural-language fidelity, motivation and originality is outstanding.
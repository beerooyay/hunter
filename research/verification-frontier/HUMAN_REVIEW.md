# praetor research receipt v0.4

claim id: `f53bd9065c821c55272c1a8425ad45abdb64a8ced18774413971c38295f9778a`

## exact statement (mathematical implication)

for offsets `H = [0, 2, 6, 12, 14, 20]`, assume that `n+h` is prime and greater than every listed witness modulus for each h in H.
then every interior offset recorded with a witness is composite; remaining offsets are not covered by this theorem.

## independently recheckable modular evidence

| offset | modulus | residue classes of H modulo modulus |
|---:|---:|---|
| 1 | 2 | [0] |
| 3 | 2 | [0] |
| 4 | 3 | [0, 2] |
| 5 | 2 | [0] |
| 7 | 2 | [0] |
| 8 | 5 | [0, 1, 2, 4] |
| 9 | 2 | [0] |
| 10 | 3 | [0, 2] |
| 11 | 2 | [0] |
| 13 | 2 | [0] |
| 15 | 2 | [0] |
| 16 | 3 | [0, 2] |
| 17 | 2 | [0] |
| 18 | 5 | [0, 1, 2, 4] |
| 19 | 2 | [0] |

unresolved interior offsets: `[]`

## proof sketch

for each listed b, H occupies every residue class except one modulo p, and b occupies the missing class. since all n+h are prime larger than p, none can be divisible by p. therefore n+b must be divisible by p and, being larger than p, is composite.

## trust boundaries

- the modular certificates were checked by two arithmetic implementations, not by the Lean kernel.
- the hypothesis that the designated numbers are prime must be independently certified.
- this is a known prime-constellation/admissibility mechanism, not a claimed new theorem.
- independent human verification of the intended statement is still pending.
- a blockchain/consensus validity claim is not implied.

## finite example

base = 17; prescribed primes = [17, 19, 23, 29, 31, 37].
verified using small-integer deterministic primality and modular divisibility.
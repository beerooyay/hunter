import Mathlib

/-!
Proof-frontier CRT realizability: useful components toward the full unbounded
greedy-adversary formalization.

WARNING: this module does not prove the full motif construction or the
unbounded approximation theorem. It deliberately exposes the missing
formalization obligations.
-/
namespace Praetor.CRTRealization

/-- Lift any desired residue modulo p to an integer vanishing modulo
    a coprime Q. The witness is supplied by Mathlib's CRT, not an axiom. -/
theorem lift_single_residue (p Q r : Nat) (hcop : p.Coprime Q) :
    ∃ x : Nat, x % p = r % p ∧ x % Q = 0 := by
  let w := Nat.chineseRemainder hcop r 0
  exact ⟨w.val, w.property.1, by simpa [Nat.ModEq] using w.property.2⟩

/-- Independently lift any finite collection of residues. -/
theorem lift_finite_residues (p Q : Nat) (hcop : p.Coprime Q)
    (residues : Finset Nat) :
    ∃ f : Nat → Nat, ∀ r ∈ residues,
      f r % p = r % p ∧ f r % Q = 0 := by
  classical
  choose f hf using (fun r => lift_single_residue p Q r hcop)
  exact ⟨f, fun r _ => hf r⟩

theorem even_of_zero_mod (Q x : Nat) (h2 : 2 ∣ Q) (hx : x % Q = 0) :
    x % 2 = 0 := by
  have hQ : Q ∣ x := Nat.dvd_of_mod_eq_zero hx
  exact Nat.mod_eq_zero_of_dvd (dvd_trans h2 hQ)

/-- If small primes are checked and the set has at most N members,
    no prime larger than N can possibly cover its residue classes. -/
theorem all_primes_of_small_prime_checks
    (s : Finset Nat) (N : Nat) (hcard : s.card ≤ N)
    (hsmall : ∀ q : Nat, Nat.Prime q → q ≤ N →
      (s.image (fun x => x % q)).card < q) :
    ∀ q : Nat, Nat.Prime q →
      (s.image (fun x => x % q)).card < q := by
  intro q hq
  by_cases hle : q ≤ N
  · exact hsmall q hq hle
  · have himage : (s.image (fun x => x % q)).card ≤ s.card :=
      Finset.card_image_le
    omega

end Praetor.CRTRealization

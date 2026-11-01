import Mathlib

/-! Infinitely many admissible prime parameters for the CRT adversary.
This invokes Mathlib's existing formalized arithmetic progression theorem;
it does not prove the existence of the explicit three motif sets. -/
namespace Praetor.GreedyPrimeParameters

theorem arbitrarily_large_prime_one_mod_three (K : Nat) :
    ∃ p : Nat, Nat.Prime p ∧ p % 3 = 1 ∧ K < p := by
  have hunit : IsUnit (1 : ZMod 3) := isUnit_one
  have hinf : Set.Infinite
      {p : Nat | Nat.Prime p ∧ (p : ZMod 3) = 1} :=
    Nat.infinite_setOfPred_prime_and_eq_mod hunit
  obtain ⟨p, hp, hgt⟩ := hinf.exists_gt K
  refine ⟨p, hp.1, ?_, hgt⟩
  have hmod : p % 3 = 1 % 3 :=
    (ZMod.natCast_eq_natCast_iff' p 1 3).mp hp.2
  simpa using hmod

theorem arbitrarily_large_prime_ratio_parameter (K : Nat) :
    ∃ p : Nat, Nat.Prime p ∧ 13 ≤ p ∧ p % 3 = 1 ∧
      6 * K < 2 * p := by
  obtain ⟨p, hp, hmod, hgt⟩ :=
    arbitrarily_large_prime_one_mod_three (3 * K + 13)
  exact ⟨p, hp, by omega, hmod, by omega⟩

end Praetor.GreedyPrimeParameters

import Mathlib

/-!
# Parametric greedy bridge arithmetic, checked independently of search

This module proves a genuinely universal arithmetic component of the
unbounded-greedy theorem. It does NOT claim CRT realization of motifs,
or full Lean formalization of admissibility. That remains open work.
-/
namespace Praetor.GreedyParam

/-- If p is odd and an even bridge h satisfies h+2 ≡ 0 mod p,
    it cannot reach the required residue before 2p-2. -/
theorem even_bridge_residue_lower_bound
    (p h : Nat) (hp : 13 ≤ p) (hpodd : p % 2 = 1)
    (hpositive : 0 < h) (heven : h % 2 = 0)
    (hresidue : (h + 2) % p = 0) :
    2 * p - 2 ≤ h := by
  have hdvd : p ∣ h + 2 := Nat.dvd_of_mod_eq_zero hresidue
  obtain ⟨k, hk⟩ := hdvd
  have kpos : 0 < k := by
    by_contra hn
    have : k = 0 := by omega
    subst k
    simp at hk
    omega
  have knone : k ≠ 1 := by
    intro heq
    subst k
    simp at hk
    omega
  have kge : 2 ≤ k := by omega
  have hbound : 2 * p ≤ h + 2 := by
    calc
      2 * p = p * 2 := by omega
      _ ≤ p * k := Nat.mul_le_mul_left p kge
      _ = h + 2 := hk.symm
  omega

theorem proposed_greedy_bridge_valid
    (p : Nat) (hp : 13 ≤ p) :
    ((2 * p - 2) + 2) % p = 0 := by
  have e : (2 * p - 2) + 2 = 2 * p := by omega
  rw [e]
  simp

/-- The only cheaper positive-even two-bridge plan than cost 6 is (2,2). -/
theorem only_cheaper_path (g h : Nat)
    (hg : 0 < g) (hh : 0 < h)
    (ge : g % 2 = 0) (he : h % 2 = 0)
    (hlt : g + h < 6) : g = 2 ∧ h = 2 := by
  omega

/-- At modulus 3, the greedy first bridge (2,2) covers all three phases. -/
theorem greedy_two_two_covers_mod_three :
    ({0, 2 % 3, (2 + 2) % 3} : Finset Nat) = {0, 1, 2} := by
  decide

theorem global_four_two_omits_mod_three :
    ({0, 4 % 3, (4 + 2) % 3} : Finset Nat) ≠ {0, 1, 2} := by
  decide

/-- Conditional unbounded overhead: the purely arithmetic passage from
    the exact local cost certificates to an unbounded approximation ratio. -/
theorem arithmetic_ratio_unbounded (K : Nat) :
    ∃ p : Nat, 13 ≤ p ∧ p % 2 = 1 ∧ p % 3 = 1 ∧
      6 * K < 2 * p := by
  refine ⟨6 * K + 13, ?_, ?_, ?_, ?_⟩ <;> omega

end Praetor.GreedyParam

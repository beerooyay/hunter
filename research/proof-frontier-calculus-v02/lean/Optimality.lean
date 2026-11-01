import Mathlib

/-!
# Proof-frontier calculus: soundness of a minimal-repair certificate

This proves an abstract certificate theorem for any feasibility relation, and
a concrete minimum-cost modular condition for the p=13 greedy adversary.
It does NOT formalize the infinite unbounded-greedy family or the construction
of its huge prime-offset sets.
-/
namespace Praetor.Certificates

theorem optimal_of_complete_lower_bound
    (feasible : Nat → Nat → Prop) (g h : Nat)
    (hg : 0 < g) (hh : 0 < h)
    (hge : g % 2 = 0) (hhe : h % 2 = 0)
    (hy : feasible g h)
    (no_cheaper : ∀ x y : Nat,
       0 < x → 0 < y → x % 2 = 0 → y % 2 = 0 →
       x + y < g + h → ¬ feasible x y) :
    ∀ x y : Nat, 0 < x → 0 < y → x % 2 = 0 → y % 2 = 0 →
      feasible x y → g + h ≤ x + y := by
  intro x y hx hy' hxe hye hf
  by_contra hc
  have hlt : x + y < g + h := by omega
  exact (no_cheaper x y hx hy' hxe hye hlt) hf

def missing13 (g h : Nat) : Prop :=
  ∃ r : Fin 13, (r.val = 1 ∨ r.val = 7) ∧
    ((r.val + 13 - g % 13) % 13 = 12 ∨
     (r.val + 13 - g % 13) % 13 = 3) ∧
    (r.val + 13 - (g + h) % 13) % 13 = 1

def missing3 (g h : Nat) : Prop :=
  ∃ r : Fin 3, r.val ≠ 0 ∧ r.val ≠ g % 3 ∧ r.val ≠ (g + h) % 3

def feasible13 (g h : Nat) : Prop := missing13 g h ∧ missing3 g h

theorem candidate_4_2 : feasible13 4 2 := by
  constructor
  · refine ⟨⟨7, by omega⟩, ?_, ?_, ?_⟩ <;> norm_num
  · refine ⟨⟨2, by omega⟩, ?_, ?_, ?_⟩ <;> norm_num

theorem cheaper_is_impossible (x y : Nat)
    (hx : 0 < x) (hy : 0 < y) (hxe : x % 2 = 0) (hye : y % 2 = 0)
    (hsmall : x + y < 6) : ¬ feasible13 x y := by
  have hs : x = 2 ∧ y = 2 := by omega
  rcases hs with ⟨rfl, rfl⟩
  intro h
  rcases h.2 with ⟨r, hr0, hr2, hr4⟩
  have rbound : r.val < 3 := r.isLt
  omega

theorem global_optimum_is_6 (x y : Nat)
    (hx : 0 < x) (hy : 0 < y) (hxe : x % 2 = 0) (hye : y % 2 = 0)
    (hgood : feasible13 x y) : 6 ≤ x + y := by
  have h := optimal_of_complete_lower_bound feasible13 4 2
    (by omega) (by omega) (by omega) (by omega)
    candidate_4_2 (by
      intro a b ha hb hae hbe hs
      exact cheaper_is_impossible a b ha hb hae hbe (by omega))
  exact h x y hx hy hxe hye hgood

end Praetor.Certificates

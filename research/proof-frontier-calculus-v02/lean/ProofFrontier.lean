import Mathlib

/-!
A small general-purpose core lemma for Praetor's exact modular bridge receipts.
This statement is independent of primality and works in any additive commutative group.
The CRT/multi-bridge construction and finite sharp bounds are NOT formalized here.
-/
namespace Praetor

theorem bridge_iff_missing_difference
    {α : Type*} [AddCommGroup α] (A B : Set α) (t : α) :
    (∃ x, x ∉ A ∧ x - t ∉ B) ↔
      (∃ x y, x ∉ A ∧ y ∉ B ∧ t = x - y) := by
  constructor
  · rintro ⟨x, hx, hy⟩
    refine ⟨x, x - t, hx, hy, ?_⟩
    abel
  · rintro ⟨x, y, hx, hy, rfl⟩
    refine ⟨x, hx, ?_⟩
    have hxy : x - (x - y) = y := by abel
    rw [hxy]
    exact hy

end Praetor
import Mathlib

/-!
# Proof-frontier calculus: open problems, exact restricted certificates

The conjectures below are *definitions of open obligations*. The theorems
prove ONLY explicitly restricted subgoals. Neither global conjecture is claimed.
No sorry, axiom, or native_decide is used.
-/
namespace Praetor.OpenProblems

def collatzStep (n : Nat) : Nat :=
  if n % 2 = 0 then n / 2 else 3 * n + 1

/-- Global conjecture: intentionally left open. -/
def CollatzConjecture : Prop :=
  ∀ n : Nat, 0 < n → ∃ k : Nat, (collatzStep^[k]) n = 1

/-- For k>0, the class n=4k+1 descends within three Collatz steps. -/
theorem collatz_four_k_one_descends (k : Nat) (hk : 0 < k) :
    collatzStep (collatzStep (collatzStep (4 * k + 1))) = 3 * k + 1 ∧
      3 * k + 1 < 4 * k + 1 := by
  have hodd : (4 * k + 1) % 2 ≠ 0 := by omega
  have heven1 : (3 * (4 * k + 1) + 1) % 2 = 0 := by omega
  have heven2 : ((3 * (4 * k + 1) + 1) / 2) % 2 = 0 := by omega
  have e1 : collatzStep (4 * k + 1) = 3 * (4 * k + 1) + 1 := by
    simp [collatzStep, hodd]
  have e2 : collatzStep (3 * (4 * k + 1) + 1) = (3 * (4 * k + 1) + 1) / 2 := by
    simp [collatzStep, heven1]
  have e3 : collatzStep ((3 * (4 * k + 1) + 1) / 2) = ((3 * (4 * k + 1) + 1) / 2) / 2 := by
    simp [collatzStep, heven2]
  constructor
  · rw [e1, e2, e3]
    omega
  · omega

/-- The complementary odd residue class *ascends* after three steps.
    This is an obstruction to a naive universal three-step descent proof. -/
theorem collatz_four_k_three_ascends (k : Nat) :
    collatzStep (collatzStep (collatzStep (4 * k + 3))) = 18 * k + 16 ∧
      4 * k + 3 < 18 * k + 16 := by
  have hodd : (4 * k + 3) % 2 ≠ 0 := by omega
  have heven1 : (3 * (4 * k + 3) + 1) % 2 = 0 := by omega
  have hodd2 : ((3 * (4 * k + 3) + 1) / 2) % 2 ≠ 0 := by omega
  have e1 : collatzStep (4 * k + 3) = 3 * (4 * k + 3) + 1 := by
    simp [collatzStep, hodd]
  have e2 : collatzStep (3 * (4 * k + 3) + 1) = (3 * (4 * k + 3) + 1) / 2 := by
    simp [collatzStep, heven1]
  have e3 : collatzStep ((3 * (4 * k + 3) + 1) / 2) =
      3 * ((3 * (4 * k + 3) + 1) / 2) + 1 := by
    simp [collatzStep, hodd2]
  constructor
  · rw [e1, e2, e3]
    omega
  · omega

/-- Global strong Goldbach conjecture: intentionally left open. -/
def GoldbachConjecture : Prop :=
  ∀ n : Nat, 4 ≤ n → n % 2 = 0 →
    ∃ p q : Nat, Nat.Prime p ∧ Nat.Prime q ∧ p + q = n

/-- Exact finite problem, with bounded finite witness search. -/
def GoldbachUpTo (bound : Nat) : Prop :=
  ∀ n ∈ Finset.Icc 4 bound, n % 2 = 0 →
    ∃ p ∈ Finset.range (bound + 1),
      ∃ q ∈ Finset.range (bound + 1),
        Nat.Prime p ∧ Nat.Prime q ∧ p + q = n

theorem goldbach_up_to_30 : GoldbachUpTo 30 := by
  decide

theorem goldbach_at_100 :
    ∃ p q : Nat, Nat.Prime p ∧ Nat.Prime q ∧ p + q = 100 := by
  refine ⟨3, 97, ?_, ?_, ?_⟩ <;> norm_num

/-- A refutation, rather than an illegal repair of the original quantifier. -/
theorem euler_polynomial_counterexample :
    ¬ Nat.Prime (40^2 + 40 + 41) := by
  norm_num

end Praetor.OpenProblems

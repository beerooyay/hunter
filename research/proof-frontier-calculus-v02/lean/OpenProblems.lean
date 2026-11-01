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
  ∀ n : Nat, 4 ≤ n → n ≤ bound → n % 2 = 0 →
    ∃ p q : Nat, Nat.Prime p ∧ Nat.Prime q ∧ p + q = n

/-- Every even 4 ≤ n ≤ 30 has explicit prime witnesses; NOT global Goldbach. -/
theorem goldbach_up_to_30 : GoldbachUpTo 30 := by
  intro n hlo hhi heven
  have hcases : n = 4 ∨ n = 6 ∨ n = 8 ∨ n = 10 ∨ n = 12 ∨ n = 14 ∨ n = 16 ∨ n = 18 ∨ n = 20 ∨ n = 22 ∨ n = 24 ∨ n = 26 ∨ n = 28 ∨ n = 30 := by omega
  rcases hcases with h | h | h | h | h | h | h | h | h | h | h | h | h | h
  all_goals subst n
  all_goals first
    | exact ⟨2, 2, by norm_num, by norm_num, by norm_num⟩
    | exact ⟨3, 3, by norm_num, by norm_num, by norm_num⟩
    | exact ⟨3, 5, by norm_num, by norm_num, by norm_num⟩
    | exact ⟨3, 7, by norm_num, by norm_num, by norm_num⟩
    | exact ⟨5, 7, by norm_num, by norm_num, by norm_num⟩
    | exact ⟨3, 11, by norm_num, by norm_num, by norm_num⟩
    | exact ⟨3, 13, by norm_num, by norm_num, by norm_num⟩
    | exact ⟨5, 13, by norm_num, by norm_num, by norm_num⟩
    | exact ⟨3, 17, by norm_num, by norm_num, by norm_num⟩
    | exact ⟨3, 19, by norm_num, by norm_num, by norm_num⟩
    | exact ⟨5, 19, by norm_num, by norm_num, by norm_num⟩
    | exact ⟨3, 23, by norm_num, by norm_num, by norm_num⟩
    | exact ⟨5, 23, by norm_num, by norm_num, by norm_num⟩
    | exact ⟨7, 23, by norm_num, by norm_num, by norm_num⟩

theorem goldbach_at_100 :
    ∃ p q : Nat, Nat.Prime p ∧ Nat.Prime q ∧ p + q = 100 := by
  refine ⟨3, 97, ?_, ?_, ?_⟩ <;> norm_num

/-- A refutation, rather than an illegal repair of the original quantifier. -/
theorem euler_polynomial_counterexample :
    ¬ Nat.Prime (40^2 + 40 + 41) := by
  norm_num

end Praetor.OpenProblems

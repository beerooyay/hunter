import Mathlib

/-!
# The exact outstanding conjecture to formalize

This file TYPECHECKS THE STATEMENT of the complete unbounded-greedy theorem.
It does NOT contain its proof. No constant, axiom, sorry, or Lean theorem
of the desired global statement is introduced.
-/
namespace Praetor.FullGreedyGoal

def admissible (s : Finset Nat) : Prop :=
  ∀ q : Nat, Nat.Prime q → (s.image (fun x => x % q)).card < q

def evenMotif (s : Finset Nat) : Prop :=
  0 ∈ s ∧ ∀ x ∈ s, x % 2 = 0

def positiveEven (g : Nat) : Prop := 0 < g ∧ g % 2 = 0

def span (s : Finset Nat) : Nat := s.sup id

def joinTwo (A B : Finset Nat) (g : Nat) : Finset Nat :=
  A ∪ B.image (fun b => span A + g + b)

def joinThree (A B C : Finset Nat) (g h : Nat) : Finset Nat :=
  joinTwo A B g ∪ C.image (fun c => span A + g + span B + h + c)

def greedyIsTwo (A B C : Finset Nat) (p : Nat) : Prop :=
  positiveEven 2 ∧
  admissible (joinTwo A B 2) ∧
  (∀ g, positiveEven g → admissible (joinTwo A B g) → 2 ≤ g) ∧
  positiveEven (2 * p - 2) ∧
  admissible (joinThree A B C 2 (2 * p - 2)) ∧
  (∀ h, positiveEven h →
    admissible (joinThree A B C 2 h) → 2 * p - 2 ≤ h)

def globallyOptimalSix (A B C : Finset Nat) : Prop :=
  positiveEven 4 ∧ positiveEven 2 ∧
  admissible (joinThree A B C 4 2) ∧
  (∀ g h, positiveEven g → positiveEven h →
    admissible (joinThree A B C g h) → 6 ≤ g + h)

/-- THIS is the unresolved complete formal target.
    It requires real finite sets and the actual ALL-PRIME admissibility
    predicate, rather than stipulating their modular signature. -/
def FullUnboundedGreedy : Prop :=
  ∀ K : Nat, ∃ (p : Nat) (A B C : Finset Nat),
    Nat.Prime p ∧ 13 ≤ p ∧ p % 3 = 1 ∧
    evenMotif A ∧ evenMotif B ∧ evenMotif C ∧
    admissible A ∧ admissible B ∧ admissible C ∧
    A.card = p - 1 ∧ B.card = p - 1 ∧ C.card = p ∧
    greedyIsTwo A B C p ∧ globallyOptimalSix A B C ∧
    6 * K < 2 * p

end Praetor.FullGreedyGoal

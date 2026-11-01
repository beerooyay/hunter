import Mathlib
import CRTRealization

/-!
Concrete finite-set CRT realization with exact image of residues. This is an
additional verified construction lemma, not the full greedy theorem.
-/
namespace Praetor.CRTRealization

/-- Realize a finite target residue set exactly modulo p, with every point
    divisible by Q. This is the key (still partial) CRT motif-construction step. -/
theorem lift_exact_residue_set
    (p Q : Nat) (hcop : p.Coprime Q)
    (R : Finset Nat) (hbounded : ∀ r ∈ R, r < p) :
    ∃ S : Finset Nat,
      S.image (fun x => x % p) = R ∧
      (∀ x ∈ S, x % Q = 0) ∧ S.card ≤ R.card := by
  classical
  obtain ⟨f, hf⟩ := lift_finite_residues p Q hcop R
  refine ⟨R.image f, ?_, ?_, ?_⟩
  · calc
      (R.image f).image (fun x => x % p)
          = R.image (fun r => f r % p) := by
              rw [Finset.image_image]
              rfl
      _ = R.image (fun r => r) := by
          apply Finset.image_congr
          intro r hr
          exact ((hf r hr).1).trans (Nat.mod_eq_of_lt (hbounded r hr))
      _ = R := by simp
  · intro x hx
    obtain ⟨r, hr, rfl⟩ := Finset.mem_image.mp hx
    exact (hf r hr).2
  · exact Finset.card_image_le

/-- Divisibility by the common modulus Q forces all residues modulo q|Q
    to be zero. -/
theorem small_prime_zero_residues
    (S : Finset Nat) (Q q : Nat)
    (hall : ∀ x ∈ S, x % Q = 0) (hq : q ∣ Q) :
    ∀ x ∈ S, x % q = 0 := by
  intro x hx
  have hxQ : Q ∣ x := Nat.dvd_of_mod_eq_zero (hall x hx)
  exact Nat.mod_eq_zero_of_dvd (dvd_trans hq hxQ)

end Praetor.CRTRealization

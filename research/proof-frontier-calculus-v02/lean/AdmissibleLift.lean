import Mathlib
import CRTSet

/-!
A mathematically substantive CRT admission theorem:
given finite target residue classes R modulo p and common modulus Q,
produce a concrete integer motif that is admissible at *every prime*,
assuming Q absorbs all other primes up to the cardinality bound.

This still does NOT formally build the paper's 0,D-anchored motifs or
prove the unbounded greedy concatenation theorem.
-/
namespace Praetor.CRTRealization

theorem exact_residue_motif_admissible
    (p Q N : Nat) (hcop : p.Coprime Q)
    (R : Finset Nat) (hbounded : ∀ r ∈ R, r < p)
    (hmiss : R.card < p) (hsize : R.card ≤ N)
    (hQ : ∀ q : Nat, Nat.Prime q → q ≤ N → q ≠ p → q ∣ Q) :
    ∃ S : Finset Nat,
      S.image (fun x => x % p) = R ∧
      S.card ≤ N ∧
      (∀ x ∈ S, x % Q = 0) ∧
      (∀ q : Nat, Nat.Prime q →
        (S.image (fun x => x % q)).card < q) := by
  classical
  obtain ⟨S, hpimage, hzero, hcardR⟩ :=
    lift_exact_residue_set p Q hcop R hbounded
  have hcard : S.card ≤ N := le_trans hcardR hsize
  refine ⟨S, hpimage, hcard, hzero, ?_⟩
  intro q hq
  by_cases hqp : q = p
  · subst q
    simpa only [hpimage] using hmiss
  by_cases hqN : q ≤ N
  · have hqQ : q ∣ Q := hQ q hq hqN hqp
    have hsingle : S.image (fun x => x % q) ⊆ ({0} : Finset Nat) := by
      intro r hr
      obtain ⟨x, hx, rfl⟩ := Finset.mem_image.mp hr
      have hxQ : Q ∣ x := Nat.dvd_of_mod_eq_zero (hzero x hx)
      have hxq : x % q = 0 :=
        Nat.mod_eq_zero_of_dvd (dvd_trans hqQ hxQ)
      simp [hxq]
    have hle : (S.image (fun x => x % q)).card ≤ 1 := by
      calc
        (S.image (fun x => x % q)).card ≤ ({0} : Finset Nat).card :=
          Finset.card_le_card hsingle
        _ = 1 := by simp
    have hq2 : 2 ≤ q := hq.two_le
    omega
  · have hle : (S.image (fun x => x % q)).card ≤ S.card :=
      Finset.card_image_le
    omega

end Praetor.CRTRealization

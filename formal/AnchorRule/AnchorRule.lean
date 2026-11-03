import Std.Tactic

/-!
Finite-window prime-anchor pruning. `P` is an arbitrary primality predicate.
Theorems are conditional on anchors satisfying P and on the supplied gap cutoff
being sound for the record/merit objective. No PRP-oracle correctness, real-log
rounding, or complete Python/Praetor refinement is claimed here.
-/
namespace Hunter.AnchorRule

abbrev Cell := Int × Int

def Consecutive (P : Int → Prop) (a b : Int) : Prop :=
  P a ∧ P b ∧ a < b ∧ ∀ z, a < z → z < b → ¬ P z

def Contains (s : Cell) (a b : Int) : Prop := s.1 ≤ a ∧ b ≤ s.2

def Covered (cells : List Cell) (a b : Int) : Prop :=
  ∃ s ∈ cells, Contains s a b

/-- A short cell cannot contain a pair reaching the cutoff. -/
theorem short_cell_excludes (s : Cell) (a b G : Int)
    (hin : Contains s a b) (hshort : s.2 - s.1 < G) : b - a < G := by
  rcases hin with ⟨ha, hb⟩
  omega

/-- A genuine prime anchor cannot lie strictly inside a consecutive-prime gap. -/
theorem anchor_cannot_cross {P : Int → Prop} {a b c : Int}
    (hgap : Consecutive P a b) (hc : P c) : b ≤ c ∨ c ≤ a := by
  by_cases hbc : b ≤ c
  · exact Or.inl hbc
  · have hcb : c < b := by omega
    by_cases hca : c ≤ a
    · exact Or.inr hca
    · have hac : a < c := by omega
      exact False.elim ((hgap.2.2.2 c hac hcb) hc)

/-- Splitting at a genuine anchor preserves containment of every consecutive pair. -/
theorem split_preserves {P : Int → Prop} {a b c : Int} {s : Cell}
    (hgap : Consecutive P a b) (hc : P c) (hin : Contains s a b) :
    Contains (s.1, c) a b ∨ Contains (c, s.2) a b := by
  rcases hin with ⟨ha, hb⟩
  rcases anchor_cannot_cross hgap hc with h | h
  · exact Or.inl ⟨ha, h⟩
  · exact Or.inr ⟨h, hb⟩

def refine (cells : List Cell) (c : Int) : List Cell :=
  cells.flatMap fun s => if s.1 ≤ c ∧ c ≤ s.2 then [(s.1,c),(c,s.2)] else [s]

theorem refine_preserves {P : Int → Prop} {a b c : Int} {cells : List Cell}
    (hgap : Consecutive P a b) (hc : P c) (hin : Covered cells a b) :
    Covered (refine cells c) a b := by
  rcases hin with ⟨s, hs, hab⟩
  unfold Covered refine
  by_cases hcell : s.1 ≤ c ∧ c ≤ s.2
  · rcases split_preserves hgap hc hab with h | h
    · exact ⟨(s.1,c), List.mem_flatMap.mpr ⟨s,hs,by simp [hcell]⟩, h⟩
    · exact ⟨(c,s.2), List.mem_flatMap.mpr ⟨s,hs,by simp [hcell]⟩, h⟩
  · exact ⟨s, List.mem_flatMap.mpr ⟨s,hs,by simp [hcell]⟩, hab⟩

def partition (cells : List Cell) (anchors : List Int) : List Cell :=
  anchors.foldl refine cells

theorem partition_preserves {P : Int → Prop} {a b : Int}
    (hgap : Consecutive P a b) (anchors : List Int)
    (hanchors : ∀ c ∈ anchors, P c) (cells : List Cell)
    (hin : Covered cells a b) : Covered (partition cells anchors) a b := by
  induction anchors generalizing cells with
  | nil => exact hin
  | cons c cs ih =>
    apply ih (by intro z hz; exact hanchors z (by simp [hz])) (refine cells c)
    exact refine_preserves hgap (hanchors c (by simp)) hin

def prune (G : Int) (cells : List Cell) : List Cell :=
  cells.filter fun s => decide (G ≤ s.2 - s.1)

theorem prune_preserves {a b G : Int} {cells : List Cell}
    (hin : Covered cells a b) (hqual : G ≤ b-a) : Covered (prune G cells) a b := by
  rcases hin with ⟨s,hs,hab⟩
  have hwide : G ≤ s.2-s.1 := by rcases hab with ⟨ha,hb⟩; omega
  exact ⟨s, List.mem_filter.mpr ⟨hs,by simpa using hwide⟩, hab⟩

/-- Every qualifying consecutive pair stays covered after any valid anchor list
and removal of short cells. This is the record-preservation pruning rule. -/
theorem qualifying_gap_survives {P : Int → Prop} {a b lo hi G : Int}
    (hgap : Consecutive P a b) (ha : lo ≤ a) (hb : b ≤ hi)
    (hqual : G ≤ b-a) (anchors : List Int) (hanchors : ∀ c ∈ anchors, P c) :
    Covered (prune G (partition [(lo,hi)] anchors)) a b := by
  apply prune_preserves (hqual := hqual)
  exact partition_preserves hgap anchors hanchors [(lo,hi)] ⟨(lo,hi),by simp,ha,hb⟩

/-- Production center-gap specialization. Two prime witnesses bracketing the
center bound its surrounding consecutive gap, without locating nearest endpoints. -/
theorem center_gap_excluded {P : Int → Prop} {a b c left right G : Int}
    (hgap : Consecutive P a b) (ha : a < c) (hb : c < b)
    (hl : P left) (hr : P right) (hlc : left < c) (hcr : c < right)
    (hwidth : right-left < G) : b-a < G := by
  have hleft := anchor_cannot_cross hgap hl
  have hright := anchor_cannot_cross hgap hr
  have hla : left ≤ a := by omega
  have hbr : b ≤ right := by omega
  exact short_cell_excludes (left,right) a b G ⟨hla,hbr⟩ hwidth

/-- Exact integer record-frontier comparison is monotone in the log lower bound.
The caller must separately justify its bound on the actual logarithm. -/
theorem rational_record_exclusion (gap numerator denominator lower actual : Nat)
    (hlog : lower ≤ actual) (hsmall : gap*denominator ≤ numerator*lower) :
    ¬ numerator*actual < gap*denominator := by
  have h := Nat.mul_le_mul_left numerator hlog
  omega

theorem target_exclusion (gap target lower actual : Nat)
    (hlog : lower ≤ actual) (hsmall : gap < target*lower) :
    gap < target*actual := by
  exact Nat.lt_of_lt_of_le hsmall (Nat.mul_le_mul_left target hlog)

#print axioms center_gap_excluded
#print axioms qualifying_gap_survives
#print axioms rational_record_exclusion
end Hunter.AnchorRule

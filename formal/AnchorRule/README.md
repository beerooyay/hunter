# Lean 4 preservation rule for finite-window anchor pruning

Pinned toolchain: Lean 4.35.0, standard library only. Run `lake build` here.
The checked declarations use no `sorry`, `admit`, or custom axioms. `#print axioms`
reports only Lean's standard `propext` and `Quot.sound` for the main results.

- `short_cell_excludes`: no pair in a cell narrower than G can have gap >=G.
- `anchor_cannot_cross`: a genuine prime anchor cannot be strictly inside a
  consecutive-prime gap.
- `split_preserves`, `refine_preserves`, `partition_preserves`: arbitrary lists
  of valid prime anchors preserve coverage of every consecutive pair.
- `prune_preserves`, `qualifying_gap_survives`: filtering out short cells cannot
  remove coverage of a qualifying pair.
- `center_gap_excluded`: two prime witnesses bracketing the center bound its
  surrounding consecutive gap. This is the production-prefilter specialization.
- `rational_record_exclusion`, `target_exclusion`: exact integer frontier
  comparisons are monotone in a sound lower bound for the logarithm.

## Scope

`P : Int -> Prop` is an arbitrary primality predicate. Concrete application
requires proving each used anchor satisfies P. BPSW checks are not proofs of
that premise; certificates or a stated oracle assumption bridge that boundary.
The cutoff contract must ensure every desired record/target gap is >=G. Real
logarithm rounding and the concrete table parser are not verified by these
standard-library theorems. The end-to-end Python/Praetor implementation is not
formally refined to these definitions. Exhaustive/randomized oracle tests and
native output comparisons provide additional implementation evidence.

The rule is elementary interval reasoning. Formal verification establishes its
stated contract; it is not a novelty claim or a proof of Cramer's/twin-prime
conjectures. Closed cells retain endpoints, and the strict `<G` pruning condition
preserves threshold-equality cases.

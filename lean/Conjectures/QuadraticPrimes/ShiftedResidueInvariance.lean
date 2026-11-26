import Mathlib
import PEqualNP.Outside.L_quadratic_primes_residue_invariance

theorem Conjectures.QuadraticPrimes.ShiftedResidueInvariance :
    ∀ (m a b c : ℕ), a % m = b % m → (a ^ 2 + (1 + c)) % m = (b ^ 2 + (1 + c)) % m := by
  intro m a b c h
  have same : Nat.ModEq m (a ^ 2 + 1) (b ^ 2 + 1) :=
    PEqualNP.Outside.L_quadratic_primes_residue_invariance m a b h
  simpa only [Nat.add_assoc] using same.add_right c

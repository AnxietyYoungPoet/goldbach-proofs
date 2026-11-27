import Mathlib

open scoped BigOperators

theorem Conjectures.Goldbach.DynExceptionEnergy :
    ∀ (E : Finset ℕ) (r b : ℕ → ℝ) (L : ℝ), 0 < L →
      (∀ n ∈ E, L ≤ b n) →
      ((E.filter (fun n => r n = 0)).card : ℝ) * L^2 ≤ ∑ n ∈ E, (r n - b n)^2 := by
  classical
  intro E r b L hL hb
  let misses := E.filter (fun n => r n = 0)
  calc
    (misses.card : ℝ) * L^2 = ∑ _n ∈ misses, L^2 := by simp [nsmul_eq_mul]
    _ ≤ ∑ n ∈ misses, (r n - b n)^2 := by
      apply Finset.sum_le_sum
      intro n hn
      obtain ⟨hnE, hr⟩ := Finset.mem_filter.mp hn
      rw [hr, zero_sub, neg_sq]
      exact pow_le_pow_left₀ hL.le (hb n hnE) 2
    _ ≤ ∑ n ∈ E, (r n - b n)^2 := by
      exact Finset.sum_le_sum_of_subset_of_nonneg (Finset.filter_subset _ _)
        (fun n _ _ => sq_nonneg (r n - b n))

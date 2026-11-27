import Mathlib

theorem Conjectures.Goldbach.DynModularMirage :
    ∀ N : ℕ, Even N → 4 ≤ N → ∃ A : Set ℕ, (∀ a ∈ A, Odd a) ∧
      (∀ m : ℕ, 0 < m → ∃ a ∈ A, ∃ b ∈ A, (a+b)%m=N%m) ∧
      ¬ (∃ a ∈ A, ∃ b ∈ A, a+b=N) := by
  intro N hEven _
  refine ⟨{a | N < a ∧ Odd a}, fun _ ha => ha.2, ?_, ?_⟩
  · intro m hm
    let k := m * (N + 1)
    have hk : N + 1 ≤ k := by
      dsimp [k]
      rw [Nat.mul_comm]
      exact Nat.le_mul_of_pos_right _ hm
    obtain ⟨j, hj⟩ := hEven
    refine ⟨N + 1, ⟨by omega, j, by omega⟩, 2 * (k - 1) + 1,
      ⟨by omega, k - 1, rfl⟩, ?_⟩
    have hsum : N + 1 + (2 * (k - 1) + 1) = N + m * (2 * (N + 1)) := by
      have hmul : m * (2 * (N + 1)) = 2 * k := by dsimp [k]; ring
      omega
    rw [hsum, Nat.add_mul_mod_self_left]
  · rintro ⟨a, ha, b, hb, hsum⟩
    have hlarge : N < a := ha.1
    omega

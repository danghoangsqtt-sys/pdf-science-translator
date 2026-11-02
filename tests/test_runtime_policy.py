from __future__ import annotations

import unittest

from pdf2zh.runtime_policy import EffectivePolicy, GIB, ResourceSnapshot, candidate_policies


class RuntimePolicyTests(unittest.TestCase):
    def test_rtx_3050_four_gib_prefers_conservative_fast_then_cpu(self) -> None:
        snapshot = ResourceSnapshot(24 * GIB, 12 * GIB, 4 * GIB, 3 * GIB, 20)
        policies = candidate_policies("fast", snapshot, "pack-a")
        self.assertEqual([(item.backend, item.context_tokens) for item in policies],
                         [("gpu", 2048), ("cpu", 2048)])
        self.assertEqual(candidate_policies("balanced", snapshot, "pack-a"), ())
        self.assertEqual(candidate_policies("quality", snapshot, "pack-a"), ())

    def test_larger_gpu_offers_four_then_two_k_without_more_than_two_probes(self) -> None:
        snapshot = ResourceSnapshot(32 * GIB, 20 * GIB, 12 * GIB, 10 * GIB, 20)
        policies = candidate_policies("quality", snapshot, "pack-a")
        self.assertEqual([item.context_tokens for item in policies], [4096, 2048])
        self.assertTrue(all(item.backend == "gpu" for item in policies))

    def test_unknown_is_not_zero_or_readiness(self) -> None:
        self.assertEqual(candidate_policies(
            "fast", ResourceSnapshot(None, None, None, None, None), "pack-a"
        ), ())

    def test_stable_key_ignores_raw_free_memory_but_tracks_policy_and_pack(self) -> None:
        first = candidate_policies(
            "fast", ResourceSnapshot(24 * GIB, 12 * GIB, 4 * GIB, 3 * GIB, 20), "pack-a"
        )[0]
        second = candidate_policies(
            "fast", ResourceSnapshot(24 * GIB, 10 * GIB, 4 * GIB, 7 * GIB // 2, 20), "pack-a"
        )[0]
        changed = candidate_policies(
            "fast", ResourceSnapshot(24 * GIB, 10 * GIB, 4 * GIB, 7 * GIB // 2, 20), "pack-b"
        )[0]
        self.assertEqual(first.stable_key(), second.stable_key())
        self.assertNotEqual(first.stable_key(), changed.stable_key())

    def test_invalid_policy_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            EffectivePolicy("fast", "gpu", 8192, 64, 4, 512, "ram24-vram4", "pack")


if __name__ == "__main__":
    unittest.main()

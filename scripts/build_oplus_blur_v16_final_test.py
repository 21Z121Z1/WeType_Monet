#!/usr/bin/env python3
"""Run the existing V16 APK builder with the corrected V16 final audit."""

from __future__ import annotations

import build_oplus_blur_test as runner
from oplus_visual_v16_final import apply_coloros_v2_visual_profile_v16

# build_oplus_blur_test resolves this imported symbol at runtime. Replace only
# the V16 pass entrypoint; APK naming/signing/build behavior stays identical.
runner.apply_coloros_v2_visual_profile_v16 = apply_coloros_v2_visual_profile_v16

if __name__ == "__main__":
    runner.main()

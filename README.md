# Jeandle Perf Observatory

Read-only JavaType cache experiments: https://jeandle.annya.work

The sidebar lists all thirteen tests together, grouped into three datasets: the original six profiling scenarios, the three context-cache reuse scenarios (`final`, `prefix`, `mutation`) and the four cross-pass production scenarios (端到端计时 / 复用机制 / JVM 编译成本 / 不利样本与边界). Each scenario includes its motivation, construction, pseudocode, characteristics and interpretation limits.

- The replay dataset uses exactly three paired rounds (18 timed processes), with separate cache-hit/correctness diagnostics.
- The cross-pass dataset reports a production-pipeline experiment with three cache-lifetime policies (ORIGINAL / PASS-LOCAL / CROSS-PASS), 60 paired timing blocks, in-process counters and JVM compile cost. It has no sampled profiles, so it shows no call stacks, cycles share or Speedscope export.

No JVM speedup is claimed. Percentages from different measurement systems are never added together.

## Source and evidence

- `viewer/`: maintainable Python standard-library backend, static builder, browser UI and tests.
- `api/artifacts/context-cache-reuse-2026-10-23/`: raw timing/diagnostic JSON, test patch, identity, report and validation logs.
- `api/artifacts/2026-10-26-javatype-cross-pass-prod/`: report, paired timing, counters, lifecycle trace, perf stat, CITime and jtreg results of the cross-pass run.
- LLVM tests: https://github.com/Atm2086/jeandle-llvm/commit/ea2953f61a852e322848b03354eb97c98ac87bf5
- `api/experiments/context-cache-reuse-2026-10-23/overview.json`: validated summary and full test descriptions.
- `api/experiments/2026-10-26-javatype-cross-pass-prod/overview.json`: validated summary and full test descriptions of the cross-pass run.

To run locally with the original frozen artifact directories:

```sh
python3 viewer/server.py --port 8766 --data /path/to/java-type-perf-2026-10-23 --data /path/to/context-cache-reuse-2026-10-23
```

To rebuild the static site (output must be a staging directory, never this Git checkout):

```sh
python3 viewer/build_static.py --data /path/to/java-type-perf-2026-10-23 --reuse-data /path/to/context-cache-reuse-2026-10-23 --cross-pass-data /path/to/2026-10-26-javatype-cross-pass-prod --out /tmp/jeandle-perf-site --domain jeandle.annya.work
```

`--data` is optional. Without it the builder keeps the profiling entries already published in the output tree and only refreshes the replay and cross-pass experiments, so a site that already serves the large profiling archives can be updated without the original `run-records.tar.gz` input.

The original large frozen archives are external build inputs. Raw `perf.data` is not published. GitHub Pages serves the generated root files; `viewer/` is the source copy. See `viewer/README.md` and `viewer/VERIFICATION.md` for protocols and verification.

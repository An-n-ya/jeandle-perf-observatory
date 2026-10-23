# Jeandle Perf Observatory

Read-only JavaType cache experiments: https://jeandle.annya.work

The dataset selector provides the original six profiling scenarios and the three context-cache reuse scenarios (`final`, `prefix`, `mutation`). Each scenario includes its motivation, construction, pseudocode, characteristics and interpretation limits. New replay data uses exactly three paired rounds (18 timed processes), with separate cache-hit/correctness diagnostics. No JVM speedup is claimed.

## Source and evidence

- `viewer/`: maintainable Python standard-library backend, static builder, browser UI and tests.
- `api/artifacts/context-cache-reuse-2026-10-23/`: raw timing/diagnostic JSON, test patch, identity, report and validation logs.
- LLVM tests: https://github.com/Atm2086/jeandle-llvm/commit/ea2953f61a852e322848b03354eb97c98ac87bf5
- `api/experiments/context-cache-reuse-2026-10-23/overview.json`: validated summary and full test descriptions.

To run locally with the original frozen artifact directories:

```sh
python3 viewer/server.py --port 8766 --data /path/to/java-type-perf-2026-10-23 --data /path/to/context-cache-reuse-2026-10-23
```

To rebuild the static site (output must be a staging directory, never this Git checkout):

```sh
python3 viewer/build_static.py --data /path/to/java-type-perf-2026-10-23 --reuse-data /path/to/context-cache-reuse-2026-10-23 --out /tmp/jeandle-perf-site --domain jeandle.annya.work
```

The original large frozen archives are external build inputs. Raw `perf.data` is not published. GitHub Pages serves the generated root files; `viewer/` is the source copy. See `viewer/README.md` and `viewer/VERIFICATION.md` for protocols and verification.

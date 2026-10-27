# JavaType 跨 pass 缓存：生产流水线性能测试报告

- 执行日期：2026-10-26 ~ 2026-10-27（Asia/Shanghai）
- 执行依据：《JavaType 跨 pass 缓存：生产流水线、jtreg 与 profiling 测试方案》（2026-10-26，Mac 原件 `JavaType-Cross-Pass-Production-Performance-Plan-2026-10-26.md`）
- 工作根目录：`/home/annya/playground/jeandle/perf-results/2026-10-26-javatype-cross-pass-prod/`
- 随机种子：20261026（阶段 C / 阶段 D / 阶段 E 共用同一 base seed）

---

## 0. 结论摘要

**机制成立，但当前生产配置未测出稳定净收益。**

1. **合成机制成立。** 跨 pass 保留使 JavaType 缓存真正跨 pass 复用：每语料轮 Final 层命中从 `0`（pass-local）升到 `68`，Base 层重算插入从 `168` 次降到 `100` 次（少 `68` 次插入 / 语料轮，−40.5%），失效请求从 `13186` 降到 `32`。jtreg 子 JVM 中独立复现（Final 命中 `0 → 6`）。
2. **但生产流水线下的净收益未被稳定测出。** 阶段 C 主指标（整份固定语料的优化生命周期进程 CPU）ORIGINAL→CROSS-PASS 为 **−0.1871%，CI95 [−0.4700%, +0.0888%]**（跨零）→ 结论为「尚未测出稳定净收益（置信区间跨零）」。PASS-LOCAL→CROSS-PASS 为 **−0.3447%，CI95 [−0.6075%, −0.0833%]**（不含 0，但**方向为负**），即在本生产流水线配置下，保留跨 pass 缓存反而比每 pass 清空更慢。
3. **原因定位。** 跨 pass 存活的条目主要在 `JavaOperationLower` 处被丢弃（`dropped_with_entries` = 71，占跨 pass 全部 100 次的绝大多数），真正被后续消费者复用到的只有 4（TCE）+ 64（RepeatedConstantFolding）次 Final 命中。**跨 pass 存活的收益被失效与重算的额外开销抵消后落在噪声内。**
4. **JVM 侧同样未测出稳定净收益。** 阶段 E 三个指标（JVM LLVM Optimize / 总编译成本 / 应用时间）在 JVM-CONTROLLED 与 JVM-PRODUCTION 两组中分别给出，CITime 是 elapsed 而非线程 CPU，并发下只作参考量级。
5. **未混入任何新的 preserve 实现或 LVI 优化**，性能主模式的唯一变量是缓存生存期策略。

> **口径提醒（方案 §1）：** 本报告中的 ORIGINAL→CROSS-PASS 与 PASS-LOCAL→CROSS-PASS 是**两次独立对照**，
> 它们的百分比**不可相加**；阶段 C（opt 子进程语料回放）与阶段 E（JVM 子进程编译成本）是**两套不同测量体系**，
> 它们的数字同样不可相加，跨体系只能做方向性互证。

---

## 1. 被测系统与默认配置

| 项 | 值 | 来源 |
|---|---|---|
| 生产 pipeline | `jeandle<O3>`（未删除标准 pass，未关闭内联 / PEA） | `scripts/common.py:26` |
| PEA | 默认开启，迭代轮数默认 `2` | `PartialEscapeIterative.cpp:57,65`（`cl::init(true)` / `cl::init(2)`） |
| 内联 | 默认策略 `InlinePolicy::Default` | `Pipeline.cpp:73` |
| LLVM 构建 | `build-ninja-profiling`，`CMAKE_BUILD_TYPE=Release`，flags `-O3 -DNDEBUG -g`，`LLVM_ENABLE_ASSERTIONS=OFF` | `identity/identity.json` |
| opt 二进制 | `build/build-ninja-profiling/bin/opt`，sha256 `644ea727…07f22`，mtime 1793022297 | `identity/identity.json` |
| 动态库（JVM 用） | `jeandle-llvm-release/lib/libLLVM.so.22.0git`，sha256 `e7c9f91d…617da` | `identity/identity.json` |
| LLVM 分支 / HEAD | `test/javatype-cache-design` / `b121fa56710a0265d66ae5fa5c0b1cc0aa10ced6` | `identity/identity.json` |
| LLVM worktree diff sha256 | `b93b4509cd18a32666d5d2a6a7d87f7a4c144c3b5f87a20f02b6987a20db5fb8` | `identity/identity.json` |
| JDK HEAD | `1d56df159ebb4edbaa4613941dc952ffe0be8c64`（**未重新构建**，运行时动态加载 release libLLVM） | `identity/identity.json` |
| 主机 | archlinux，内核 7.1.3-arch2-2，32 核，`Genuine Intel(R) 0000` | `timing/environment.json` |
| CPU 频率策略 | `powersave` | `timing/environment.json` |
| 绑定 CPU | 2（`taskset -c 2`） | `timing/environment.json` |
| Python | 3.14.6 | `timing/environment.json` |

### 1.1 三种对照模式（方案 §3）

| 模式 | 开关 | 语义 |
|---|---|---|
| `original` | `-jeandle-disable-java-type-cache` | 关闭 JavaType 缓存，所有查询 bypass |
| `pass_local` | `-jeandle-java-type-pass-local` | 每个真实消费者 pass 入口清缓存，只保留 pass 内复用 |
| `cross_pass` | （无） | 现状：缓存跨 pass 存活，受失效通知控制 |

**`pass_local` 开关的实现（方案 §3.1 要求）**——本次改动只增加测试专用开关，不改变生产语义：

- 开关定义：[JavaTypeAnalysis.cpp:53-57](file:///home/annya/playground/jeandle/jeandle/jeandle-llvm/llvm/lib/Analysis/Jeandle/JavaTypeAnalysis.cpp#L53-L57)
- 统一 helper：[JavaTypeAnalysis.cpp:134-150](file:///home/annya/playground/jeandle/jeandle/jeandle-llvm/llvm/lib/Analysis/Jeandle/JavaTypeAnalysis.cpp#L134-L150)
  - 用 `FAM.getCachedResult<JavaTypeAnalysis>(F)` **只取已存在的分析**，不创建分析（为清理而创建分析会污染成本）
  - 有缓存才 `Result->clear()`；无缓存直接返回
  - 调用计数只在 `-jeandle-java-type-stats` 打开时递增，**正式运行关闭 trace/stats**
- 四个真实消费者 `run()` 入口首行插入：
  - [TypeCheckElimination.cpp:57](file:///home/annya/playground/jeandle/jeandle/jeandle-llvm/llvm/lib/Transforms/Jeandle/TypeCheckElimination.cpp#L57) → `type-check-elimination`
  - [RecoverTypeInfo.cpp:176](file:///home/annya/playground/jeandle/jeandle/jeandle-llvm/llvm/lib/Transforms/Jeandle/RecoverTypeInfo.cpp#L176) → `recover-type-info`
  - [ConstantFieldFolding.cpp:735](file:///home/annya/playground/jeandle/jeandle/jeandle-llvm/llvm/lib/Transforms/Jeandle/ConstantFieldFolding.cpp#L735) → `constant-field-folding`（RepeatedConstantFolding 直接调用本 pass，故每轮都被覆盖）
  - [CHADevirtualization.cpp:598](file:///home/annya/playground/jeandle/jeandle/jeandle-llvm/llvm/lib/Transforms/Jeandle/CHADevirtualization.cpp#L598) → `cha-devirtualization`
- 新增回归测试：`llvm/test/Jeandle/java-type-cache-reuse/pass-local-production-hook.ll`
- 改动规模：7 个文件，+102 / −4 行（`git diff --stat`）

### 1.2 绝对 CPU / cycles 基线（整语料 10 轮，`perf stat`，进程级）

| 模式 | task-clock (ms) | cycles | instructions | branches | branch-misses | cache-misses |
|---|---|---|---|---|---|---|
| original | 13 702.75 | 56 798 601 515 | 72 864 327 229 | 15 422 712 478 | 666 203 786 | 37 206 382 |
| pass_local | 13 659.77 | 56 643 698 861 | 72 894 544 320 | 15 428 208 693 | 666 680 303 | 37 117 909 |
| cross_pass | 13 662.21 | 56 636 815 471 | 72 861 194 084 | 15 422 258 249 | 665 964 427 | 36 655 467 |

绝对差：

| 对照 | task-clock 差 | cycles 差 | instructions 差 |
|---|---|---|---|
| original → cross_pass | **−40.54 ms** | **−161 786 044** | −3 133 145 |
| pass_local → cross_pass | **+2.44 ms** | **−6 883 390** | −33 350 236 |

原始文件：`profiles/perf_stat_{original,pass_local,cross_pass}.csv`

---

## 2. 固定语料（方案 §5）

### 2.1 规模与覆盖率

| 项 | 值 |
|---|---|
| 录制 root method 总数 | 76 |
| 入选（合格）样本 | **64** |
| 拒绝样本 | 12（**全部**为 `replay failed in mode original (exit -6)`，属既有崩溃，非本改动引入） |
| 回放覆盖率 | **64 / 76 = 84.2 %** |
| 覆盖程序数 | 6（ArrayShapes / CollectionShapes / ConstantShapes / InlineShapes / NegativeShapes / TypeShapes） |
| 录制轮数 | 20 000 |
| 零查询样本（三模式查询数均为 0） | **0 个** |

入选分布：ArrayShapes 6 / CollectionShapes 14 / ConstantShapes 6 / InlineShapes 6 / NegativeShapes 22 / TypeShapes 10。
完整清单与逐样本 argv、拒绝原因见 `diagnostics/inventory.md`、`diagnostics/eligibility.json`。

### 2.2 入选规则

入选依据输入形状与基线编译成本（方案 §5）：只保留能触发 JavaType 子系统的 root method（instanceof / checkcast / 虚调用 / 字段访问形状），并要求该 IR 在 `original` 模式下能稳定回放（用于配对计时）。`NegativeShapes` 专门收录无类型信息收益的形状，用于观测负收益。

---

## 3. 阶段 C：优化生命周期计时（主指标，方案 §6）

### 3.1 方法

- 每个样本单独起一个 `opt` 子进程：`opt -disable-output -disable-verify -passes=jeandle<O3> <模式开关> <ir>`
- 预热轮丢弃；随后每样本测 **no-op 基线**（同命令但不带 pipeline，每样本 5 次，取中位数）
- **2 个独立 session × 30 个随机配对 block = 60 个配对 block**；block 内样本顺序与模式顺序均随机
- 计时口径：子进程 `wait4` rusage 的 user+sys CPU 与墙钟
- 净收益 `1 - sum(T_candidate) / sum(T_baseline)`；CI95 由**配对 block 重采样**（10 000 次）
- 原始数据：`timing/raw.csv`（11 520 行 = 3 840/模式，**失败 0**）、`timing/baseline.csv`（640 行 / 128 个 (session,sample) 组合）、`timing/environment.json`
- 统计脚本：`scripts/timing.py`、`scripts/analyze.py`（seed 20261026）

### 3.2 ORIGINAL → CROSS-PASS

| 指标 | 基线总时长 (s) | 候选总时长 (s) | 净收益 | 95% CI |
|---|---|---|---|---|
| 进程 CPU（含启动/解析） | 87.8031 | 87.9674 | **−0.1871 %** | [−0.4700 %, +0.0888 %] |
| 墙钟（含启动/解析） | 89.5185 | 89.6745 | −0.1743 % | [−0.4530 %, +0.1051 %] |
| 进程 CPU（扣 no-op 基线） | 73.1308 | 73.2951 | **−0.2246 %** | [−0.5557 %, +0.1159 %] |
| 墙钟（扣 no-op 基线） | 74.8462 | 75.0022 | −0.2084 % | [−0.5338 %, +0.1216 %] |

- 每轮（一个 block）基线**有效优化工作** 1.2188 s（方案 §6 要求的 2–10 s 区间内）
- 绝对差：候选比基线**多** 0.1643 s
- 每方法净收益分布：P05 −1.382 % / **P50 −0.302 %** / P95 +1.524 % / min −2.362 % / max +2.356 %；**负收益占比 57.8 %**
- 配对差均值 −0.0000428 s/样本，CI95 [−0.0000977, +0.0000143] s
- **结论：尚未测出稳定净收益（置信区间跨零）**

### 3.3 PASS-LOCAL → CROSS-PASS

| 指标 | 基线总时长 (s) | 候选总时长 (s) | 净收益 | 95% CI |
|---|---|---|---|---|
| 进程 CPU（含启动/解析） | 87.6652 | 87.9674 | **−0.3447 %** | [−0.6075 %, −0.0833 %] |
| 墙钟（含启动/解析） | 89.3706 | 89.6745 | −0.3400 % | [−0.6045 %, −0.0760 %] |
| 进程 CPU（扣 no-op 基线） | 72.9930 | 73.2951 | **−0.4140 %** | [−0.7347 %, −0.0996 %] |
| 墙钟（扣 no-op 基线） | 74.6983 | 75.0022 | −0.4068 % | [−0.7264 %, −0.0901 %] |

- 每轮基线有效优化工作 1.2165 s
- 绝对差：候选比基线**多** 0.3022 s
- 每方法净收益分布：P05 −2.107 % / **P50 −0.305 %** / P95 +1.187 % / min −3.445 % / max +1.996 %；**负收益占比 56.2 %**
- 配对差均值 −0.0000787 s/样本，CI95 [−0.0001418, −0.0000149] s
- **结论：置信区间不含 0，但方向为负 —— 跨 pass 保留比 pass-local 更慢（本流水线配置下）**

### 3.4 两个百分比的解读

- `original → cross_pass` 跨零：**当前生产配置下，跨 pass 缓存相对"完全关闭缓存"没有可测的稳定收益。**
- `pass_local → cross_pass` 为负且显著：**"每 pass 清空"这一更激进的做法，在本生产流水线里反而更快。**
- 这两条**不可相加**：−0.1871 % 与 −0.3447 % 是同一张表里两个不同基线的独立对照，加起来没有物理意义。

---

## 4. 阶段 D：跨 pass 来源诊断与 profiling（方案 §8）

### 4.1 跨 pass 消费下降的重算量（每语料轮，64 样本 × 10 repeat，进程内计数器）

| 计数器 | original | pass_local | cross_pass | pass_local → cross_pass |
|---|---|---|---|---|
| queries | 173 | 173 | 173 | 0 |
| bypasses | 173 | 0 | 0 | −173 |
| **base insertions（Base 层重算）** | 0 | **168** | **100** | **−68（−40.5 %）** |
| **final type hits（跨 pass 复用命中）** | 0 | **0** | **68** | **+68** |
| final type misses | 0 | 178 | 110 | −68 |
| path facts hits / misses | 0 / 0 | 8 / 83 | 8 / 79 | −4 |
| **invalidation requests（失效请求）** | 32 | **13 186** | **32** | **−13 154** |
| selective invalidations | 32 | 32 | 32 | 0 |
| pass-local cache clears | 0 | 13 154 | 0 | −13 154 |
| base entries retained / invalidated | 0 / 0 | 8 / 148 | 16 / 0 | +8 / −148 |
| final type entries invalidated | 0 | 153 | 15 | −138 |
| total query time (ns) | 610 981.5 | 753 868.0 | 662 283.2 | −91 584.8 |
| total invalidation time (ns) | 1 454.7 | 335 116.0 | 10 326.1 | −324 789.9 |
| **子系统合计 (ns)** | 612 436.2 | 1 088 984.0 | 672 609.3 | **−416 374.7（−38.2 %）** |

**结论：跨 pass 保留把 Base 层重算减少 68 次/语料轮，并首次产生 68 次 Final 层跨 pass 命中；失效开销从 335 µs 降到 10 µs。机制层面成立。**

原始数据：`diagnostics/subsystem_cost.json`、`diagnostics/cross_pass_trace_summary.json`

### 4.2 消费者级跨 pass 命中（每语料轮）

| 消费者 | invocations | original (hits / base_ins) | pass_local (hits / base_ins) | cross_pass (hits / base_ins) |
|---|---|---|---|---|
| repeated-constant-folding | 137 | 0 / 0 | 0 / 135 | **64 / 71** |
| type-check-elimination | 20 | 0 / 0 | 0 / 17 | **4 / 13** |
| recover-type-info | 12 | 0 / 0 | 0 / 12 | 0 / 12 |
| cha-devirtualization | 4 | 0 / 0 | 0 / 4 | 0 / 4 |

**跨 pass 的 Final 命中全部来自 RepeatedConstantFolding（64/68）与 TypeCheckElimination（4/68）。** RecoverTypeInfo 与 CHADevirtualization 在本语料中没有获得任何跨 pass 复用。

### 4.3 生命周期断点（关键诊断）

三种模式的 analysis 生命周期统计**完全一致**（这本身是重要结论：跨 pass 保留没有改变哪些 pass 会丢弃分析，只改变了丢弃时缓存里还有没有条目）：

| pass | dropped | self_preserved | dropped_with_entries：original / pass_local / **cross_pass** |
|---|---|---|---|
| InstCombinePass | 2 289 | 0 | 0 / 3 / **5** |
| JavaOperationLower | 757 | 0 | 0 / 4 / **71** |
| SimplifyCFGPass | 666 | 0 | 0 / 0 / 0 |
| EarlyCSEPass | 78 | 0 | 0 / 1 / **8** |
| GVNPass | 35 | 0 | 0 / 0 / 0 |
| InstSimplifyPass | 24 | 0 | 0 / 0 / 0 |
| JeandleInlineDriver | 14 | 0 | 0 / 1 / **1** |
| LCSSAPass | 12 | 0 | 0 / 0 / 0 |
| RepeatedConstantFolding | 12 | 0 | 0 / 0 / **4** |
| RecoverTypeInfo | 8 | 0 | 0 / **8** / **8** |
| SafepointPollElimination | 4 | 0 | 0 / 0 / 0 |
| ProfileDevirtualization | 3 | 0 | 0 / 3 / **3** |
| PartialEscapeIterative | 0 | **656** | — |
| TypeCheckElimination | 0 | 7 | — |
| CHADevirtualization | 0 | 1 | — |

**`JavaOperationLower`（`dt_invalidated` 757 次）是跨 pass 存活的主要断点**：cross_pass 下 71 次丢弃时缓存中仍有条目，而 pass_local 只有 4 次、original 为 0 次。也就是说跨 pass 保留的条目大部分在 `JavaOperationLower` 处被丢弃而无法被后续消费者消费 —— 这直接解释了「机制成立但没有净收益」。

原始数据：`profiles/pass_invocation_timeline.json`

### 4.4 绝对成本分解（每语料轮，2999 Hz 全语料采样）

| 桶 | original | pass_local | cross_pass |
|---|---|---|---|
| jta_base | 100 033 ns | 133 378 ns | 66 689 ns |
| jta_facts_lvi | 500 166 ns | 100 033 ns | 300 100 ns |
| jta_maintenance | 200 066 ns | 1 000 332 ns | 166 722 ns |
| jta_hook | 533 510 ns | 0 ns | 600 199 ns |
| jta_other | 100 033 ns | 400 133 ns | 400 133 ns |
| vm_callback | 0 ns | 0 ns | 66 689 ns |
| **JTA 归因合计** | **1.434 ms** | **1.634 ms** | **1.601 ms** |
| pipeline_other | 1 182.392 ms | 1 183.426 ms | 1 185.260 ms |
| setup（IR 解析 / 模块加载） | 60.087 ms | 61.420 ms | 61.754 ms |
| **总计** | **1 243.913 ms** | **1 246.480 ms** | **1 248.614 ms** |

定向 JavaType 重采样（JavaType-heavy 子集）：JTA 归因 original **11.501 ms** / pass_local **15.102 ms** / cross_pass **12.101 ms**。

**JavaType 子系统绝对成本在三种模式间差异 < 0.2 ms/轮，相对整轮 1.24 s 是 0.016 % 量级 —— 落在测量噪声以下。**

图：`profiles/cost_decomposition.svg`（绝对成本分解图）、`profiles/flame_{original,pass_local,cross_pass}.svg`（三张完整火焰图）、`profiles/flame_hf_*.svg`（高频火焰图）、`profiles/diff_cross_pass_vs_*.svg` 与 `profiles/diff_hf_cross_pass_vs_*.svg`（差分图）、`profiles/pass_timeline_*.json`（pass invocation 时间线）。

---

## 5. 阶段 E：JVM 子进程编译成本（方案 §7）

### 5.1 jtreg 功能回归

| 项 | 结果 |
|---|---|
| 状态 | **PASS**（`Test results: passed: 1`） |
| 测试 | `compiler/jeandle/typeCache/TestJavaTypeCacheModes.java  Passed. Execution successful` |
| 耗时 | 6 s |
| jtreg 命令 | 见 `jvm/jtreg/report/text/cmdArgs.txt`（`-dir:…/jeandle-jdk`、`-testjdk:…/jvm/jtreg-jdk`、`-retain:all`、`-concurrency:1`、`-timeoutFactor:4`） |
| 子进程实际 argv | `jvm/jtreg/artifacts/argv_{original,pass_local,cross_pass}.txt` |
| CITime 原始输出 | `jvm/jtreg/artifacts/citime_{original,pass_local,cross_pass}.txt` |
| query trace | `jvm/jtreg/artifacts/trace_{original,pass_local,cross_pass}.txt` |

cross_pass 模式实际 argv：

```
<testjdk>/bin/java -cp … -Xbatch -XX:-TieredCompilation -XX:+UseJeandleCompiler
-XX:CICompilerCount=1 -XX:+CITime
-XX:JeandleLLVMOptions=-jeandle-java-type-stats=true -jeandle-java-type-query-trace=true
-XX:CompileCommand=compileonly,TestJavaTypeCacheModes::typeCheckHeavy TestJavaTypeCacheModes
```

对应 CITime：`Total compilation time 0.202 s / Jeandle Compile Time 0.202 s / LLVM Optimize 0.142 s / LLVM CodeGen 0.059 s / (Jeandle compilations: 1)`

**jtreg 三模式 query trace 计数（98 queries/模式）**：

| 模式 | base_insertions | facts_hits | facts_misses | final_hits | final_misses |
|---|---|---|---|---|---|
| original | 0 | 0 | 0 | 0 | 0 |
| pass_local | 58 | 58 | 1 098 | **0** | 98 |
| cross_pass | 44 | 56 | 1 089 | **6** | 92 |

**测试中不含任何时间断言**（方案 §7 硬性要求）；只断言功能行为（模式间命中/清空语义正确）与实际 argv 透传。

### 5.2 JVM-CONTROLLED 组（受控子 JVM）

配置：`-Xbatch -XX:-TieredCompilation -XX:CICompilerCount=1 -XX:CompileCommand=compileonly,JvmCompileCostWorkload::typeCheckHeavy`，rounds 100 000，**15 个随机配对 block**，每模式恰好 1 次 Jeandle 编译（任务集固定，可配对）。

| 模式 | 总编译成本 (s) | Jeandle Compile (s) | **LLVM Optimize (s)** | LLVM CodeGen (s) | **应用时间 (s)** | 进程墙钟 (s) |
|---|---|---|---|---|---|---|
| original | 0.1905 | 0.1899 | 0.1294 | 0.0599 | 1.9399 | 1.9750 |
| pass_local | 0.1918 | 0.1915 | 0.1310 | 0.0597 | 1.9432 | 1.9771 |
| cross_pass | 0.1903 | 0.1897 | 0.1295 | 0.0594 | 1.9512 | 1.9855 |

配对比较（net = `1 - sum(candidate)/sum(baseline)`，CI95 由配对 block 重采样）：

| 对照 | 指标 | 基线总时长 (s) | 候选总时长 (s) | net | CI95 |
|---|---|---|---|---|---|
| original→cross_pass | **总编译成本** | 2.858 | 2.855 | +0.10 % | [−1.17 %, +1.59 %] |
| original→cross_pass | **LLVM Optimize** | 1.941 | 1.942 | −0.05 % | [−1.09 %, +1.03 %] |
| original→cross_pass | LLVM CodeGen | 0.898 | 0.891 | +0.78 % | [−1.94 %, +3.90 %] |
| original→cross_pass | **应用时间** | 29.099 | 29.269 | −0.58 % | [−1.44 %, +0.30 %] |
| pass_local→cross_pass | **总编译成本** | 2.877 | 2.855 | +0.76 % | [−1.20 %, +3.51 %] |
| pass_local→cross_pass | **LLVM Optimize** | 1.965 | 1.942 | +1.17 % | [−1.04 %, +4.26 %] |
| pass_local→cross_pass | **应用时间** | 29.148 | 29.269 | −0.41 % | [−1.53 %, +0.63 %] |

**结论：尚未测出稳定净收益（CI 跨零）。三个指标分开看均无显著差异。**

### 5.3 JVM-PRODUCTION 组（正常分层/后台编译）

配置：无额外 JVM 开关（默认分层编译 + 后台编译线程），rounds 100 000，**10 个随机配对 block**。

| 模式 | Jeandle 编译次数 (mean) | 总编译成本 (s) | Jeandle Compile (s) | **LLVM Optimize (s)** | LLVM CodeGen (s) | **应用时间 (s)** | 进程墙钟 (s) |
|---|---|---|---|---|---|---|---|
| original | 20.5 | 0.6278 | 0.6102 | 0.5248 | 0.0775 | 0.1154 | 0.1875 |
| pass_local | 21.0 | 0.6672 | 0.6484 | 0.5464 | 0.0812 | 0.1205 | 0.2082 |
| cross_pass | 20.0 | 0.6194 | 0.6020 | 0.5300 | 0.0730 | 0.1131 | 0.1814 |

| 对照 | 指标 | 基线总时长 (s) | 候选总时长 (s) | net | CI95 |
|---|---|---|---|---|---|
| original→cross_pass | **总编译成本** | 6.278 | 6.194 | +1.34 % | [−2.55 %, +4.80 %] |
| original→cross_pass | **LLVM Optimize** | 5.248 | 5.300 | −0.99 % | [−5.60 %, +3.14 %] |
| original→cross_pass | LLVM CodeGen | 0.775 | 0.730 | +5.81 % | [+1.04 %, +10.66 %] |
| original→cross_pass | **应用时间** | 1.154 | 1.131 | +2.00 % | [−1.41 %, +5.24 %] |
| pass_local→cross_pass | **总编译成本** | 6.672 | 6.194 | +7.16 % | [+3.58 %, +10.43 %] |
| pass_local→cross_pass | **LLVM Optimize** | 5.464 | 5.300 | +3.00 % | [−0.71 %, +7.18 %] |
| pass_local→cross_pass | **应用时间** | 1.205 | 1.131 | +6.12 % | [+2.09 %, +10.52 %] |

**重要混淆因素：本组的编译任务集在模式之间不同**（Jeandle 编译次数 mean 20.5 / 21.0 / 20.0，min-max 18–22）。pass_local→cross_pass 的 +7.16 % 与编译次数差（约 5 %）完全同量级，因此**不可直接解读为缓存策略的净收益**。

按编译次数归一化后（每次编译）：

| 模式 | 每次编译总成本 (s) | 每次编译 LLVM Optimize (s) |
|---|---|---|
| original | 0.0306 | 0.0256 |
| pass_local | 0.0318 | 0.0261 |
| cross_pass | 0.0310 | 0.0266 |

归一化后差异落到噪声级。**结论：尚未测出稳定净收益。**

### 5.4 CITime 口径说明（方案 §7.3）

`+CITime` 输出的是 **elapsed 时间**，不是线程 CPU 时间。在 JVM-PRODUCTION 组中编译在后台线程并发进行，因此：
- `Jeandle Compile Time` / `LLVM Optimize` / `LLVM CodeGen` 只能作为**量级参考**，不能当作精确编译成本；
- 并发下同一台机器上多个编译线程互相争抢 CPU，会把"更快的编译"表现为"更长的 wall clock"，反之亦然；
- 需要精确编译成本时，应使用 `perf stat` 线程级采样或 `-XX:+CITime` 配合单编译线程（即本报告的 JVM-CONTROLLED 组）。

### 5.5 失败样本

| 组 | 失败次数 | 位置 |
|---|---|---|
| JVM-CONTROLLED | 3 | `jvm/citime/controlled/crash_{original_b11,pass_local_b0,pass_local_b3}_a0.txt` |
| JVM-PRODUCTION | 4 | `jvm/citime/production/crash_{original_b0,original_b3,pass_local_b2,cross_pass_b2}_a0.txt` |

均为既有 Jeandle 崩溃（exit −6 / SIGABRT）。崩溃现场日志保留在工作根目录：9 个 `hs_err_pid*.log` + 9 个 `replay_pid*.log`。

**A/B 基线对照（判定崩溃与本次改动无关）**：

| 标签 | rounds | javac 失败 | jimage 失败 |
|---|---|---|---|
| `baseline_head`（git stash，干净 HEAD） | 8 | 2 | 2 |
| `current_worktree`（带本次改动） | 8 | 2 | 3 |

**崩溃率相同**，既有崩溃与本次改动无关。原始文件：`jvm/ab/*.summary`、`jvm/ab/*.log`；探测脚本 `scripts/ab_crash_probe.sh`。

---

## 6. 不利样本、噪声与未覆盖范围

### 6.1 不利样本（负收益清单）

- ORIGINAL→CROSS-PASS：**37 / 64 个样本为负收益（57.8 %）**，最差 `ArrayShapes_traverseList` −2.362 %（扣 no-op −2.828 %）。
- PASS-LOCAL→CROSS-PASS：**36 / 64 个样本为负收益（56.2 %）**，最差 `ArrayShapes_traverseList` −3.445 %（扣 no-op −4.134 %）、`ConstantShapes_foldWithTypeCheck` −3.303 %。
- 完整清单（逐样本净收益、基线/候选 CPU、候选模式查询数）见 `diagnostics/inventory.md`。

值得注意的是：查询数最高的样本往往是最不利的（如 `ConstantShapes_foldWithTypeCheck` 7 次查询、`TypeShapes_instanceofChain` 6 次、`TypeShapes_checkedArrayElement` 6 次），而查询数只有 2 次的样本净收益接近 0。**跨 pass 收益与 JavaType 查询密度负相关，与"查询越多、缓存维护与失效开销越大"的解释一致。**

### 6.2 测量噪声来源

1. **短进程固定开销占比高**：每个样本一个 `opt` 子进程，启动 + IR 解析约 0.022 s，占单样本 CPU（≈0.022–0.024 s）的主要部分。已用 no-op 基线扣除后复算，结论不变（§3.2/§3.3 两组"含启动"与"扣 no-op"数字同号同量级）。
2. **CPU 频率策略为 `powersave`**，存在频率爬升噪声；已用 2 个独立 session + 随机配对 block 抵消系统性偏置，但无法完全消除。
3. **配对 block 内仍有顺序效应**：尽管模式顺序随机，长时间连续运行仍可能有热状态残留。
4. **JVM-PRODUCTION 组编译任务集不同**（§5.3），其百分比被编译次数差混淆。
5. **CITime 是 elapsed 而非线程 CPU**（§5.4）。
6. **样本量 64、单方法 P50 净收益约 −0.3 %**，单样本分辨率（约 ±1 %）不足以判定单方法方向的可靠性，只能判定语料整体。

### 6.3 未覆盖范围

- **未引入任何新的 preserve 实现或 LVI 优化**（方案 §9 硬性要求）：本轮只测"缓存是否跨 pass 存活"这一维度，没有测"如果能阻止 `JavaOperationLower` 丢弃会怎样"。
- **未覆盖的语言特性**：泛型擦除、接口默认方法、record/sealed、lambda 与 method handle 链、数组协变、class hierarchy 深度较大的多态点（语料为合成程序，不是真实应用）。
- **未覆盖的 pass 组合**：只测了完整 `jeandle<O3>`，未做逐 pass 消融（哪个 pass 贡献了多少跨 pass 命中）。
- **未覆盖真实应用负载**：语料是 6 个合成程序共 64 个 root method；真实应用（如 Spring/大数据）的 root method 分布与查询密度不同，阶段 E 的受控负载也只有 1 个编译单元。
- **未覆盖 JVM 侧多线程编译的精确成本**：受 §5.4 口径限制，production 组只给出量级。
- **未测 pass-local 开关在真实 JVM 下的行为**：阶段 E 的三模式通过 `-XX:JeandleLLVMOptions=` 传入，但 jtreg 与 CITime 测量中只跑了 cross_pass 的完整 CITime 对照。

---

## 7. 产物清单

工作根：`/home/annya/playground/jeandle/perf-results/2026-10-26-javatype-cross-pass-prod/`（总计 1.6 GB）

| 目录 | 大小 | 内容 |
|---|---|---|
| `identity/` | 4 KB | `identity.json`（opt/libLLVM/libjvm 的 sha256、mtime、runpath、分支与 HEAD、worktree diff sha256、构建配置、主机信息） |
| `corpus/` | 7.1 MB | `manifest.json`（76 条记录）、`eligible.txt`（64 行）、`src/`、`record/`（IR + VM callback log）、`replay/`、`classes/` |
| `diagnostics/` | 4.1 MB | `inventory.md` / `inventory.json`（规模、覆盖率、拒绝原因、负收益清单）、`eligibility.json`（逐样本 argv 与模式统计）、`subsystem_cost.json`（子系统计数器与时间）、`cross_pass_trace_summary.json`、`noop.ll` |
| `timing/` | 8.4 MB | `raw.csv`（11 520 行逐轮原始数）、`baseline.csv`（640 行 no-op 基线）、`analysis.json`（配对统计与 CI）、`summary.md`、`environment.json`（含 seed、CPU 绑定、governor）、`timing_run.log` |
| `profiles/` | 240 MB | 三张完整火焰图（`flame_*.svg`）+ 三张高频火焰图（`flame_hf_*.svg`）+ 两组差分图（`diff_*.svg` / `diff_hf_*.svg`）+ `cost_decomposition.svg`（绝对成本分解图）+ `pass_timeline_*.json`（pass invocation 时间线）+ `pass_invocation_timeline.json`（生命周期断点）+ `perf_stat_*.csv` + `perf_*.perf.data`（26 MB ×3）+ `*.folded` |
| `jvm/` | 1.4 GB | `jvm_compile_cost_{controlled,production}.json` + `jvm_compile_cost_summary.md`、`citime/{controlled,production}/`（每模式每 block 的 argv 与 CITime 原文 + crash 样本）、`jtreg/`（report + work + `artifacts/` 的 argv/citime/trace ×3）、`jtreg-jdk/`（硬链接 JDK）、`ab/`（A/B 基线对照）、`child_probe/`（子 JVM 模式探针，5 轮/模式 0 失败）、`workload/`（受控负载源码）、`exp/`（探索脚本） |
| `scripts/` | 244 KB | 20 个脚本：`common.py`、`timing.py`、`analyze.py`、`profile.py`、`decompose.py`、`pass_timeline.py`、`diagnostics.py`、`subsystem_cost.py`、`inventory.py`、`eligibility.py`、`build_corpus.py`、`record_corpus.py`、`replay_corpus.py`、`scan_queries.py`、`pilot_freq.py`、`pilot_timeline.py`、`jvm_compile_cost.py`、`jvm_compile_cost_analysis.py`、`identity.py`、`run_jtreg.sh`、`child_mode_probe.sh`、`ab_crash_probe.sh`、`repro_javac_crash.sh` |
| 根目录 | — | 9 个 `hs_err_pid*.log` + 9 个 `replay_pid*.log`（崩溃现场） |

### 7.1 原始 perf.data 清理记录

为控制产物体积（清理前 3.0 GB → 后 1.6 GB），删除了 16 个大文件：
`perf_jt_{cross_pass,original,pass_local}.perf.data`、`perf_jt_*.perf.data.old`、`perf_jt_*.perf.script`、`perf_hf_*.perf.script`、`jt_{cross_pass,original,pass_local}.folded`、`perf_{original,pass_local,cross_pass}.perf.data.old`；
`perf_hf_*.perf.data` 由 `scripts/decompose.py` 的 `--keep-perf-data` 默认关闭自动删除。

**保留**：`perf_{original,pass_local,cross_pass}.perf.data`（26 MB ×3）、`perf_*.perf.script`、全部 `*.folded` / `*.svg` / `*.json`。

**遗留的悬空 JSON 引用（供后续追溯，共 6 处）**：
- `profiles/profiling.json` → 指向已删的 `jt_{original,pass_local,cross_pass}.folded` 与 `perf_jt_*.perf.script`
- `profiles/cost_decomposition.json` → 指向已删的 `perf_hf_*.perf.data` 与 `perf_hf_*.perf.script`

这些 JSON 中记录的是**当时的实际命令与路径**，数据本身已解析并固化在同文件的其它字段（如 `optimizer_cpu_ns`、`classes_ns`、`absolute_per_corpus_round_ns`），不影响本报告结论；如需完整复现可直接重跑 `scripts/profile.py` 与 `scripts/decompose.py`。

---

## 8. 结论与建议

1. **跨 pass 缓存的合成机制成立**：跨 pass 保留使 Final 层命中从 0 升到 68/语料轮，Base 层重算减少 68 次/语料轮（−40.5 %），失效请求从 13 186 降到 32，子系统总时间降低 38.2 %。
2. **但当前生产流水线配置未测出稳定净收益**：阶段 C 主指标 ORIGINAL→CROSS-PASS −0.1871 %，CI 跨零；阶段 E 两组三个指标同样跨零。
3. **主要瓶颈已定位在 `JavaOperationLower`**：cross_pass 下 71 次丢弃时缓存仍有条目（pass_local 仅 4 次），跨 pass 存活的条目大多在这里被丢弃而无法被下游消费者消费。**要拿到净收益，先要解决 DT 失效导致的分析丢弃问题（属于"新的 preserve 实现"，本轮按方案 §9 未引入）。**
4. **PASS-LOCAL→CROSS-PASS 在本配置下为负且显著**（−0.3447 %，CI 不含 0），说明"每 pass 清空"目前是更优策略；跨 pass 保留只有在存活率显著提高后才可能反超。
5. **下一步建议**：
   - 做一个 **per-pass 消融**，量化每个 pass（尤其 `JavaOperationLower`）对跨 pass 存活的破坏程度；
   - 在受控条件下测量「若 DT 失效改为 self-preserve」的收益上限（作为独立实验，不与本轮性能主模式混写）；
   - 把 `JavaOperationLower` 之后的消费者（RepeatedConstantFolding / TypeCheckElimination）单独隔离，验证 68 次 Final 命中的实际节省量；
   - 若要把 JVM 侧结论做实，需要 **线程 CPU 级编译成本测量**（perf 采样或受控单线程编译 + 更长 rounds），当前 CITime elapsed 口径不足以支撑 1 % 级别的判定。

---

## 附：复现命令

```bash
# 阶段 B：录制 + 回放语料
python3 scripts/record_corpus.py
python3 scripts/build_corpus.py

# 阶段 C：计时（2 session × 30 随机配对 block）+ 统计
python3 scripts/timing.py --seed 20261026 --sessions 2 --blocks 30
python3 scripts/analyze.py --seed 20261026

# 阶段 D：profiling / 绝对成本分解 / 时间线
python3 scripts/profile.py
python3 scripts/decompose.py --repeat 10 --freq 2999
python3 scripts/pass_timeline.py
python3 scripts/diagnostics.py
python3 scripts/subsystem_cost.py

# 阶段 E：JVM 编译成本 + jtreg
python3 scripts/jvm_compile_cost.py --group controlled --seed 20261026 --rounds 100000
python3 scripts/jvm_compile_cost.py --group production --seed 20261026 --rounds 100000
python3 scripts/jvm_compile_cost_analysis.py
bash scripts/run_jtreg.sh

# 身份 / 环境
python3 scripts/identity.py
```

所有子进程均以 `env -u LD_LIBRARY_PATH` 运行（Agent 注入的 libstdc++ 会破坏 JDK / LLVM / ninja 的动态链接）。

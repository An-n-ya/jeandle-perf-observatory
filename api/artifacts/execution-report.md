# JavaType 缓存 perf 性能诊断执行报告

日期：2026-10-23。执行依据：[JavaType-Perf-Profiling-Plan-2026-10-23.md](JavaType-Perf-Profiling-Plan-2026-10-23.md)。

状态：已完成 L1 五场景、一个 L2 CFF 回放的四模式基线、事件计数和调用栈采样，并完成调度/RSS 补测与频率/长栈抽查。源码、输入和二进制身份在测量结束后复核一致。质量限制与未覆盖项保留在本报告中。

## 1. 结论与适用范围

当前 S1 已减少重复的基础类型计算；这批回放中的下一处主要成本是上下文事实查询，尤其是 LVI，而非 Base 表删除。deep-static、tce-cha 的诊断性 CPU 数据显示 S1 比 ORIGIN 低约 13%；leaf-static、virtual-cfg 则略高。原先短进程实验无法区分收益，不能据此认定缓存没有作用。

S1 的失效入口在主采样中约占整进程 cycles 的 0.6%–1.7%，样本量不足以细排其中的 erase、集合操作与析构。继续替换失效数据结构，当前可见收益空间较小。优先实验应针对 LVI 的重复子问题，以及修改后分析结果的保留契约。

以上结论限于本轮 LLVM 回放。L1 是 CHA 或 TCE→CHA 合成输入，L2 是从现有 lit fixture 克隆的 CFF 单 pass 回放；没有把它们视作完整 Jeandle pipeline 或真实 JVM 编译。每个缓存仍是函数级缓存，独立函数放大没有把单个 Base 表扩为 8192 倍。deep 的单函数 Base 规模约 66，wide 约 18；本轮不覆盖超大单函数缓存。

所有时间差均为一个 session、10 个随机配对轮次的诊断数据。没有执行两个 session × 30 轮的正式速度验收，故不作生产编译性能承诺。

## 2. 身份、环境与正确性

- 主机：`annya@100.122.220.40`；仓库：`/home/annya/playground/jeandle/jeandle/jeandle-llvm`。
- 分支：`test/javatype-cache-design`；HEAD：`357604c7724e49eace6fbfa42e4f671b12b5ff98`。
- 完整 tracked + untracked source patch SHA-256：`d17c2da23a1332ebdba7d9b3ab52fe5f914e0f684607c4ca78f6790e560d0a9d`。
- profiling opt SHA-256：`fcd3fd2fa57c5bef3f1aef5372c936e627b08bc332cc1adabcfb6e5f947e3079`。
- opt build-id：`376a5dc08ddadd66005d07a52358796599405b56`。
- 原有未提交改动完整保留；没有 commit、push、reset 或 clean。

profiling build 沿用原 Release 的 GCC 15、`-O3 -DNDEBUG`、X86-only、无 LTO/RTTI/EH，增加 `-g`。四模式来自同一二进制。配置差异见 [配置对比](artifacts/java-type-perf-2026-10-23/build/configuration-comparison.json)，完整配置与构建日志见 [build-records.tar.gz](artifacts/java-type-perf-2026-10-23/build-records.tar.gz)。

固定 CPU 16，为 atom PMU 对应的核，没有 SMT sibling；governor 为 powersave。服务器为 Linux 7.1.3，`perf_event_paranoid=2`。未修改 sysctl、capability、governor 或整机频率设置。硬件计数仅使用 `cpu_atom/*`；`cpu_core/*` 的 0% running 行已排除。有效硬件事件的 pcnt-running 最低为 99%，没有低于 90% 的有效记录。

JavaTypeQueryTests **44/44**、六组相关 lit **96/96** 通过。首次 lit 因 profiling build 缺 llvm-config/llvm-readobj 失败，补齐后重跑通过，失败日志仍保留。小输入诊断中四模式输出 IR 哈希一致，预期优化调用点数量全部满足，缓存校验 skip 为 0。诊断启用的重算和计数未混入正式计时或采样。

证据：[单测](artifacts/java-type-perf-2026-10-23/build/JavaTypeQueryTests.log)、[lit](artifacts/java-type-perf-2026-10-23/build/Jeandle-JavaType-lit.log)、[首次失败](artifacts/java-type-perf-2026-10-23/build/Jeandle-JavaType-lit.failed-missing-tools.log)、[manifest](artifacts/java-type-perf-2026-10-23/manifest.json)、[source.patch](artifacts/java-type-perf-2026-10-23/source.patch)、[结束时身份](artifacts/java-type-perf-2026-10-23/identity-post.json)。

## 3. 策略、输入与测量口径

| 模式 | 开关 | 解释 |
| --- | --- | --- |
| ORIGIN | `-jeandle-disable-java-type-cache` | 原始查询引擎 |
| FULL | `-jeandle-java-type-force-full-invalidation` | 缓存引擎，每次通知全清 |
| S0 | `-jeandle-java-type-force-base-scan-invalidation` | 选择性失效，Base 扫描 |
| S1 | 无上述开关 | 选择性失效，Base 逐 key 删除 |

ORIGIN/FULL 涉及不同查询引擎，不能将其全部差异归为容器开销。S0/S1 才隔离 Base 删除方式。所有性能运行关闭 stats、verification 和 debug logging，保留必需的 VM callback 回放。

| 输入 | 独立函数数 | 每函数形状/消费者 |
| --- | ---: | --- |
| deep-static | 8192 | 64 层 select，16 个 CHA 位置 |
| wide-static | 8192 | 16 层 select，64 个 CHA 位置 |
| leaf-static | 8192 | 叶子，32 个 CHA 位置 |
| tce-cha | 8192 | 64 层 select，TCE→CHA |
| virtual-cfg | 8192 | 叶子，32 个 virtual/CFG 改写位置 |
| cff-cache-reuse | 262144 | 原 cache-reuse fixture 克隆，6 次 JavaType 查询/函数 |

deep/S1 的放大 pilot 用户态 CPU：512/2048/4096/8192 函数分别约为 0.354/1.428/2.855/5.730 秒。保持单函数形状和预算不变，没有通过加深 DAG 放大。

基线：每模式预热 3 次，再做 10 个随机配对轮次；stat：每组 3 次；主 profile：每 case/mode 3 份。record 使用 `cycles:u`、199 Hz、DWARF 8192 bytes。性能运行串行，不与构建或其他 benchmark 并发。L1 profile 的实际模式顺序固定，为本轮与计划随机 profile 顺序的偏差；无采样基线和 L2 profile 使用固定 seed 随机排列。未将固定顺序 profile 的 elapsed 用于速度排名。

所有占比使用 event period 权重。排他分类每样本只计一次，分组和为 100%；inclusive 按样本栈是否包含入口判断，递归帧不重复计权。父子 inclusive 不可相加。JavaType 视图包含查询、失效和分析结果回收；LVI 子树是其子集。容器/分配共享函数依调用栈归属，不将所有 DenseMap、malloc/free 都算给三层缓存。

## 4. 无采样基线与硬件计数

下表为中位数，单元格为 **user 秒 / wall 秒**。

| 场景 | ORIGIN | FULL | S0 | S1 |
| --- | --- | --- | --- | --- |
| deep-static | 6.6021 / 6.7558 | 6.5553 / 6.7529 | 5.8693 / 6.0577 | 5.7675 / 5.9656 |
| wide-static | 16.6992 / 16.9440 | 17.1113 / 17.4098 | 16.2592 / 16.5506 | 16.1142 / 16.3988 |
| leaf-static | 4.9481 / 5.0631 | 5.0790 / 5.2266 | 5.0480 / 5.2077 | 5.0157 / 5.1741 |
| tce-cha | 6.6968 / 6.8403 | 6.6310 / 6.8385 | 5.9161 / 6.1037 | 5.7989 / 5.9812 |
| virtual-cfg | 10.7947 / 11.0789 | 11.1356 / 11.4702 | 11.0372 / 11.3784 | 11.0492 / 11.3929 |
| cff-cache-reuse | 6.4977 / 6.7273 | 6.4222 / 6.6483 | 6.3667 / 6.5987 | 6.3188 / 6.5433 |

配对中位差 **S1 − 对照**，单位秒；负数表示 S1 用户态 CPU 更少。区间、每轮原始值及 system CPU 见附件 JSON/CSV。这是诊断比较。

| 场景 | S1−ORIGIN | S1−FULL | S1−S0 |
| --- | --- | --- | --- |
| deep-static | -0.8339 | -0.7878 | -0.1025 |
| wide-static | -0.6176 | -1.0388 | -0.1455 |
| leaf-static | +0.0740 | -0.0480 | -0.0425 |
| tce-cha | -0.8948 | -0.8251 | -0.1139 |
| virtual-cfg | +0.2604 | -0.0773 | +0.0011 |
| cff-cache-reuse | -0.1741 | -0.1027 | -0.0533 |

硬件事件每组 3 次，下表为 **十亿 cycles / IPC / branch miss %**。IPC 来自同一次运行的 instructions/cycles；branch miss % 为 misses/branches，分母不是 instructions。完整 instructions 和原始 runtime 字段保留在 stat 附件。

| 场景 | ORIGIN | FULL | S0 | S1 |
| --- | --- | --- | --- | --- |
| deep-static | 23.483 / 2.402 / 0.586% | 23.387 / 2.394 / 0.570% | 20.863 / 2.391 / 0.598% | 20.555 / 2.397 / 0.596% |
| wide-static | 60.021 / 2.291 / 0.527% | 61.423 / 2.273 / 0.540% | 58.217 / 2.266 / 0.575% | 57.637 / 2.275 / 0.579% |
| leaf-static | 17.587 / 2.131 / 0.504% | 18.125 / 2.109 / 0.515% | 18.041 / 2.105 / 0.526% | 17.829 / 2.115 / 0.523% |
| tce-cha | 23.930 / 2.388 / 0.587% | 23.771 / 2.384 / 0.561% | 20.993 / 2.388 / 0.591% | 20.653 / 2.398 / 0.596% |
| virtual-cfg | 38.742 / 2.092 / 0.825% | 39.981 / 2.065 / 0.876% | 39.576 / 2.074 / 0.865% | 39.641 / 2.070 / 0.881% |
| cff-cache-reuse | 23.471 / 1.696 / 0.688% | 23.002 / 1.638 / 0.700% | 22.715 / 1.614 / 0.726% | 22.598 / 1.614 / 0.717% |

deep 的 ORIGIN/S1 IPC 都约 2.40，cycles 随工作量下降；这些数据支持减少重复计算的解释，不能据此宣称改善了硬件 cache miss。generic cache-misses 未被用来解释 JavaType 缓存命中。

## 5. 调用栈归因

### 5.1 整进程与 JavaType 子树

每格为 **JavaType inclusive % / 其中 LVI inclusive 占整进程 %**，取三份 profile 的中位数。后者并非以 JavaType 为分母。

| 场景 | ORIGIN | FULL | S0 | S1 |
| --- | --- | --- | --- | --- |
| deep-static | 56.97 / 40.44 | 56.40 / 40.30 | 53.03 / 44.92 | 50.31 / 45.39 |
| wide-static | 55.57 / 37.08 | 56.80 / 36.27 | 54.46 / 37.83 | 54.33 / 37.24 |
| leaf-static | 30.09 / 18.00 | 33.56 / 18.37 | 32.57 / 17.86 | 32.55 / 19.29 |
| tce-cha | 56.56 / 39.30 | 56.96 / 38.84 | 51.09 / 44.65 | 49.93 / 44.44 |
| virtual-cfg | 41.89 / 21.02 | 42.57 / 20.09 | 41.79 / 20.24 | 43.77 / 20.46 |
| cff-cache-reuse | 10.29 / 0.00 | 8.79 / 0.00 | 8.36 / 0.00 | 7.39 / 0.00 |

失效入口 inclusive 占整进程 cycles 的中位数如下。多个格子累计不足 100 个失效样本，只用于判断量级，不细排 erase、worklist 或析构。ORIGIN 的空缓存通知也可能产生少量调用开销，零样本不代表数学上的零成本。

| 场景 | ORIGIN | FULL | S0 | S1 |
| --- | --- | --- | --- | --- |
| deep-static | 0.00 | 1.29 | 2.03 | 0.69 |
| wide-static | 0.06 | 1.42 | 2.08 | 1.08 |
| leaf-static | 0.10 | 1.17 | 2.25 | 1.68 |
| tce-cha | 0.00 | 1.03 | 2.34 | 0.60 |
| virtual-cfg | 0.09 | 1.28 | 0.89 | 0.97 |
| cff-cache-reuse | 0.00 | 0.70 | 1.10 | 0.71 |

S1 的排他分组如下，三份 profile 合并计算。与前表的“每份百分比中位数”不同，数值会略有差异。其余/未细分包括查询剩余部分、其他 pass 工作、模块回收和无法确定的操作；没有将它们强归为缓存成本。

| 场景 | 查询 LVI | 基础类型 | 失效 | JavaType 回收 | 解析 | 外部 replay | 外部 LVI | 外部 DT | 其余/未细分 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deep-static | 45.36 | 0.89 | 0.74 | 0.11 | 24.91 | 2.29 | 2.17 | 1.67 | 21.85 |
| wide-static | 38.12 | 0.32 | 1.25 | 0.07 | 16.91 | 3.63 | 3.46 | 1.80 | 34.44 |
| leaf-static | 19.59 | 0.17 | 1.54 | 0.20 | 25.84 | 5.23 | 2.41 | 2.62 | 42.40 |
| tce-cha | 44.66 | 0.97 | 0.74 | 0.14 | 25.03 | 2.53 | 2.05 | 1.66 | 22.23 |
| virtual-cfg | 20.50 | 0.13 | 0.93 | 0.11 | 10.45 | 1.36 | 2.28 | 20.19 | 44.06 |
| cff-cache-reuse | 0.00 | 0.68 | 0.82 | 0.95 | 46.82 | 1.63 | 0.19 | 3.64 | 45.28 |

### 5.2 查询为何仍然昂贵

主要调用链：

```text
CHA::tryNarrowJavaObjType
  → JavaTypeAnalysisResult::getJavaType
  → getCachedJavaType → factsAt → isNullEdge
  → LVINullEdgeOracle::operator()
  → LazyValueInfo::getPredicateOnEdge / getValueOnEdge
  → solve → solveBlockValueSelect
  → isGuaranteedNotToBeUndef → programUndefinedIfUndefOrPoison
```

`CachedJavaType.cpp:1337` 附近的 predecessor 循环会查询 null edge；`LVINullEdgeOracle.cpp:37` 委托 LVI。LVI 的 `LazyValueInfo.cpp:939` 附近对 select condition 做 undef 证明；`ValueTracking.cpp:8270` 起会扫描后续指令/uses，带 32 条指令的扫描界限。生成输入的多层 select 反复使用同一个 `%c`。

BaseTypes 缓存的是 JavaType 基础类型，不会代替 LVI 的值格与 undef/poison 分析。Klass 已知也不等于指针非 null，不能直接省略 null-edge 证明。

CHA 的 `CHADevirtualization.cpp:477/483` 在对应改写路径清空 LVI；`JavaTypeCache::invalidate` 对 call/memory/terminator 保守清空上下文结果。这解释了 Base 保留后，上下文计算仍反复发生。

对于 virtual-cfg，查询之外还有约 20% 的 DT 更新成本，原生 self 栈中出现 SemiNCAInfo::DeleteReachable、getNodeInfo、runSemiNCA 等。这里应称为 DT 更新，不能仅凭函数名断言每次都完整重建。

对于 CFF，query 基本在 entry block，factsAt 提前返回，LVI 为零样本符合源码路径；这不代表 CFF 的其他输入也没有 LVI 成本。其进程约 47% 用于 IR 解析，因此查询层的小优化会被摊薄。

热点源码与文件哈希见 [source-context.json](artifacts/java-type-perf-2026-10-23/source-context.json)；`perf annotate` 原始输出见 [poison](artifacts/java-type-perf-2026-10-23/annotate/poison.txt)、[LVI select](artifacts/java-type-perf-2026-10-23/annotate/lvi-select.txt)、[invalidate](artifacts/java-type-perf-2026-10-23/annotate/invalidate.txt)。失效的 annotate 仅作源码定位，样本不足以细分内部成本。

### 5.3 结构诊断：保留是否转化为复用

以下为独立的 8 函数正确性诊断，不能将带重算校验的 query time 作为性能结果。

| 场景 | 查询数 | FULL Base 插入 | S1 Base 插入 | S1 Path hit/miss | S1 Final hit/miss |
| --- | --- | --- | --- | --- | --- |
| deep-static | 128 | 8448 | 528 | 0/960 | 0/128 |
| wide-static | 512 | 9216 | 144 | 0/16128 | 0/512 |
| leaf-static | 256 | 256 | 8 | 0/3968 | 0/256 |
| tce-cha | 136 | 8976 | 528 | 0/960 | 0/136 |
| virtual-cfg | 256 | 256 | 8 | 0/7936 | 0/256 |
| cff-cache-reuse | 48 | 24 | 8 | 0/0 | 24/24 |

deep 的 Base 插入从 8448 降为 528，wide 从 9216 降为 144，配合同工作量 CPU/cycles 下降，支持 Base 复用产生收益。现有 BaseHits 只统计 base-only 顶层查询，不代表递归 Base 命中数；本报告没有把该字段为 0 当作 Base 没有复用。

L1 的 Path/Final hit 均为 0，主要成本持续落在上下文计算与其支持分析。CFF 中 FULL 和 S1 都有 24 次 Final hit，因此不能把这些命中全部归功于选择性失效；S1 的额外保留主要体现为更少的 Base 重新填充。

累计 retained 数不等于后来命中数。本轮未为每条 Base entry 建立跨修改的永久身份轨迹，尚不能精确给出每类保留条目的重访收益。

### 5.4 按消费者与值存储成本观察

下表以 S1 的 JavaType 相关 cycles 为分母，来自实际栈；未恢复到调用者的部分保留为未识别，不分配给猜测的消费者。

| 场景 | CHA % | TCE % | CFF % | FAM 回收 % | 未识别 % |
| --- | --- | --- | --- | --- | --- |
| deep-static | 97.86 | 0.00 | 0.00 | 0.23 | 1.92 |
| wide-static | 84.10 | 0.00 | 0.00 | 0.13 | 15.76 |
| leaf-static | 93.91 | 0.00 | 0.00 | 0.61 | 5.47 |
| tce-cha | 97.39 | 0.45 | 0.00 | 0.28 | 1.88 |
| virtual-cfg | 70.01 | 0.00 | 0.00 | 0.24 | 29.75 |
| cff-cache-reuse | 0.00 | 0.00 | 87.22 | 12.78 | 0.00 |

RecoverTypeInfo、RepeatedCFF、ArrayCopySpecialization、PEA 及完整 pre-PEA/JVM pipeline 未在本轮放大采样中覆盖；其缺失不是零成本。TCE→CHA 中主要采样成本仍由 CHA 产生，查询数量不能代替成本权重。

| S1 场景 | JavaType 构造/复制/移动/析构 % | 相关堆分配/释放 % |
| --- | --- | --- |
| deep-static | 1.21 | 0.95 |
| wide-static | 3.55 | 1.76 |
| leaf-static | 2.38 | 2.37 |
| tce-cha | 0.94 | 0.94 |
| virtual-cfg | 2.65 | 2.08 |
| cff-cache-reuse | 1.11 | 0.39 |

这是调用栈交叉视图，分母仍为整进程，可能与 LVI、失效或回收重叠，不能再加到排他表中。堆操作也包含 LVI 等被调用分析的分配；未将其全部归于 Base/Path/Final。未知 libc 叶帧使精确的 copy/allocator/缓存层细分仍不完整。

## 6. 样本质量、失败记录与限制

主 profile 共 72 份，另有 5 份抽查。每 case/mode 3 份累计样本如下，格式为总样本/JavaType 相关样本。

| 场景 | ORIGIN | FULL | S0 | S1 |
| --- | --- | --- | --- | --- |
| deep-static | 4034 / 2259 | 4015 / 2235 | 3602 / 1853 | 3535 / 1772 |
| wide-static | 10141 / 5591 | 10404 / 5855 | 9867 / 5382 | 9804 / 5248 |
| leaf-static | 3015 / 883 | 3114 / 1030 | 3103 / 992 | 3071 / 984 |
| tce-cha | 4064 / 2286 | 4082 / 2293 | 3622 / 1821 | 3562 / 1761 |
| virtual-cfg | 6606 / 2773 | 6825 / 2922 | 6798 / 2814 | 6793 / 2965 |
| cff-cache-reuse | 4012 / 391 | 4007 / 340 | 3940 / 311 | 3918 / 281 |

L1 每模式跨场景已超过调查样本目标。部分 leaf 单元格略低于 1000，CFF 只有约 281–391 个 JavaType 样本，因此 CFF 只作总体占比观察，不为其缓存内部子热点排名；少于 100 样本的子项也不排名。没有通过不断提高频率制造热点。

原始事件统计核验 77 份 perf.data：LOST record=0，LOST_SAMPLES record=0，THROTTLE record=0。原始统计、record stderr 与数据哈希均保留。

| 场景 | 全部未知叶帧 | JavaType 内未知叶帧 | wall 开销 | 栈到达 libc/start |
| --- | --- | --- | --- | --- |
| deep-static | 9.92% | 1.31% | 3.05% | 6.94% |
| wide-static | 8.61% | 2.50% | 1.77% | 5.84% |
| leaf-static | 12.88% | 3.99% | 3.70% | 9.37% |
| tce-cha | 9.58% | 1.51% | 3.62% | 6.94% |
| virtual-cfg | 9.38% | 3.75% | 2.00% | 5.29% |
| cff-cache-reuse | 13.55% | 8.54% | 3.87% | 18.05% |

未知比例包含 DSO 已知但符号未知的 libc 叶帧。先前只看 DSO unknown 得到的 pilot 0.17% 口径不完整，已撤回。匹配 libc build-id 的官方 debuginfod 请求返回 404，未安装系统包或改变安全配置；JavaType 子树未知叶帧未全部达到 <1% 目标，故 allocator 内部和细粒度缓存层成本明确标为归因不完整。

8 KiB 栈很多未到进程根，但多数能够恢复查询/helper 边界。使用冻结 opt 的原生符号表补全所属函数；分类只匹配函数所属类与名字，不匹配形参中的 LazyValueInfo/DominatorTree。原生/内联两种栈已对同一 pilot 校验粗粒度一致性。频率与长栈抽查如下；它们每档一份，仅作稳定性调查。

| 抽查 | 样本 | JavaType % | 查询 LVI % | 栈到根 % | 相对同规模无采样 wall 开销 |
| --- | --- | --- | --- | --- | --- |
| deep-199-32k | 1185 | 51.81 | 45.59 | 31.25 | +3.51% |
| high-399-8k | 2359 | 50.20 | 45.41 | 6.63 | +5.16% |
| low-49-8k | 290 | 48.84 | 44.31 | 6.42 | +2.33% |
| virtual-cfg-199-32k | 2269 | 42.63 | 19.38 | 15.35 | +2.63% |
| wide-static-199-32k | 3267 | 54.65 | 38.30 | 22.12 | +1.68% |

上述 wall 开销包含 perf 启动、收尾和数据写入，只用来检查扰动；sample duration 与 user CPU 的比较不能替代这个同口径对照。超过 5% 的档位仅用于调查，不进入无采样速度排名。32 KiB 的消费者恢复程度也见 quality-summary.json；它不能使未解析 libc 符号自动可用。

本轮 399 Hz 档的 wall 开销约 5.15%，超过调查阈值，因此用 49/199 Hz 检查；低/高频 LVI 占整进程分别约 44.31%/45.41%，主采样继续采用 199 Hz。三组 32 KiB 抽查相对主表的 JavaType 占比变化不超过约 1.5 个百分点，virtual/wide 的消费者已几乎全部恢复到 CHA/FAM。32 KiB 仍非完整进程根栈，精细调用者和未知 libc 内部操作不作完整归因。

### 调度与 RSS 补测

L1 原始 runner 的 RSS 所有场景/模式均为 1,892,964 KiB；其哈希函数整块读取约 1.8 GiB opt，父进程高水位污染了子进程峰值记录。原始 RSS 保留但不作缓存空间比较。补测改为流式哈希，并通过小内存父进程 wait4 直接取得 opt 的 RSS、user/system CPU 和 context switches。

在 paranoid=2 下，即使请求不带 `:u` 的软件事件，perf 仍将本机实际事件报告为 `:u`，switch/migration 继续为零。因此 context switches 使用 wait4，migration 只确认固定 affinity，不将 perf 的零值解释为实测无迁移。软件 task-clock 包含小型 Python launcher，补测不进入正式时间排名。

| 场景 | ORIGIN RSS MiB | FULL RSS MiB | S0 RSS MiB | S1 RSS MiB | S1 voluntary/involuntary 切换 |
| --- | --- | --- | --- | --- | --- |
| deep-static | 389.9 | 542.4 | 542.6 | 542.3 | 0/56 |
| wide-static | 568.1 | 725.2 | 725.1 | 725.1 | 0/202 |
| leaf-static | 305.4 | 422.2 | 422.2 | 422.0 | 0/52 |
| tce-cha | 389.1 | 541.3 | 541.3 | 541.5 | 0/68 |
| virtual-cfg | 730.8 | 887.8 | 887.6 | 887.9 | 0/133 |
| cff-cache-reuse | 728.3 | 726.0 | 725.9 | 725.6 | 0/84 |

原 stat JSON 的 `enabled_pct` 是历史字段命名错误，实际保存 perf 分隔格式的事件 runtime 数值；`running_pct` 才是 pcnt-running。本报告不将前者当百分数。软件调度受限和 RSS 问题均保留原始记录与修正后的解释。

### 其余执行边界

- 没有运行 P1–P5 全进程 perf 并将其叫作纯失效；PauseTiming 不会暂停 perf 的范围问题没有被引入。
- 主测量期间源码与 opt 冻结；外置辅助脚本放结果目录，避免改变测量身份。没有为了统计重访而保留已删除 Value。
- 原计划三份 perf self/inclusive 文本改为：完整原始栈、每份原生 self、原始事件统计，以及可重算的 inclusive/排他 CSV。pilot 还保留原版 self/inclusive。L1 栈展开内联；L2 为减少重复源码解析导出原生 DWARF 栈，原始 perf.data 仍支持内联/源行分析。
- 64 层 select、同一个 condition、频繁调用改写/分析清空是本轮输入的特征，可能放大 LVI 的该路径。不能外推为所有真实 Java 方法的热点比例。
- 尚无完整 RecoverTypeInfo、RepeatedCFF、pre-PEA high-tier 或 JVM 采样；没有新增 L3 驱动器，现有 L1 已能解释主要成本，CFF 的细分仍标为证据不足。

## 7. 下一轮优先实验

### 实验 1：在一次 LVI solve 内缓存重复 condition 的 undef 证明

依据：deep/tce 的 LVI 子树约占整进程 cycles 的 44%–45%；select 链反复使用相同 `%c`，`solveBlockValueSelect` 重复调用 `isGuaranteedNotToBeUndef(Cond, AC)`，并进入 ValueTracking 扫描。热点源行见本报告 5.2 和 annotate。

方案：先加默认关闭的计数，确认每次 solve 中相同 Cond 的重复评估，再试 query/solve 局部 memo。不要直接建立跨 IR 修改的全局缓存。memo 的有效期必须覆盖同一 IR、同一 AC 状态、同一种证明请求；缓存 false 也要验证精度未变。

受益预期：优先 deep-static、tce-cha，其次有重复 select condition 的真实回放。维护成本较低：局部生命周期无需新增跨修改依赖图，但须确认求解过程不会改变证明所依赖的状态。

验收：相同 Cond 的实际 ValueTracking 评估数显著下降；对照记录 LVI/ValueTracking cycles 与总体 user CPU。undef、poison、freeze、assume、循环/预算边界和所有既有正确性测试通过，关键优化数和完整输入的输出精度保持。建议将 ≥5% 的 deep/tce CPU 改善作为继续投入的目标，正式性能结论再用两 session × 30 轮验证。

### 实验 2：明确修改事件的分析影响，减少不必要的 LVI/上下文重算

依据：L1 Path/Final 0 hit，Base 插入已大幅减少；CHA 对应路径多次清空 LVI。wide 和 virtual 除 LVI 外仍有 factsAt 遍历与类型值构造成本。相比优化删除入口，避免重建被删掉的上下文结果可能有更大的空间。

方案：让改写 helper 报告实际影响，例如是否改变 CFG、call 的 nullability/dereferenceable/assume 事实、内存行为、Value operands 或仅修改不影响分析的元数据。先审计 LVI 的依赖与更新接口；仅在能证明保留正确的事件上保留结果，其余继续保守清空。调用目标变化、CallBase 新建、Klass 已知均不能单独作为保留 null/poison 事实的理由。

必须继续在旧 Value/use 图存活时通知；考虑批量通知时，先界定无查询穿插的修改窗口。跨删除身份与 FAM 生命周期仍遵守既有边界。

验收：记录每种清空原因、oracle 调用数、实际 retained→hit，而非累计 retained。与全新 DT/LVI/FAM 参考逐次比较 Query—Mutate—Query；覆盖 call attrs 增删、null guard、assume、内存访问、CFG、PHI、RAUW/删除及地址复用。以 LVI 相关 CPU 至少降低 20%、deep/wide 总体 user CPU 至少降低 5% 为实验目标，同时审查 leaf/virtual 是否回退；这些是验收目标，不是本轮已证明的收益。

目前不建议直接实现 S2/S3/S4 或替换 DenseMap。本轮 S1 失效只占约 1% 量级；完全消除它也只有同量级 CPU 收益空间，而且样本不足以给精确上限。相比之下，deep 的 LVI 约 45% 提供更大的理论空间，但其中并非全部可缓存，cycles 的 Amdahl 上限也不是墙钟承诺。若未来真实 workload 出现高 C 或巨大单函数表，再以该 workload 重新比较分组索引、epoch 或反向依赖登记的净成本。

## 8. 产物与复现

服务器持久目录：

```text
/home/annya/playground/jeandle/perf-results/2026-10-23-javatype-perf/
  build/                         配置、符号、单测与 lit 日志
  run/manifest.json              身份与输入
  run/baseline/                  L1 无采样每轮记录
  run/stat/                      L1 原始分组计数
  run/profiles/<case>/<mode>/    60 份主 profile
  run/l2/                       CFF baseline/stat/12 份 profile
  run/diagnostics/scheduling/    72 份补测
  run/diagnostics/quality/       5 份频率/长栈抽查
  run/diagnostics/annotate/      热点源行与汇编
  run/perf-data-ledger.json      全部 perf.data 绝对路径、大小和 SHA-256
  run/input-identity-post.json   结束时输入/cblog 哈希
  run/identity-post.json         结束时源码与二进制哈希
```

大 perf.data 保留在服务器，准确位置与哈希见 [ledger](artifacts/java-type-perf-2026-10-23/perf-data-ledger.json)。本地保留 [原始小型记录](artifacts/java-type-perf-2026-10-23/run-records.tar.gz)、[主表](artifacts/java-type-perf-2026-10-23/report-tables.md)、[排他分类](artifacts/java-type-perf-2026-10-23/attribution/attribution.csv)、[每份 inclusive/质量数据](artifacts/java-type-perf-2026-10-23/attribution/profile-runs.csv)、[调度/RSS](artifacts/java-type-perf-2026-10-23/scheduling-summary.csv)、[质量汇总](artifacts/java-type-perf-2026-10-23/quality-summary.json)。

辅助图：[deep/S1 火焰图](artifacts/java-type-perf-2026-10-23/deep-static-s1-flamegraph.svg)，按 period 权重生成。图中根栈可能不完整，不将宽度变化直接解释成绝对时间变化。生成器版本为 `javatype-flamegraph-1`，源码与校验脚本保留在 [scripts/](artifacts/java-type-perf-2026-10-23/scripts/README.md)。

所有性能数据均来自同一冻结身份；最后未改动缓存算法，也未自动实现下一轮方案。

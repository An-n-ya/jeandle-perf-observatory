# JavaType 昂贵上下文查询缓存复用测试

日期：2026-10-23。按用户要求，每个场景仅运行 **3 轮配对回放**。

## 提交与分支

- 原 LVI 优化提交 `599e47ee8b8096695f6c723202573a5c12899520` 已推送到 `origin` 的 `perf/lvi-select-demand-undef`，已通过 `git ls-remote` 核对远程 SHA。
- 已切回 `test/javatype-cache-design`，在 `8df28fa046fd59251be09a065a468c08628dd397` 上补测试。
- 新测试提交：`ea2953f61a852e322848b03354eb97c98ac87bf5`，工作树干净；本测试提交已推送到 `origin/test/javatype-cache-design`。
- 未修改生产查询算法或失效策略；当前分支的 `LazyValueInfo.cpp` 与 cache-design 基线完全一致，不含上一分支的 LVI 优化。

## 测试构造

新增三个单测，以及共享 fixture、原生回放程序、Python 配对脚本和使用说明：

```text
llvm/unittests/IR/JavaTypeCacheReuseTestSupport.h
llvm/unittests/IR/JavaTypeCacheReuseTest.cpp
llvm/unittests/IR/JavaTypeCacheReuseReplay.cpp
llvm/utils/jeandle/replay-java-type-context-cache.py
llvm/docs/JeandleJavaTypeCacheReuse.md
```

fixture 的对象参数没有 `java-klass` 基础属性。类型必须由实际的 `check_instanceof` guard 恢复，经过 32 个 CFG block 后，在 16 个非 entry 上下文处查询。null-edge oracle 使用真实 LVI；预算没有耗尽。诊断中的每次查询均与全新 DT、AssumptionCache、LVI 和 JavaTypeCache 的结果比较。

1. **同块重复查询**：相同 Value、相同 ContextBB 连续查询 16 次；单测还使用同块中的不同指令作为 Context，验证完整缓存键的粒度。
2. **跨块共享前缀**：相同 Value，在 16 个不同 BB 依次查询；每批清空缓存，避免后续批次退化为 Final 命中测试。
3. **查询批次—修改—再查询**：先查询 16 次，修改一条无用户的纯算术指令，再查询 16 次；随后将 guard 的 Klass 从 22 改为 33，再查询 16 次。修改前通知，guard 修改后清空 LVI，结果必须更新为 33。

## 正确性与结构计数

- JavaType 单测：**47/47 通过**，其中新增三个测试。
- 原六组 Jeandle lit：**96/96 通过**。
- 新单测和独立诊断全部通过；格式与 diff 检查通过。

下表为每个诊断批次的实际计数。cold 模式在每次查询前只清空 JavaTypeCache，LVI 可继续复用；full 模式只在修改时全清 JavaTypeCache。

| 场景 | 对照 → 缓存模式的 Final hit/miss | PathFacts hits：对照 → 缓存 | oracle 调用：对照 → 缓存 |
| --- | --- | ---: | ---: |
| 同块重复 | 0/16 → 15/1 | 0 → 0 | **544 → 34** |
| 跨块前缀 | 0/16 → 0/16 | **0 → 15** | **664 → 49** |
| 修改后复用 | 45/3 → 46/2 | 0 → 0 | **102 → 68** |

这三个结果分别说明：

- Final 命中能直接跳过昂贵的上下文路径计算。
- ContextBB 不同导致 Final 全 miss 时，PathFacts 仍然可以显著复用公共前缀。
- 修改后的总体命中率差距可能很小，但昂贵 miss 从三次降到两次，仍有可见收益；相关 guard 修改则必须丢弃旧结果。

oracle 调用数是进入 null-edge oracle 的次数，不是 LVI 内部 solve 次数。PathFacts miss 在这个无环线性 fixture 中反映展开的块事实工作，但没有直接测量 DT 内部节点访问数。

## 三轮计时

固定 CPU 16，随机配对顺序，三个场景 × 两种模式 × 三轮，共 **18 次计时进程**。每进程回放 4096 批。IR 构造不计时；计时关闭额外 oracle 计数和全新参考重算。计入每批缓存清理，修改场景也计入修改和失效成本。

| 场景 | 对照 user 秒，中位数 | 缓存 user 秒，中位数 | 配对 CPU 减少，中位数 |
| --- | ---: | ---: | ---: |
| 同块重复：cold 对 cached | 0.421713 | 0.056075 | **86.70%** |
| 跨块前缀：cold 对 cached | 0.532962 | 0.098154 | **81.58%** |
| 修改后复用：full 对 selective | 0.140325 | 0.117943 | **15.95%** |

这是直接查询 API 的合成机制回放，不是 CHA/CFF 或 JVM 性能结果。cold 的强制清表成本也包含在对照中，因此不能把降幅全部归为 DT 遍历成本。样本较短且只有三轮，结果用于确认复用机制与成本方向，不作生产速度承诺。

## 证据与复现

- [源码补丁](artifacts/context-cache-reuse-2026-10-23/tests.patch)
- [单测日志](artifacts/context-cache-reuse-2026-10-23/unit-tests.log)、[lit 日志](artifacts/context-cache-reuse-2026-10-23/lit-tests.log)
- [结构计数与命令](artifacts/context-cache-reuse-2026-10-23/replay/diagnostics.json)
- [18 次计时与命令](artifacts/context-cache-reuse-2026-10-23/replay/timings.json)、[三轮汇总](artifacts/context-cache-reuse-2026-10-23/replay/summary.json)
- [二进制身份](artifacts/context-cache-reuse-2026-10-23/replay/identity.json)、[提交及远程核对](artifacts/context-cache-reuse-2026-10-23/identity-post.json)
- [完整小型记录包](artifacts/context-cache-reuse-2026-10-23/records.tar.gz)

服务器产物：`/home/annya/playground/jeandle/perf-results/2026-10-23-context-cache-reuse/`。

复现命令（out 使用新的目录）：

```sh
python3 llvm/utils/jeandle/replay-java-type-context-cache.py \
  --binary build/build-ninja-profiling/bin/JavaTypeCacheReuseReplay \
  --out /tmp/java-type-context-reuse --rounds 3 --batches 4096 --cpu 16
```

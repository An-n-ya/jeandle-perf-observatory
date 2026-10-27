# Jeandle Perf Observatory

在本机浏览 JavaType 缓存实验的计时、周期归属、调用栈、源码及采样质量。仅使用 Python 标准库和原生浏览器，无需 npm、数据库或第三方 CDN。

## 启动

在 Jeandle 工作目录运行：

```sh
python3 perf-viewer/server.py --port 8766
```

浏览器打开 <http://127.0.0.1:8766>。按 Ctrl-C 停止。默认端口是 8765；如果已有服务占用，使用 `--port` 指定其他端口。

默认发现相邻 `jeandle-develop-log/artifacts/java-type-perf-*` 与 `context-cache-reuse-*` 目录。也可以显式载入多份同格式实验：

```sh
python3 perf-viewer/server.py --port 8766 \
  --data /path/to/java-type-perf-session1 \
  --data /path/to/java-type-perf-session2
```

每个数据集的目录名必须唯一；支持当前冻结实验的文件格式，不是通用 perf.data 上传器。新增数据集后重启服务。缺少必要文件会报告错误，不用零值替代缺失数据。

服务仅监听 `127.0.0.1`，含 Host、Origin 校验与资源白名单。所有原始数据只读；不连接服务器，不重新执行 perf，也不上传数据。

## 怎样查看

- **实验总览**：六个场景，ORIGIN / FULL / S0 / S1 四策略；十轮计时中位数、硬件计数、校正后的 RSS、互斥周期分解及消费者归属。
- **调用栈探索**：主实验三份合并或单次重复；S1 的五份频率/栈深诊断单独选择。点击图中节点放大，用面包屑返回；搜索函数及 native owner，过滤 JavaType / LVI / invalidate / unknown；查看 Self、Inclusive 和直接调用关系。原始采样记录可直接打开。
- **策略对比**：任选两策略，同时对比百分比、百分点及每轮平均采样 cycles，避免只看占比误判。已保存的 S1 配对 bootstrap 区间也会展示。
- **源码与汇编**：保存时的源码片段、原始行号、SHA-256，以及 poison、LVI select、invalidate 的 perf annotate 原文。
- **采样质量与原始资料**：丢样/节流、栈完整度、未知叶子、诊断对照、修正的调度与 RSS 指标、结构诊断及原始报告。

上方 **Speedscope** 按当前场景、策略与重复导出，三份合并时导出为三个独立 profile，避免把独立运行拼成时间线。诊断记录只在调用栈视图选择诊断后导出；过滤/搜索只影响本站探索，导出包含该记录的全部样本。

## 数据口径

- 仅 `opt` 的 `cpu_atom/cycles/u` 样本进入分母；权重是样本的 event period，**不是样本个数或时间戳差**。
- 图中递归调用按原始顺序保留。函数表 Inclusive 对同一帧每样本最多计一次；不同函数重叠，不可相加。Self 成本之和等于选中范围总周期。
- 帧按 `(inline 名称, native owner, inline 标记)` 区分。native owner 由该次运行的 `_start` 重定位和冻结的 `opt-symbols.gz` 恢复，不插入虚构调用层；没有进程根时不猜基址。未知 libc 符号继续显示 unknown。
- 分类规则冻结自实验的 `attribute-stacks.py`，独立保存于查看器；不执行数据集中的 Python 文件。归属匹配忽略函数参数列表，避免把签名里的 `LazyValueInfo&` 当作实际 LVI 执行。
- 周期分解/策略对比用所选重复合并的 period 占比；总览 KPI 标明逐次占比的中位数，两者可能略有差异。绝对周期对比除以重复数，而不是把三份总和与单份比较。
- Speedscope JSON 使用 `sampled` + 显式 `weights`，单位 `none`，名称标明 cycles-weighted；这些权重不代表 wall time。
- 主实验 8 KiB 栈截断、未知符号、小样本及 profile 顺序等限制在页面保留。原 baseline RSS 和零值 `:u` 调度事件不作为有效资源指标。

## 索引

摘要可以立即访问；首次启动后台顺序扫描 `run-records.tar.gz`，索引 72 份主采样及 5 份诊断。每份主记录的样本数、period 总和与冻结汇总核对后才标记可用。无需解压到工作区或复制服务器上的大体积 perf.data。

派生索引在 `perf-viewer/.cache/`，目录依据归档、符号文件 SHA-256 及解析版本命名，可以停止服务后删除重建。原始资料与 artifact 哈希清单不变。再次启动复用压缩 JSON 索引。

主要只读 API：`/api/datasets`、`/api/overview`、`/api/status`、`/api/profile`、`/api/speedscope`、`/api/raw`、`/api/record`。通过 `dataset` 参数选择数据集，profile 另带 `case`、`mode`、`run`；`run=all` 只合并主实验，不混入诊断。诊断使用 `run=diag:deep-199-32k` 等保存的 tag。

## 验证

```sh
python3 -m unittest discover -s perf-viewer/tests -v
node --check perf-viewer/web/app.js
```

测试包含加权分母与事件过滤、递归去重、签名误归属、Speedscope 周期守恒、全部 72 份主记录与冻结互斥分类精确一致、五份诊断隔离、真实 API、路径白名单与跨站请求拒绝。真实数据测试启动临时回环 HTTP 端口；受限执行环境需允许本地监听。


## 静态构建与部署

当前冻结实验也可以构建为纯静态站点，供 GitHub Pages 托管：

```sh
PYTHONPATH=perf-viewer python3 perf-viewer/build_static.py \
  --data jeandle-develop-log/artifacts/java-type-perf-2026-10-23 \
  --reuse-data jeandle-develop-log/artifacts/context-cache-reuse-2026-10-23 \
  --cross-pass-data jeandle-develop-log/artifacts/2026-10-26-javatype-cross-pass-prod \
  --domain jeandle.annya.work
```

`dist/` 包含预生成的 profile JSON、Speedscope JSON、原始采样记录和 artifact。前端读取静态文件，不需要 Python 服务。原始 perf.data 仍不上传；构建产物只包含实验已保存的调用栈和记录。更新实验后重新构建并发布新的 `dist/`。

`--data` 可省略：省略时构建器不再重建剖析索引，只读取输出目录里已有的 `api/datasets.json`，保留其中的剖析条目，并刷新回放与跨 pass 两组实验。适合已经托管了大体积剖析产物的站点做增量更新（输出目录必须已存在 `api/datasets.json`）。

## 上下文缓存复用数据集

侧栏同时列出原六场景剖析、新三场景 API 回放与新四场景跨 pass 生产性能，共十三个测试入口；点击入口自动切换对应数据集，下拉框仍可单独选择数据集。每个场景均有“测试说明与伪代码”，说明问题、IR/调用形状、变量、失效时机及结果边界。

- `final`：同一非 entry BB 连续 16 次查询；cold 对比 cached，验证 Final 复用。
- `prefix`：16 个不同 BB 共用 32 块路径前缀；两组 Final 均零命中，验证 PathFacts 复用。
- `mutation`：16 次查询 → 无关算术修改 → 16 次查询 → 守卫 22 改 33 → 16 次查询；full 对比 cached，验证选择性失效和 fresh 参考一致性。

仅使用已保存的三轮（18 个计时进程），每进程 4096 批；命中计数来自独立单批诊断。页面列出每轮 CPU/wall 秒数、配对降低率与原始 JSON、补丁、测试日志。载入时检查轮次完整性、重复项、checksum，以及原始秒数与保存摘要一致性。新数据没有 perf profile，不展示虚构的 cycles、IPC 或调用栈。基准清理成本也在计时内；不将微基准加速外推到 JVM。

静态部署仓库 `viewer/` 保存查看器源码，`api/artifacts/context-cache-reuse-2026-10-23/` 保存本次小型原始记录。原始大采样归档仍需从实验目录提供；源码不依赖部署仓库中的派生 profile 反推原始样本。

## 跨 pass 缓存 · 生产流水线性能数据集

第三组数据集 `2026-10-26-javatype-cross-pass-prod`（kind = `cross-pass`）回答的问题是「JavaType 缓存跨 pass 存活，在真实生产流水线下到底省不省时间」。它比较三种缓存生存期策略：

- **ORIGINAL**：关闭 JavaType 缓存，所有查询 bypass。
- **PASS-LOCAL**：每个真实消费者 pass 入口清空缓存。
- **CROSS-PASS**：现状——缓存跨 pass 存活，由失效通知控制。

四个场景对应方案的阶段 C / D / E：

- **端到端计时**（阶段 C）：2 session × 30 个随机配对 block，64 个样本，11 520 行逐轮原始计时；每次比较给出净收益 `1 − 候选总时长 / 基线总时长` 与 10 000 次配对重采样得到的 CI95。
- **复用机制**（阶段 D）：进程内计数器（查询、Final 命中、Base 插入、失效请求、pass-local 清空次数等）、消费者级命中与生命周期断点；附 2999 Hz 全语料采样的绝对成本分解图。
- **JVM 编译成本**（阶段 E）：受控子 JVM（15 block）与正常分层/后台编译（10 block）两组的 CITime，加上 jtreg 功能回归与崩溃 A/B 对照。
- **不利样本与边界**：语料清单与入选规则、两组对照各 64 个样本的全清单，以及测量噪声与未覆盖范围。

**口径约束（页面与代码都强制）**

- 三套测量体系（阶段 C 计时、阶段 D 计数器、阶段 E CITime）互不可加。
- 两个对照百分比（ORIGINAL→CROSS-PASS 与 PASS-LOCAL→CROSS-PASS）互不可加。
- 净收益定义固定为 `1 − 候选 / 基线`，正数代表候选更快；判定由 CI95 是否跨零决定。
- CITime 是 elapsed 时间，不是线程 CPU 时间；JVM-PRODUCTION 组三个模式的编译任务集不同，百分比被编译次数差混淆，只能当量级参考。
- 语料是 6 个合成程序，不是真实生产负载；不把占比下降直接解释为加速，也不把阶段 C 的结果外推为 JVM 加速。

该数据集**没有 perf 采样栈**，因此页面不展示调用栈、cycles 占比或 Speedscope 导出，也不展示任何虚构的采样数据；原始 `perf.data` 保留在服务器上不随站点发布。载入时（`viewer/perfview/crosspass.py`）会逐项交叉校验：净收益与总时长一致、判定与 bootstrap 区间一致、计数器合计与 trace 一致、消费者计数求和等于总数、逐样本净收益自洽、JVM net gain 自洽、jtreg 结果为 PASS。任何一项不符即拒绝发布。

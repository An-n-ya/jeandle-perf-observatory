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
  --domain jeandle.annya.work
```

`dist/` 包含预生成的 profile JSON、Speedscope JSON、原始采样记录和 artifact。前端读取静态文件，不需要 Python 服务。原始 perf.data 仍不上传；构建产物只包含实验已保存的调用栈和记录。更新实验后重新构建并发布新的 `dist/`。

## 上下文缓存复用数据集

侧栏同时列出原六场景剖析与新三场景 API 回放，共九个测试入口；点击入口自动切换对应数据集，下拉框仍可单独选择数据集。每个场景均有“测试说明与伪代码”，说明问题、IR/调用形状、变量、失效时机及结果边界。

- `final`：同一非 entry BB 连续 16 次查询；cold 对比 cached，验证 Final 复用。
- `prefix`：16 个不同 BB 共用 32 块路径前缀；两组 Final 均零命中，验证 PathFacts 复用。
- `mutation`：16 次查询 → 无关算术修改 → 16 次查询 → 守卫 22 改 33 → 16 次查询；full 对比 cached，验证选择性失效和 fresh 参考一致性。

仅使用已保存的三轮（18 个计时进程），每进程 4096 批；命中计数来自独立单批诊断。页面列出每轮 CPU/wall 秒数、配对降低率与原始 JSON、补丁、测试日志。载入时检查轮次完整性、重复项、checksum，以及原始秒数与保存摘要一致性。新数据没有 perf profile，不展示虚构的 cycles、IPC 或调用栈。基准清理成本也在计时内；不将微基准加速外推到 JVM。

静态部署仓库 `viewer/` 保存查看器源码，`api/artifacts/context-cache-reuse-2026-10-23/` 保存本次小型原始记录。原始大采样归档仍需从实验目录提供；源码不依赖部署仓库中的派生 profile 反推原始样本。

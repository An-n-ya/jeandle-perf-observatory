# 验证记录 · 2026-10-23

数据集：`java-type-perf-2026-10-23`。服务地址：<http://127.0.0.1:8766>。

- `python3 -m unittest discover -s perf-viewer/tests -v`：8 项测试全部通过。
- `node --check perf-viewer/web/app.js`：通过。
- 索引：72 份主采样 + 5 份诊断，全部可用。
- 主采样核对：逐份样本数、event period 总和、JavaType 加权占比与冻结摘要一致；所有互斥分类的周期数与 `attribution.csv` 精确一致。
- Speedscope：三次运行分成三个 profile；每个 profile 的权重之和等于 endValue，所有 profile 的周期总和等于合并调用栈周期。
- 原始资料：重新计算 `artifact-sha256.json` 所列 63 个文件的大小与 SHA-256，全部一致。查看器未修改冻结实验资料。
- 本地浏览器实测：总览、ORIGIN / FULL / S0 / S1 切换、跨场景切换、单次/合并重复、策略对比和配对置信区间、源码与汇编切换、采样质量与原始链接均可用。
- 调用栈实测：函数搜索、JavaType 过滤、函数选择与直接调用关系、32 KiB 诊断加载、图形点击放大、面包屑及重置缩放均可用；ORIGIN 的失效样本过滤显示空结果提示。
- 浏览器未记录 JavaScript error；已检查页面没有 NaN / undefined / Infinity 数值。
- 接口验证：真实 profile、gzip 响应、Speedscope、源码与原始采样记录读取；非法数据选择、路径穿越、外部 Host 与跨站 Origin 均被拒绝。

启动不需要第三方依赖。首次后台索引，后续复用约 3.9 MiB 的派生缓存。服务生命周期由启动它的终端进程管理；不注册系统常驻任务。

## 上下文缓存复用扩展

- `python3 -m unittest discover -s perf-viewer/tests -v`：10 项通过，包含原 8 项与新增回放完整性/损坏数据拒绝测试。
- 三轮、4096 批、18 个计时进程，检查唯一的 (scenario, mode, round)、checksum 与诊断批次的比例；重新计算三轮摘要及每轮配对降低率。
- `node --check perf-viewer/web/app.js` 通过。静态构建保留 101 份 profile、385 份记录、101 份 Speedscope；新数据不生成 perf profile。
- 本地 API 版浏览器：原六场景与新三场景切换、prefix 的 81.58% 及伪代码、隐藏不适用的采样控件；新数据原始 timings API 返回 18 条记录。
- 本次没有重新运行 LLVM 性能实验，使用先前完成的三轮与 47/47 单测、96/96 lit 原始记录。
- 静态版浏览器：九个场景伪代码检查通过；mutation 显示 15.95%；新数据 10 个原始链接全部 HTTP 200；CFF 原始记录五种文件及 Speedscope 全部 HTTP 200；新结果页没有 NaN / undefined / Infinity。
- 远程核对：`origin/test/javatype-cache-design` 为 `ea2953f61a852e322848b03354eb97c98ac87bf5`。
- 九入口侧栏：浏览器检查共 9 个按钮，逐一点击跨数据集加载与伪代码均通过；回到 deep-static 后原 S1 user 中位数 5.7674575 秒保留。原 101 profile、385 record、101 export 文件未改动。

## 跨 pass 生产性能扩展 · 2026-10-26

数据集：`2026-10-26-javatype-cross-pass-prod`（kind = `cross-pass`）。静态站点地址 <https://jeandle.annya.work>，本地验证服务 <http://127.0.0.1:8791>。

- `python3 -m unittest discover -s viewer/tests -v`：24 项，17 项通过、7 项因冻结源数据不在本机而跳过（含原剖析与回放数据集的既有测试）。新增 `viewer/tests/test_crosspass.py` 覆盖形状、目录条目、计时自洽、计数器求和、语料覆盖、JVM 与 jtreg、artifact 可读与路径穿越拒绝，以及 6 项损坏数据必须被拒绝（缺文件、净收益错位、判定与 bootstrap 不符、计数器不符、逐样本净收益错位、JVM net gain 错位、jtreg 非 PASS）。
- `node --check viewer/web/app.js`：通过。
- 数据自洽（载入时强制）：60 block / 2 session / 64 样本 / 11 520 行；净收益 = 1 − 候选/基线；CI95 内含均值；判定与 bootstrap 区间及跨零标志一致；计数器与 trace 一致；消费者计数求和 = 总数（queries 173、base insertions 100、final hits 68、final misses 110）；语料 64 接受 + 12 拒绝 = 76 录制；逐样本净收益自洽且与负样本清单一致；JVM 受控 15 block / 生产 10 block 且每指标覆盖全部 block；jtreg `Passed. Execution successful`、`passed: 1`。
- 静态构建：`python3 viewer/build_static.py --out /tmp/staging --cross-pass-data <数据目录>`（无 `--data`，增量发布，保留既有剖析条目）。产出 `api/experiments/2026-10-26-javatype-cross-pass-prod/{overview,status}.json`、`api/artifacts/2026-10-26-javatype-cross-pass-prod/` 下 36 个原始文件，以及根目录 `index.html` / `app.js` / `style.css` 和 `api/datasets.json`。
- 本地无头浏览器实测（Chromium headless，1600×1100 与全页长图）：跨 pass 的 4 个场景 × 3 个 tab 共 12 个视图全部渲染，无 NaN / undefined / Infinity / 空内容，控制台无 JavaScript error；38 处 CI95 与判定标签逐行重算一致；`cost_decomposition.svg` 图正常绘出（含图例），不是破图。
- 另两组数据集回归：profiling 的 `deep-static`、`cff-cache-reuse` 与 context-reuse 的 `final`、`mutation` 均正常渲染，数值无异常。
- 侧栏共 13 个入口，分三组（原有 · 性能剖析 6、新增 · 缓存复用 3、新增 · 跨 pass 生产性能 4）；跨 pass 四项使用中文标题与阶段副标题；隐藏不适用的采样范围与 Speedscope 导出控件。
- 本次没有重新运行 LLVM 性能实验，使用 2026-10-26 已完成的阶段 C / D / E 冻结记录；原始 `perf.data` 仍保留在服务器上，未随站点发布。

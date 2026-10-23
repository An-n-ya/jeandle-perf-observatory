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

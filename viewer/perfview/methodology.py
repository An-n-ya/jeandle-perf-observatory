"""Human-readable protocols tied to the frozen experiments, not current code."""
def case(question, setup, pseudocode, features, interpretation, notes=None):
    return dict(question=question, setup=setup, pseudocode=pseudocode,
                features=features, interpretation=interpretation, notes=notes or [])

STATIC = '''# 每个函数的 IR 形状（示意）
v = arg_a
repeat SELECT_DEPTH:
    v = select(same_condition, v, arg_b)
repeat CALL_SITES:
    invoke _linkToStatic(v) -> next_basic_block
# a/b 都带 java-klass=22；每个 invoke 位于不同 BB
# CHA 改写调用后通知缓存失效，LVI 也会被清理'''
ORIGINAL = {
'deep-static': case('深层 select 的类型查询成本在哪里？Base 缓存能覆盖多少？',
'8192 个独立函数；64 层 select；每函数 16 个静态 invoke；运行 CHA。',
STATIC.replace('SELECT_DEPTH','64').replace('CALL_SITES','16'),
['同一 SSA Value 被重复查询，但 ContextBB 随调用点改变，FinalTypes 的键并不相同。',
 '反复使用同一个条件的 select 会放大 LVI / poison / undef 判断成本；代表刻意放大的编译器微基准。',
 '调用改写触发上下文失效，因此不能把 Final 零命中简单解释成实现无效。'],
'主要观察 Base DAG 复用、LVI 查询与失效开销；不能单独证明 DT 路径缓存的收益。'),
'wide-static': case('调用点增多时，类型查询和上下文失效成本如何变化？',
'8192 个独立函数；16 层 select；每函数 64 个静态 invoke；运行 CHA。',
STATIC.replace('SELECT_DEPTH','16').replace('CALL_SITES','64'),
['比 deep 更浅的 Value DAG、更长的调用点链，增加查询次数与路径长度。',
 '同一 V、不同 BB，且每次改写失效；不是“同一缓存键查询 64 次”。'],
'用于比较查询密度及失效压力；与 deep 的差异同时包含 select 深度和调用数，不能当作单变量实验。'),
'leaf-static': case('几乎没有 Base DAG 工作时，缓存本身是否引入开销？',
'8192 个独立函数；0 层 select；32 个静态 invoke；类型直接来自参数 java-klass=22。',
STATIC.replace('SELECT_DEPTH','0').replace('CALL_SITES','32'),
['叶子值控制组：削弱 Base DAG 遍历成本，突出容器查找、LVI 与失效固定成本。',
 '仍然有不同调用 BB 和改写通知，并不等于完全没有上下文查询。'],
'缓存可能因查表及维护成本变慢；不能把本例结果推广到昂贵的 DT 路径查询。'),
'tce-cha': case('两个 pass 连续消费类型信息时，缓存实际能留下什么？',
'8192 个函数；64 层 select、16 个静态 invoke，额外 check_instanceof(22)；顺序执行 TCE → CHA，每函数约 17 次查询。',
'''v = select_chain(depth=64, typed_args=22)
check_instanceof(v, klass=22)
repeat 16: invoke _linkToStatic(v) -> next_BB
run TypeCheckElimination  # 删除冗余 check，通知失效
run ClassHierarchyAnalysis  # 查询并改写调用''',
['测试 pass 串联与类型检查消除带来的失效。',
 '冗余检查被删除会改变可用事实；跨 pass 不自动等价于同键 Final 命中。'],
'关注消费者分布和失效处理；不能据此断言已测得跨 pass FinalTypes 复用收益。'),
'virtual-cfg': case('虚调用改写与 CFG 更新的成本如何影响缓存？',
'8192 个函数；0 层 select、32 个虚调用 invoke；CHA 插入推测性类型守卫、空值检查并更新 CFG。',
'''v = typed_argument(klass=22)
repeat 32: invoke virtual_method(v) -> next_BB
run CHA:
    build speculative_guard_and_null_check()
    rewrite_call_and_CFG()
    update_DT(); clear_LVI(); notify_cache()''',
['结构变化比静态调用测试更强，包含 DT 维护、CFG 修改与分析失效成本。',
 '外部 DT 更新开销与 getJavaType 内遍历支配树是不同来源，需结合调用栈区分。'],
'这是 CFG 改写压力测试，不能把全部 DT 采样都归为类型查询。'),
'cff-cache-reuse': case('出现 Final 命中时，是否真的省下了昂贵的路径遍历？',
'262144 个独立函数；entry 中 4 个调用，2 个 load_klass 可折叠，2 个 get_classmirror 不可折叠；CFF 迭代。',
'''entry:
    c0 = load_klass(v); c1 = load_klass(v)
    c2 = get_classmirror(v); c3 = get_classmirror(v)
round_1: query c0 -> miss; fold/delete; invalidate
         query c1 -> miss; fold/delete; invalidate
         query c2 -> miss; keep
         query c3 -> hit; keep
round_2: query c2 -> hit; query c3 -> hit
# 6 次查询中有 3 次 Final hit''',
['本例是正向命中控制组，独立小诊断 8 函数为 48 次查询、24 次 Final hit。',
 'Context 是 entry，PathFacts 早返回，没有昂贵的支配路径；高命中率不等于高收益。'],
'证明 Final 复用路径可达，不能作为降低 DT 路径查询成本的证据。')}

REUSE = {
'final': case('完全相同的 (canonical V, ContextBB) 重复查询，能否跳过整条类型推导路径？',
'V 无 java-klass 属性；真实 check_instanceof(v,22) 守卫；经过 32 个 CFG 块，在同一个非 entry BB 查询 16 次。',
'''for batch in 4096:
    cache.clear()
    for i in 0..15:
        if mode == cold: cache.clear()  # 只清 JavaTypeCache
        result = getJavaType(v, same_context_BB)
        consume(result)  # 期待 klass=22''',
['cached 每批 1 次 miss、15 次 Final hit；cold 每次 miss。',
 '同一 BB 内不同指令 Context 的等价性另有单元测试覆盖。',
 '冷基线只清 JavaTypeCache，LVI 可以变暖；包含 clear 成本，不是纯 DT 遍历耗时。'],
'诊断中 oracle 544→34，说明 Final 命中跳过了后续路径；这提供缓存降低查询成本的直接证据。'),
'prefix': case('ContextBB 不同、Final 始终 miss 时，能否复用支配路径公共前缀？',
'相同的真实类型守卫与 32 块前缀；同一个 V 在 16 个连续、不同的非 entry BB 查询；查询之间无改写。',
'''for batch in 4096:
    cache.clear()  # 防止下一批直接 Final hit
    for context in 16_distinct_BBs_after_32_block_prefix:
        if mode == cold: cache.clear()
        result = getJavaType(v, context)
        consume(result)  # 期待 klass=22''',
['两种模式都是 Final 0 hit / 16 miss，控制 Final 复用的干扰。',
 'cached 出现 15 次 PathFacts hit，facts misses 从 664 降到 49。',
 'facts miss 统计不能直接等同内部 DT 访问节点数；oracle 调用次数也不是 LVI 实际求解次数。'],
'Final 零命中仍可显著受益：公共路径事实被复用；原调用改写测试破坏了这项复用机会。'),
'mutation': case('无关修改保留缓存、相关修改使其失效，能否同时保证收益与正确性？',
'同一非 entry Context，三个阶段各查询 16 次；先改无关纯算术指令，再将类型守卫 klass 22 改为 33。',
'''for batch in 4096:
    restore_guard(22); reset_analyses_and_cache()
    query_same_context(16)  # 22
    notify_before_edit(unrelated_arithmetic)
    edit_unused_arithmetic_operand()
    query_same_context(16)  # 22，cached 保留；full 已清空
    notify_before_edit(type_guard)
    change_guard_klass(22, 33); LVI.clear()
    query_same_context(16)  # 必须为 33
# full: 每次修改都清空 JavaTypeCache
# cached: 使用选择性失效；二者在查询之间都保留缓存''',
['full 不是每次查询冷启动：每批 45 hit / 3 miss；cached 为 46 hit / 2 miss。',
 '通知发生于真实 IR 修改之前；相关修改后强制清 LVI，防止其旧事实掩盖缓存错误。',
 '每条诊断查询都与新建 DT/AC/LVI/JavaTypeCache 的参考结果比较；单元测试额外覆盖 Context 细节。'],
'无关修改可少一次重建，相关修改仍得到 33；收益来自减少失效，并非复用已经过期的事实。')}

CROSSPASS = {
'timing': case('让 JavaType 缓存跨 pass 存活，在真实优化流水线上到底快不快？',
 '固定语料 64 个 root method（6 个合成程序）。每个样本单独起一个 opt 子进程跑完整 jeandle<O3>；'
 '2 个独立 session × 30 个随机配对 block = 60 个配对 block，block 内样本顺序与模式顺序都随机。'
 '另测同命令的 no-op 基线（不带 pipeline）用于扣除启动与 IR 解析。',
 '''for block in 60:                     # 2 sessions x 30 blocks
    order = shuffle(samples x modes)  # 样本顺序、模式顺序都随机
    for sample, mode in order:
        opt -disable-output -disable-verify \\
            -passes=jeandle<O3> <mode flag> <sample.ll>
        measure wait4 rusage -> user+sys cpu, wall
    net_benefit = 1 - sum(candidate_s) / sum(baseline_s)
    ci95 = bootstrap(paired blocks, 10000 resamples)

mode flags:
  original    -jeandle-disable-java-type-cache   # 关闭缓存，全部 bypass
  pass_local  -jeandle-java-type-pass-local      # 每个消费者 pass 入口清缓存
  cross_pass  (无)                                # 缓存跨 pass 存活''',
 ['唯一变量是缓存生存期策略；未混入新的 preserve 实现，也未改 LVI 优化。',
  '计时口径是子进程 wait4 的 user+sys CPU（含启动与解析）与墙钟，不是单次查询延迟。',
  '每样本单独起进程，因此单样本 CPU 仅约 0.023 s，固定开销占比高；已另测 no-op 基线做扣除对照。',
  '两套指标（"含启动" 与 "扣 no-op"）来自同一次实验，结论同号同量级。'],
 'ORIGINAL→CROSS-PASS 的置信区间跨零，说明当前生产配置下没有测出稳定净收益。'
 'PASS-LOCAL→CROSS-PASS 的区间不含 0 但方向为负，说明"每 pass 清空"目前反而更快。'
 '这两个百分比是两次独立对照，不可相加。'),
'mechanism': case('如果跨 pass 保留确实在复用缓存，机制层面能看到吗？',
 '同一语料、同一 64 个样本，在进程内计数器与 pass invocation 生命周期统计上重复采集 10 轮，'
 '同时做全语料 2999 Hz 采样做绝对成本分解。',
 '''counters (per corpus round, 64 samples x 10 repeat):
    queries, bypasses
    base insertions        # Base 层重算次数
    final type hits/misses # Final 层命中（跨 pass 复用）
    path facts hits/misses
    invalidation requests / selective invalidations
    pass-local cache clears
    total query time (ns) / total invalidation time (ns)

pass invocation timeline (per pass):
    dropped                 # 分析被丢弃
    dropped_with_entries    # 丢弃时缓存里仍有条目  <- 跨 pass 存活的断点
    self_preserved''',
 ['计数器是进程内直接统计，不是 perf 采样推导；计时进程关闭 trace/stats，诊断单独跑。',
  '生命周期统计三种模式完全一致：跨 pass 保留没有改变哪些 pass 会丢弃分析，'
  '只改变了丢弃那一刻缓存里还有没有条目。',
  '绝对成本分解基于 2999 Hz 全语料采样，与阶段 C 的子进程计时是两套独立测量，不能相加。'],
 '机制成立：Final 层命中从 0 升到 68/语料轮，Base 层重算少 68 次，失效请求从 13186 降到 32。'
 '但存活下来的条目大多在 JavaOperationLower 处被丢弃，无法被下游消费者吃到——'
 '这正是"机制成立却没有净收益"的原因。'),
'jvm': case('在真实 JVM 编译里，跨 pass 缓存能省下编译时间吗？',
 '两组独立测量。JVM-CONTROLLED：单编译线程、compileonly 指定负载、15 个随机配对 block；'
 'JVM-PRODUCTION：默认分层 + 后台编译、10 个随机配对 block。另跑 jtreg 功能回归。',
 '''controlled:
    java -Xbatch -XX:-TieredCompilation -XX:CICompilerCount=1
         -XX:+CITime -XX:+UseJeandleCompiler
         -XX:CompileCommand=compileonly,Workload::typeCheckHeavy
    (每个 block 每模式恰好 1 次 Jeandle 编译 -> 可配对)

production:
    java (默认分层编译 + 后台编译线程)

metrics from CITime:
    total compile cost / Jeandle compile time
    LLVM Optimize / LLVM CodeGen
    application time / process wall clock''',
 ['CITime 输出的是 elapsed 时间，不是线程 CPU 时间；后台并发编译时只能当量级参考。',
  'JVM-PRODUCTION 组三个模式的编译任务集不同（Jeandle 编译次数 mean 20.5 / 21.0 / 20.0），'
  '其百分比被任务集差异混淆。',
  '测试里不含任何时间断言，只断言功能行为与 argv 透传。'],
 '两组、每组三个主指标（LLVM Optimize / 总编译成本 / 应用时间）分开看都没有稳定差异：'
 'CONTROLLED 全部跨零，PRODUCTION 的 positive 结果与编译次数差同量级，归一化后落到噪声级。'
 '阶段 E 与阶段 C 是两套测量体系，数字不可相加，只能做方向性互证。'),
'limits': case('这个结论有多可信？哪些地方不能外推？',
 '保留全部不利样本、拒绝样本与崩溃对照，不做筛选。',
 '''negative samples:
    per-sample net benefit for all 64 accepted samples, both comparisons
    (57.8% / 56.2% of samples are negative)

rejected samples:
    12 of 76 recorded root methods rejected, all with the same reason

crash A/B control:
    baseline_head (clean HEAD)  vs current_worktree (with this change)
    rounds / javac failures / jimage failures''',
 ['不利样本全部保留并逐条列出；查询数最高的样本往往最不利，与"查询越多、维护与失效开销越大"一致。',
  '12 个拒绝样本全部是既有的 replay 崩溃（exit -6），与本改动无关；A/B 对照显示崩溃率相同。',
  '单样本分辨率约 ±1 %，只能判定语料整体方向，不能判定单方法方向。'],
 '结论可用于"当前生产流水线配置下没有测出稳定净收益"这一层；'
 '不能外推为 JVM 应用吞吐加速，也不能外推到真实应用负载、'
 '泛型/record/lambda 等未覆盖语言特性，或逐 pass 消融的归因。',
 notes=['测量噪声：短进程固定开销占比高（启动 + IR 解析约 0.022 s，而单样本 CPU 仅约 0.023 s），'
        '已用 no-op 基线扣除后复算，结论不变。',
        'CPU 频率策略为 powersave，存在频率爬升噪声；用 2 个独立 session + 随机配对 block 抵消系统性偏置，'
        '但无法完全消除。',
        '配对 block 内仍有顺序效应：尽管模式顺序随机，长时间连续运行仍可能残留热状态。',
        'JVM-PRODUCTION 组三个模式的编译任务集不同，其百分比被编译次数差混淆。',
        'CITime 是 elapsed 而非线程 CPU。',
        '未覆盖：泛型擦除、接口默认方法、record/sealed、lambda 与 method handle 链、数组协变、'
        '层次较深的类；只测了完整 jeandle<O3>，未做逐 pass 消融；语料是 6 个合成程序的 64 个 root method，'
        '不是真实应用负载；JVM 侧多线程编译的精确成本未覆盖。'])}

CROSSPASS_PROTOCOL = '''跨 pass 生产流水线性能测试，三种模式（original 关闭缓存 / pass_local 每 pass 清空 / cross_pass 现状跨 pass 存活）对照。阶段 C 是 opt 子进程语料回放的生命周期 CPU/墙钟计时（2 session × 30 随机配对 block，bootstrap CI95 10000 次重采样）；阶段 D 是进程内计数器、pass invocation 生命周期统计与 2999 Hz 绝对成本分解；阶段 E 是 JVM-CONTROLLED（15 block）与 JVM-PRODUCTION（10 block）的 CITime 编译成本，外加 jtreg 功能回归。三者是不同测量体系，数字不可相加。ORIGINAL→CROSS-PASS 与 PASS-LOCAL→CROSS-PASS 是两次独立对照，百分比也不可相加。净收益一律为 1 - 候选/基线：正值代表候选更快。CITime 是 elapsed 而非线程 CPU，并发编译下只作量级参考。JVM-PRODUCTION 组三模式编译任务集不同，其百分比被编译次数差混淆。计时进程与诊断进程分开运行，计时期间关闭 trace/stats。语料是 6 个合成程序的 64 个 root method，不是真实应用负载；本轮未引入任何新的 preserve 实现，也未改 LVI 优化，唯一变量是缓存生存期策略。不把占比下降直接解释为加速，不把负收益样本或拒绝样本隐藏，不外推为 JVM 加速。'''

PROTOCOL = '''三类新测试均直接调用 JavaTypeCache API，使用真实 LVINullEdgeOracle 与合成类层次；不是完整优化 pass 或 JVM 应用。CPU 16，seed=20261023，每场景两种模式配对随机排序，3 轮，共 18 个计时进程；每进程 4096 批。原生计时排除 fixture 构造，覆盖查询循环、批间清理及 mutation 的修改/失效；计时禁用 oracle 计数与 fresh 参考检查。命中诊断另跑 1 批，每次查询对照 fresh DT/AC/LVI/cache。计时与诊断不能混作同一次测量。CPU 降低率逐轮计算 (baseline-cached)/baseline，再取三轮中位数；秒数分别取三轮中位数。只有三轮且运行很短，不给置信区间，也不外推为生产环境加速。代码基于 cache-design，未混入 LVI 优化分支。验证记录：JavaType 单元测试 47/47、六组 lit 测试 96/96。'''

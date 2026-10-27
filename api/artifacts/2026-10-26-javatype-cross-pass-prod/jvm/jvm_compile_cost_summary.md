# 阶段 E：JVM 子进程受控编译成本测量

## 组别 group: controlled

- 随机配对 block 数: 15，seed: 20261026，rounds: 100000
- block 内模式顺序（随机）: pass_local cross_pass original; pass_local original cross_pass; original cross_pass pass_local; pass_local original cross_pass; cross_pass pass_local original; original pass_local cross_pass; original cross_pass pass_local; cross_pass pass_local original; original cross_pass pass_local; original pass_local cross_pass; pass_local cross_pass original; original cross_pass pass_local; pass_local original cross_pass; cross_pass original pass_local; original cross_pass pass_local
- 子进程实际 argv 与 CITime 原始输出: `jvm/citime/controlled/<mode>_b<block>.txt`
- 失败样本: 3 次（见 JSON 的 failures 字段与 `jvm/citime/controlled/crash_*.txt`）

### 每次运行的编译次数

| 模式 | Jeandle 编译次数 mean | min | max |
|---|---|---|---|
| original | 1.0 | 1 | 1 |
| pass_local | 1.0 | 1 | 1 |
| cross_pass | 1.0 | 1 | 1 |

### 三项指标分开（绝对值，均值 over blocks）

#### total compile cost

| 模式 | mean | median | sd |
|---|---|---|---|
| original | 0.1905 | 0.1900 | 0.00401 |
| pass_local | 0.1918 | 0.1900 | 0.00793 |
| cross_pass | 0.1903 | 0.1900 | 0.00265 |

#### Jeandle compile time

| 模式 | mean | median | sd |
|---|---|---|---|
| original | 0.1899 | 0.1890 | 0.00394 |
| pass_local | 0.1915 | 0.1890 | 0.00802 |
| cross_pass | 0.1897 | 0.1890 | 0.00277 |

#### LLVM Optimize

| 模式 | mean | median | sd |
|---|---|---|---|
| original | 0.1294 | 0.1290 | 0.00150 |
| pass_local | 0.1310 | 0.1290 | 0.00621 |
| cross_pass | 0.1295 | 0.1290 | 0.00228 |

#### LLVM CodeGen

| 模式 | mean | median | sd |
|---|---|---|---|
| original | 0.0599 | 0.0590 | 0.00260 |
| pass_local | 0.0597 | 0.0590 | 0.00202 |
| cross_pass | 0.0594 | 0.0600 | 0.00136 |

#### application time

| 模式 | mean | median | sd |
|---|---|---|---|
| original | 1.9399 | 1.9325 | 0.02455 |
| pass_local | 1.9432 | 1.9351 | 0.02507 |
| cross_pass | 1.9512 | 1.9438 | 0.02698 |

#### process wall clock

| 模式 | mean | median | sd |
|---|---|---|---|
| original | 1.9750 | 1.9656 | 0.02501 |
| pass_local | 1.9771 | 1.9694 | 0.02475 |
| cross_pass | 1.9855 | 1.9770 | 0.02741 |

### 按编译次数归一化后的每次编译成本

| 模式 | 每次编译的总编译成本(s) | 每次编译的 LLVM Optimize(s) |
|---|---|---|
| original | 0.1905 | 0.1294 |
| pass_local | 0.1918 | 0.1310 |
| cross_pass | 0.1903 | 0.1295 |

### 配对比较（net = 1 - sum(candidate)/sum(baseline)，95% CI 由配对 block 重采样得到）

| 对照 | 指标 | 基线总时长(s) | 候选总时长(s) | net | CI95 |
|---|---|---|---|---|---|
| original->cross_pass | total compile cost | 2.858 | 2.855 | +0.10% | [-1.17%, +1.59%] |
| original->cross_pass | Jeandle compile time | 2.849 | 2.846 | +0.11% | [-1.20%, +1.60%] |
| original->cross_pass | LLVM Optimize | 1.941 | 1.942 | -0.05% | [-1.09%, +1.03%] |
| original->cross_pass | LLVM CodeGen | 0.898 | 0.891 | +0.78% | [-1.94%, +3.90%] |
| original->cross_pass | application time | 29.099 | 29.269 | -0.58% | [-1.44%, +0.30%] |
| original->cross_pass | process wall clock | 29.625 | 29.783 | -0.53% | [-1.40%, +0.36%] |
| pass_local->cross_pass | total compile cost | 2.877 | 2.855 | +0.76% | [-1.20%, +3.51%] |
| pass_local->cross_pass | Jeandle compile time | 2.873 | 2.846 | +0.94% | [-1.02%, +3.67%] |
| pass_local->cross_pass | LLVM Optimize | 1.965 | 1.942 | +1.17% | [-1.04%, +4.26%] |
| pass_local->cross_pass | LLVM CodeGen | 0.895 | 0.891 | +0.45% | [-1.59%, +2.75%] |
| pass_local->cross_pass | application time | 29.148 | 29.269 | -0.41% | [-1.53%, +0.63%] |
| pass_local->cross_pass | process wall clock | 29.656 | 29.783 | -0.43% | [-1.54%, +0.61%] |

### 编译事件核对（额外的 -XX:+PrintCompilation 运行，不计入计时）

| 模式 | Jeandle 编译次数 | 编译方法总数 | C2 标准编译(s) | deopt 次数 |
|---|---|---|---|---|
| cross_pass | 1 | 0 | n/a | 0 |
| original | 1 | 0 | n/a | 0 |
| pass_local | 1 | 0 | n/a | 0 |


## 组别 group: production

- 随机配对 block 数: 10，seed: 20261026，rounds: 100000
- block 内模式顺序（随机）: pass_local cross_pass original; pass_local original cross_pass; original cross_pass pass_local; pass_local original cross_pass; cross_pass pass_local original; original pass_local cross_pass; original cross_pass pass_local; cross_pass pass_local original; original cross_pass pass_local; original pass_local cross_pass
- 子进程实际 argv 与 CITime 原始输出: `jvm/citime/production/<mode>_b<block>.txt`
- 失败样本: 4 次（见 JSON 的 failures 字段与 `jvm/citime/production/crash_*.txt`）

### 每次运行的编译次数

| 模式 | Jeandle 编译次数 mean | min | max |
|---|---|---|---|
| original | 20.5 | 19 | 21 |
| pass_local | 21.0 | 19 | 22 |
| cross_pass | 20.0 | 18 | 21 |

### 三项指标分开（绝对值，均值 over blocks）

#### total compile cost

| 模式 | mean | median | sd |
|---|---|---|---|
| original | 0.6278 | 0.6365 | 0.03480 |
| pass_local | 0.6672 | 0.6690 | 0.02083 |
| cross_pass | 0.6194 | 0.6095 | 0.02759 |

#### Jeandle compile time

| 模式 | mean | median | sd |
|---|---|---|---|
| original | 0.6102 | 0.6190 | 0.03446 |
| pass_local | 0.6484 | 0.6490 | 0.02100 |
| cross_pass | 0.6020 | 0.5935 | 0.02752 |

#### LLVM Optimize

| 模式 | mean | median | sd |
|---|---|---|---|
| original | 0.5248 | 0.5240 | 0.02269 |
| pass_local | 0.5464 | 0.5460 | 0.02186 |
| cross_pass | 0.5300 | 0.5365 | 0.02818 |

#### LLVM CodeGen

| 模式 | mean | median | sd |
|---|---|---|---|
| original | 0.0775 | 0.0770 | 0.00530 |
| pass_local | 0.0812 | 0.0790 | 0.00538 |
| cross_pass | 0.0730 | 0.0745 | 0.00648 |

#### application time

| 模式 | mean | median | sd |
|---|---|---|---|
| original | 0.1154 | 0.1150 | 0.00584 |
| pass_local | 0.1205 | 0.1203 | 0.00734 |
| cross_pass | 0.1131 | 0.1120 | 0.00388 |

#### process wall clock

| 模式 | mean | median | sd |
|---|---|---|---|
| original | 0.1875 | 0.1707 | 0.03431 |
| pass_local | 0.2082 | 0.1775 | 0.04560 |
| cross_pass | 0.1814 | 0.1760 | 0.02608 |

### 按编译次数归一化后的每次编译成本

| 模式 | 每次编译的总编译成本(s) | 每次编译的 LLVM Optimize(s) |
|---|---|---|
| original | 0.0306 | 0.0256 |
| pass_local | 0.0318 | 0.0261 |
| cross_pass | 0.0310 | 0.0266 |

### 配对比较（net = 1 - sum(candidate)/sum(baseline)，95% CI 由配对 block 重采样得到）

| 对照 | 指标 | 基线总时长(s) | 候选总时长(s) | net | CI95 |
|---|---|---|---|---|---|
| original->cross_pass | total compile cost | 6.278 | 6.194 | +1.34% | [-2.55%, +4.80%] |
| original->cross_pass | Jeandle compile time | 6.102 | 6.020 | +1.34% | [-2.64%, +4.88%] |
| original->cross_pass | LLVM Optimize | 5.248 | 5.300 | -0.99% | [-5.60%, +3.14%] |
| original->cross_pass | LLVM CodeGen | 0.775 | 0.730 | +5.81% | [+1.04%, +10.66%] |
| original->cross_pass | application time | 1.154 | 1.131 | +2.00% | [-1.41%, +5.24%] |
| original->cross_pass | process wall clock | 1.875 | 1.814 | +3.22% | [-3.68%, +12.21%] |
| pass_local->cross_pass | total compile cost | 6.672 | 6.194 | +7.16% | [+3.58%, +10.43%] |
| pass_local->cross_pass | Jeandle compile time | 6.484 | 6.020 | +7.16% | [+3.49%, +10.51%] |
| pass_local->cross_pass | LLVM Optimize | 5.464 | 5.300 | +3.00% | [-0.71%, +7.18%] |
| pass_local->cross_pass | LLVM CodeGen | 0.812 | 0.730 | +10.10% | [+4.22%, +15.70%] |
| pass_local->cross_pass | application time | 1.205 | 1.131 | +6.12% | [+2.09%, +10.52%] |
| pass_local->cross_pass | process wall clock | 2.082 | 1.814 | +12.87% | [-6.07%, +27.15%] |

### 编译事件核对（额外的 -XX:+PrintCompilation 运行，不计入计时）

| 模式 | Jeandle 编译次数 | 编译方法总数 | C2 标准编译(s) | deopt 次数 |
|---|---|---|---|---|
| cross_pass | 22 | 127 | n/a | 27 |
| original | 0 | None | n/a | 21 |
| pass_local | 23 | 128 | n/a | 28 |


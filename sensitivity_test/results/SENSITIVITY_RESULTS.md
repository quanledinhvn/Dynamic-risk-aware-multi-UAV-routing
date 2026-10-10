# Kết quả sensitivity test

Sinh tự động bởi `analyze.py` lúc 2026-10-10 18:56 · commit 1d15fce · 2430 job · 0 nghiệm không khả thi.

Kế hoạch: mục 2.2 của [../CLAUDE.md](../CLAUDE.md). Theo dõi tiến độ trực tiếp: `phase1/.venv/Scripts/python sensitivity_test/code/runner.py status`.

## 1. Tiến độ

| Case | Job xong | % | CPU đã chạy |
|---|---|---|---|
| A. RH (warm_alns) | 810/810 | 100.0% | 172.3 h |
| B. CTX (static) | 855/855 | 100.0% | 39.9 h |
| C. RH + CTX | 765/765 | 100.0% | 193.4 h |
| **Tổng** | **2430/2430** | **100.0%** | |

## 2. Kết luận theo tham số

| Case | Tham số | Số mức | Cặp đủ | Mức tốt nhất (thắng − thua) | p (Holm) | Kết luận |
|---|---|---|---|---|---|---|
| A | `epoch_fraction` | 4 | 45 | 0.025 | <0.001 | **NHẠY** |
| A | `iterations_per_epoch` | 4 | 45 | 1000 | <0.001 | **NHẠY** |
| A | `trigger` | 3 | 45 | hybrid | <0.001 | **NHẠY** |
| A | `iterations_epoch0` | 4 | 45 | 4000 | 0.002 | **NHẠY** |
| A | `beta` | 5 | 45 | 0.75 | — | mô tả (β đổi định nghĩa objective) |
| A | `q_min-q_max` | 3 | 45 | 10-20 | 0.001 | **NHẠY** |
| B | `iterations` | 3 | 45 | 2000 | <0.001 | **NHẠY** |
| B | `linucb_exploration` | 5 | 45 | 1.0 | <0.001 | **NHẠY** |
| B | `context_window` | 4 | 45 | mặc định | 1.000 | không nhạy |
| B | `beta` | 5 | 45 | 0.75 | — | mô tả (β đổi định nghĩa objective) |
| B | `linucb_regularization` | 3 | 45 | 0.1 | 1.000 | không nhạy về chất lượng; nhạy về runtime |
| B | `include_temperature` | 2 | 45 | mặc định | 1.000 | không nhạy |
| B | `q_min-q_max` | 3 | 45 | 10-20 | <0.001 | **NHẠY** |
| C | `epoch_fraction` | 4 | 45 | 0.025 | <0.001 | **NHẠY** |
| C | `iterations_per_epoch` | 4 | 45 | 1000 | <0.001 | **NHẠY** |
| C | `linucb_exploration` | 3 | 45 | 2.0 | <0.001 | **NHẠY** |
| C | `beta` | 5 | 45 | 0.75 | — | mô tả (β đổi định nghĩa objective) |
| C | `context_window` | 3 | 45 | mặc định | 0.749 | không nhạy |
| C | `q_min-q_max` | 3 | 45 | 10-20 | 0.004 | **NHẠY** |

Quy tắc kết luận:

- **NHẠY:** kiểm định tổng thể (Friedman trên thứ hạng từ điển; sign test khi chỉ có 2 mức) có $p < 0.05$ sau hiệu chỉnh Holm trong cùng case, **và** có ít nhất một mức đạt hiệu ứng thực tế: $|\text{median}\,\Delta\text{Obj}| \ge 1\%$, hoặc $|\overline{\Delta K}| \ge 0.1$, hoặc (case động) số khách unserved đổi $\ge 0.1$.
- **Có ý nghĩa thống kê, hiệu ứng nhỏ:** $p$ đạt ngưỡng nhưng hiệu ứng dưới các ngưỡng trên.
- **Không nhạy về chất lượng; nhạy về runtime:** chỉ runtime đổi $\ge 20\%$.
- **Mô tả:** $\beta$ đổi chính định nghĩa của objective nên chỉ đọc bảng đánh đổi, không xếp hạng.
- Thứ tự so sánh: case động (A, C) dùng (unserved, số UAV, objective); case tĩnh (B) dùng (số UAV, objective).
- Với 5 seed × 9 instance = 45 cặp, đây là kết quả **sàng lọc**.

## 3. Chi tiết theo case

ΔUAV, ΔObj, ΔUnserved, ΔRuntime: so với mức mặc định trên cùng (instance, seed). Số âm là tốt hơn (trừ runtime). Thắng/Thua: số cặp mà mức đó tốt hơn / kém hơn mặc định.

### Case A. RH (warm_alns)

#### `epoch_fraction`

| Mức | n | UAV | ΔUAV | Quãng đường | Risk delay | Objective | median ΔObj (%) | unserved | ΔUnserved | Thắng/Thua | Runtime (s) | ΔRuntime (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **mặc định** | 45 | 14.33 | — | 1425.2 | 0.084 | 0.4916 | — | 0.56 | — | — | 544.4 | — |
| 0.2 | 45 | 14.09 | -0.24 | 1417.6 | 0.096 | 0.4941 | 0.98 | 1.93 | 1.38 | 3/42 | 297.6 | -45 |
| 0.1 | 45 | 14.38 | 0.04 | 1423.4 | 0.091 | 0.4934 | 0.71 | 0.91 | 0.36 | 11/34 | 398.9 | -27 |
| 0.025 | 45 | 14.38 | 0.04 | 1413.6 | 0.085 | 0.4890 | 0.01 | 0.27 | -0.29 | 29/16 | 1078.3 | 98 |

Số cặp (instance, seed) đủ mọi mức: 45.

#### `iterations_per_epoch`

| Mức | n | UAV | ΔUAV | Quãng đường | Risk delay | Objective | median ΔObj (%) | unserved | ΔUnserved | Thắng/Thua | Runtime (s) | ΔRuntime (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **mặc định** | 45 | 14.33 | — | 1425.2 | 0.084 | 0.4916 | — | 0.56 | — | — | 544.4 | — |
| 100 | 45 | 14.62 | 0.29 | 1449.9 | 0.086 | 0.5011 | 1.09 | 0.58 | 0.02 | 7/38 | 291.4 | -46 |
| 250 | 45 | 14.51 | 0.18 | 1436.4 | 0.086 | 0.4968 | 0.65 | 0.60 | 0.04 | 10/31 | 402.5 | -26 |
| 1000 | 45 | 14.38 | 0.04 | 1416.2 | 0.080 | 0.4874 | -0.57 | 0.58 | 0.02 | 29/16 | 1035.7 | 90 |

Số cặp (instance, seed) đủ mọi mức: 45.

#### `trigger`

| Mức | n | UAV | ΔUAV | Quãng đường | Risk delay | Objective | median ΔObj (%) | unserved | ΔUnserved | Thắng/Thua | Runtime (s) | ΔRuntime (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **mặc định** | 45 | 14.33 | — | 1425.2 | 0.084 | 0.4916 | — | 0.56 | — | — | 544.4 | — |
| event | 45 | 14.33 | 0.00 | 1418.0 | 0.082 | 0.4883 | -0.23 | 0.13 | -0.42 | 35/10 | 755.4 | 39 |
| hybrid | 45 | 14.36 | 0.02 | 1418.7 | 0.080 | 0.4879 | -0.61 | 0.13 | -0.42 | 36/9 | 946.8 | 74 |

Số cặp (instance, seed) đủ mọi mức: 45.

#### `iterations_epoch0`

| Mức | n | UAV | ΔUAV | Quãng đường | Risk delay | Objective | median ΔObj (%) | unserved | ΔUnserved | Thắng/Thua | Runtime (s) | ΔRuntime (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **mặc định** | 45 | 14.33 | — | 1425.2 | 0.084 | 0.4916 | — | 0.56 | — | — | 544.4 | — |
| 500 | 45 | 14.47 | 0.13 | 1437.2 | 0.082 | 0.4945 | -0.46 | 0.58 | 0.02 | 19/26 | 371.2 | -32 |
| 1000 | 45 | 14.56 | 0.22 | 1424.2 | 0.080 | 0.4888 | -0.31 | 0.60 | 0.04 | 18/22 | 409.0 | -25 |
| 4000 | 45 | 14.31 | -0.02 | 1410.4 | 0.072 | 0.4814 | -1.14 | 0.58 | 0.02 | 23/12 | 682.7 | 25 |

Số cặp (instance, seed) đủ mọi mức: 45.

#### `beta`

| Mức | n | UAV | ΔUAV | Quãng đường | Risk delay | Objective | median ΔObj (%) | unserved | ΔUnserved | Thắng/Thua | Runtime (s) | ΔRuntime (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **mặc định** | 45 | 14.33 | — | 1425.2 | 0.084 | 0.4916 | — | 0.56 | — | — | 544.4 | — |
| 0.0 | 45 | 14.02 | -0.31 | 1335.7 | 0.349 | 0.8357 | 67.64 | 0.58 | 0.02 | 16/29 | 521.8 | -4 |
| 0.25 | 45 | 14.20 | -0.13 | 1366.2 | 0.122 | 0.6745 | 37.15 | 0.56 | 0.00 | 15/30 | 532.7 | -2 |
| 0.75 | 45 | 14.51 | 0.18 | 1471.0 | 0.062 | 0.2802 | -42.96 | 0.58 | 0.02 | 30/15 | 525.5 | -3 |
| 1.0 | 45 | 15.47 | 1.13 | 2359.0 | 0.054 | 0.0537 | -91.74 | 0.53 | -0.02 | 14/31 | 470.3 | -14 |

Số cặp (instance, seed) đủ mọi mức: 45.

#### `q_min-q_max`

| Mức | n | UAV | ΔUAV | Quãng đường | Risk delay | Objective | median ΔObj (%) | unserved | ΔUnserved | Thắng/Thua | Runtime (s) | ΔRuntime (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **mặc định** | 45 | 14.33 | — | 1425.2 | 0.084 | 0.4916 | — | 0.56 | — | — | 544.4 | — |
| 5-10 | 45 | 14.24 | -0.09 | 1391.4 | 0.082 | 0.4794 | -2.29 | 0.56 | 0.00 | 29/16 | 1294.4 | 138 |
| 10-20 | 45 | 14.07 | -0.27 | 1369.6 | 0.085 | 0.4733 | -3.77 | 0.60 | 0.04 | 33/12 | 3228.3 | 493 |

Số cặp (instance, seed) đủ mọi mức: 45.

### Case B. CTX (static)

#### `iterations`

| Mức | n | UAV | ΔUAV | Quãng đường | Risk delay | Objective | median ΔObj (%) | Thắng/Thua | Runtime (s) | ΔRuntime (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **mặc định** | 45 | 13.89 | — | 1467.6 | 0.100 | 0.4841 | — | — | 137.1 | — |
| 500 | 45 | 14.18 | 0.29 | 1508.1 | 0.094 | 0.4949 | 1.59 | 13/32 | 64.9 | -53 |
| 2000 | 45 | 13.91 | 0.02 | 1456.1 | 0.082 | 0.4728 | -2.16 | 28/17 | 328.0 | 139 |

Số cặp (instance, seed) đủ mọi mức: 45.

#### `linucb_exploration`

| Mức | n | UAV | ΔUAV | Quãng đường | Risk delay | Objective | median ΔObj (%) | Thắng/Thua | Runtime (s) | ΔRuntime (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **mặc định** | 45 | 13.89 | — | 1467.6 | 0.100 | 0.4841 | — | — | 137.1 | — |
| 0.0 | 45 | 14.27 | 0.38 | 1584.4 | 0.122 | 0.5306 | 7.70 | 7/38 | 189.9 | 38 |
| 0.1 | 45 | 13.98 | 0.09 | 1512.0 | 0.122 | 0.5095 | 2.61 | 14/31 | 171.5 | 25 |
| 1.0 | 45 | 14.00 | 0.11 | 1449.5 | 0.084 | 0.4706 | -1.63 | 25/20 | 128.6 | -6 |
| 2.0 | 45 | 14.02 | 0.13 | 1452.9 | 0.092 | 0.4767 | -0.22 | 20/25 | 116.2 | -15 |

Số cặp (instance, seed) đủ mọi mức: 45.

#### `context_window`

| Mức | n | UAV | ΔUAV | Quãng đường | Risk delay | Objective | median ΔObj (%) | Thắng/Thua | Runtime (s) | ΔRuntime (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **mặc định** | 45 | 13.89 | — | 1467.6 | 0.100 | 0.4841 | — | — | 137.1 | — |
| 200 | 45 | 14.00 | 0.11 | 1459.8 | 0.100 | 0.4825 | -1.00 | 21/24 | 143.0 | 4 |
| 25 | 45 | 14.00 | 0.11 | 1472.5 | 0.097 | 0.4838 | 0.18 | 20/25 | 141.7 | 3 |
| 50 | 45 | 14.04 | 0.16 | 1486.0 | 0.092 | 0.4862 | 0.96 | 19/26 | 143.7 | 5 |

Số cặp (instance, seed) đủ mọi mức: 45.

#### `beta`

| Mức | n | UAV | ΔUAV | Quãng đường | Risk delay | Objective | median ΔObj (%) | Thắng/Thua | Runtime (s) | ΔRuntime (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **mặc định** | 45 | 13.89 | — | 1467.6 | 0.100 | 0.4841 | — | — | 137.1 | — |
| 0.0 | 45 | 13.82 | -0.07 | 1360.3 | 0.390 | 0.7984 | 69.86 | 8/37 | 115.1 | -16 |
| 0.25 | 45 | 13.89 | 0.00 | 1416.0 | 0.145 | 0.6603 | 41.11 | 12/33 | 127.6 | -7 |
| 0.75 | 45 | 14.11 | 0.22 | 1521.9 | 0.071 | 0.2801 | -42.93 | 35/10 | 126.5 | -8 |
| 1.0 | 45 | 14.47 | 0.58 | 2177.5 | 0.087 | 0.0866 | -84.08 | 21/24 | 121.6 | -11 |

Số cặp (instance, seed) đủ mọi mức: 45.

#### `linucb_regularization`

| Mức | n | UAV | ΔUAV | Quãng đường | Risk delay | Objective | median ΔObj (%) | Thắng/Thua | Runtime (s) | ΔRuntime (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **mặc định** | 45 | 13.89 | — | 1467.6 | 0.100 | 0.4841 | — | — | 137.1 | — |
| 0.1 | 45 | 13.96 | 0.07 | 1478.4 | 0.099 | 0.4865 | -0.46 | 23/22 | 106.5 | -22 |
| 10.0 | 45 | 14.00 | 0.11 | 1497.0 | 0.096 | 0.4933 | 0.84 | 21/24 | 142.7 | 4 |

Số cặp (instance, seed) đủ mọi mức: 45.

#### `include_temperature`

| Mức | n | UAV | ΔUAV | Quãng đường | Risk delay | Objective | median ΔObj (%) | Thắng/Thua | Runtime (s) | ΔRuntime (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **mặc định** | 45 | 13.89 | — | 1467.6 | 0.100 | 0.4841 | — | — | 137.1 | — |
| false | 45 | 14.02 | 0.13 | 1470.6 | 0.093 | 0.4827 | -0.38 | 20/25 | 117.0 | -15 |

Số cặp (instance, seed) đủ mọi mức: 45.

#### `q_min-q_max`

| Mức | n | UAV | ΔUAV | Quãng đường | Risk delay | Objective | median ΔObj (%) | Thắng/Thua | Runtime (s) | ΔRuntime (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **mặc định** | 45 | 13.89 | — | 1467.6 | 0.100 | 0.4841 | — | — | 137.1 | — |
| 5-10 | 45 | 14.09 | 0.20 | 1400.7 | 0.082 | 0.4560 | -4.69 | 25/20 | 217.8 | 59 |
| 10-20 | 45 | 13.80 | -0.09 | 1343.7 | 0.101 | 0.4468 | -7.00 | 34/11 | 552.8 | 303 |

Số cặp (instance, seed) đủ mọi mức: 45.

### Case C. RH + CTX

#### `epoch_fraction`

| Mức | n | UAV | ΔUAV | Quãng đường | Risk delay | Objective | median ΔObj (%) | unserved | ΔUnserved | Thắng/Thua | Runtime (s) | ΔRuntime (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **mặc định** | 45 | 14.24 | — | 1431.8 | 0.089 | 0.4952 | — | 0.56 | — | — | 726.3 | — |
| 0.2 | 45 | 14.00 | -0.24 | 1429.0 | 0.112 | 0.5050 | 2.06 | 1.89 | 1.33 | 2/43 | 393.9 | -46 |
| 0.1 | 45 | 14.36 | 0.11 | 1440.5 | 0.098 | 0.5015 | 0.36 | 0.93 | 0.38 | 11/34 | 490.0 | -33 |
| 0.025 | 45 | 14.27 | 0.02 | 1434.6 | 0.088 | 0.4976 | -0.25 | 0.27 | -0.29 | 29/16 | 1155.3 | 59 |

Số cặp (instance, seed) đủ mọi mức: 45.

#### `iterations_per_epoch`

| Mức | n | UAV | ΔUAV | Quãng đường | Risk delay | Objective | median ΔObj (%) | unserved | ΔUnserved | Thắng/Thua | Runtime (s) | ΔRuntime (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **mặc định** | 45 | 14.24 | — | 1431.8 | 0.089 | 0.4952 | — | 0.56 | — | — | 726.3 | — |
| 100 | 45 | 14.51 | 0.27 | 1457.6 | 0.093 | 0.5051 | 1.27 | 0.56 | 0.00 | 10/33 | 390.8 | -46 |
| 250 | 45 | 14.38 | 0.13 | 1436.6 | 0.091 | 0.4978 | 0.09 | 0.56 | 0.00 | 15/27 | 506.6 | -30 |
| 1000 | 45 | 14.16 | -0.09 | 1416.8 | 0.095 | 0.4941 | -0.31 | 0.56 | 0.00 | 27/17 | 1143.8 | 57 |

Số cặp (instance, seed) đủ mọi mức: 45.

#### `linucb_exploration`

| Mức | n | UAV | ΔUAV | Quãng đường | Risk delay | Objective | median ΔObj (%) | unserved | ΔUnserved | Thắng/Thua | Runtime (s) | ΔRuntime (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **mặc định** | 45 | 14.24 | — | 1431.8 | 0.089 | 0.4952 | — | 0.56 | — | — | 726.3 | — |
| 0.0 | 45 | 14.71 | 0.47 | 1472.2 | 0.082 | 0.5046 | 0.78 | 0.58 | 0.02 | 9/36 | 734.0 | 1 |
| 2.0 | 45 | 14.29 | 0.04 | 1417.6 | 0.081 | 0.4882 | -2.36 | 0.58 | 0.02 | 24/21 | 600.5 | -17 |

Số cặp (instance, seed) đủ mọi mức: 45.

#### `beta`

| Mức | n | UAV | ΔUAV | Quãng đường | Risk delay | Objective | median ΔObj (%) | unserved | ΔUnserved | Thắng/Thua | Runtime (s) | ΔRuntime (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **mặc định** | 45 | 14.24 | — | 1431.8 | 0.089 | 0.4952 | — | 0.56 | — | — | 726.3 | — |
| 0.0 | 45 | 14.02 | -0.22 | 1328.0 | 0.368 | 0.8307 | 66.05 | 0.62 | 0.07 | 14/31 | 716.8 | -1 |
| 0.25 | 45 | 14.20 | -0.04 | 1385.6 | 0.120 | 0.6814 | 38.02 | 0.56 | 0.00 | 11/34 | 653.3 | -10 |
| 0.75 | 45 | 14.47 | 0.22 | 1495.0 | 0.058 | 0.2808 | -44.33 | 0.60 | 0.04 | 29/16 | 685.0 | -6 |
| 1.0 | 45 | 15.33 | 1.09 | 2338.6 | 0.058 | 0.0576 | -92.13 | 0.56 | 0.00 | 11/34 | 573.4 | -21 |

Số cặp (instance, seed) đủ mọi mức: 45.

#### `context_window`

| Mức | n | UAV | ΔUAV | Quãng đường | Risk delay | Objective | median ΔObj (%) | unserved | ΔUnserved | Thắng/Thua | Runtime (s) | ΔRuntime (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **mặc định** | 45 | 14.24 | — | 1431.8 | 0.089 | 0.4952 | — | 0.56 | — | — | 726.3 | — |
| 200 | 45 | 14.49 | 0.24 | 1420.3 | 0.076 | 0.4863 | -1.89 | 0.58 | 0.02 | 19/26 | 636.0 | -12 |
| 25 | 45 | 14.38 | 0.13 | 1417.2 | 0.082 | 0.4880 | -1.89 | 0.60 | 0.04 | 22/23 | 718.5 | -1 |

Số cặp (instance, seed) đủ mọi mức: 45.

#### `q_min-q_max`

| Mức | n | UAV | ΔUAV | Quãng đường | Risk delay | Objective | median ΔObj (%) | unserved | ΔUnserved | Thắng/Thua | Runtime (s) | ΔRuntime (%) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **mặc định** | 45 | 14.24 | — | 1431.8 | 0.089 | 0.4952 | — | 0.56 | — | — | 726.3 | — |
| 5-10 | 45 | 14.22 | -0.02 | 1397.2 | 0.086 | 0.4835 | -1.95 | 0.56 | 0.00 | 29/16 | 1382.2 | 90 |
| 10-20 | 45 | 13.91 | -0.33 | 1371.1 | 0.087 | 0.4754 | -3.97 | 0.60 | 0.04 | 31/14 | 3962.5 | 446 |

Số cặp (instance, seed) đủ mọi mức: 45.


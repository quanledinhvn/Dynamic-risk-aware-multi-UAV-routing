## dynamic_n25_d5

| policy | runs | F mean | F std | UAVs | unserved | served-all % | gap % (all-served) | runtime s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| greedy_insert | 900 | 0.6449 | 0.1443 | 5.31 | 0.30 | 74.9 | 12.35 | 7.2 |
| cold_restart | 900 | 0.6362 | 0.1467 | 5.29 | 0.30 | 74.6 | 10.67 | 23.3 |
| warm_alns | 900 | 0.6199 | 0.1524 | 5.17 | 0.28 | 76.0 | 6.12 | 23.1 |

Paired comparison of `warm_alns` against each other policy on the same scenario and seed. Wins use the lexicographic order (unserved, UAVs, F); ΔF is other minus reference, so positive favours the reference. Wilcoxon is the two-sided signed-rank test on F; Holm adjusts across the comparisons in this block.

| reference vs | pairs | wins | losses | ties | mean ΔF | median ΔF | Wilcoxon p | Holm p |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| greedy_insert | 900 | 604 | 40 | 256 | +0.0250 | +0.0226 | 2.01e-77 | 4.01e-77 |
| cold_restart | 900 | 413 | 92 | 395 | +0.0163 | +0.0000 | 1.90e-46 | 1.90e-46 |

## dynamic_n25_d12

| policy | runs | F mean | F std | UAVs | unserved | served-all % | gap % (all-served) | runtime s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| greedy_insert | 900 | 0.8860 | 0.2175 | 6.32 | 0.89 | 40.0 | 25.76 | 7.3 |
| cold_restart | 900 | 0.8017 | 0.1743 | 6.14 | 0.96 | 39.9 | 15.33 | 25.8 |
| warm_alns | 900 | 0.7809 | 0.1827 | 6.08 | 0.94 | 40.4 | 10.35 | 25.3 |

Paired comparison of `warm_alns` against each other policy on the same scenario and seed. Wins use the lexicographic order (unserved, UAVs, F); ΔF is other minus reference, so positive favours the reference. Wilcoxon is the two-sided signed-rank test on F; Holm adjusts across the comparisons in this block.

| reference vs | pairs | wins | losses | ties | mean ΔF | median ΔF | Wilcoxon p | Holm p |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| greedy_insert | 900 | 741 | 110 | 49 | +0.1050 | +0.0864 | 4.60e-133 | 9.21e-133 |
| cold_restart | 900 | 540 | 148 | 212 | +0.0207 | +0.0052 | 3.92e-42 | 3.92e-42 |

## dynamic_n25_d25

| policy | runs | F mean | F std | UAVs | unserved | served-all % | gap % (all-served) | runtime s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| greedy_insert | 900 | 1.1722 | 0.2702 | 8.47 | 1.81 | 36.0 | 35.76 | 7.3 |
| cold_restart | 900 | 1.0231 | 0.1982 | 7.76 | 1.92 | 35.1 | 18.49 | 31.0 |
| warm_alns | 900 | 0.9879 | 0.2040 | 7.76 | 1.85 | 35.4 | 11.78 | 31.0 |

Paired comparison of `warm_alns` against each other policy on the same scenario and seed. Wins use the lexicographic order (unserved, UAVs, F); ΔF is other minus reference, so positive favours the reference. Wilcoxon is the two-sided signed-rank test on F; Holm adjusts across the comparisons in this block.

| reference vs | pairs | wins | losses | ties | mean ΔF | median ΔF | Wilcoxon p | Holm p |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| greedy_insert | 900 | 777 | 113 | 10 | +0.1843 | +0.1500 | 2.26e-139 | 4.53e-139 |
| cold_restart | 900 | 583 | 239 | 78 | +0.0352 | +0.0190 | 1.59e-49 | 1.59e-49 |

## dynamic_n100_d5

| policy | runs | F mean | F std | UAVs | unserved | served-all % | gap % (all-served) | runtime s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| greedy_insert | 270 | 0.5227 | 0.0479 | 14.33 | 0.19 | 84.1 | 16.08 | 33.3 |
| cold_restart | 270 | 0.5313 | 0.0786 | 14.79 | 0.19 | 84.1 | 15.24 | 97.6 |
| warm_alns | 270 | 0.4799 | 0.0493 | 14.07 | 0.21 | 81.9 | 5.51 | 97.7 |

Paired comparison of `warm_alns` against each other policy on the same scenario and seed. Wins use the lexicographic order (unserved, UAVs, F); ΔF is other minus reference, so positive favours the reference. Wilcoxon is the two-sided signed-rank test on F; Holm adjusts across the comparisons in this block.

| reference vs | pairs | wins | losses | ties | mean ΔF | median ΔF | Wilcoxon p | Holm p |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| greedy_insert | 270 | 246 | 24 | 0 | +0.0428 | +0.0321 | 1.34e-40 | 2.68e-40 |
| cold_restart | 270 | 221 | 49 | 0 | +0.0514 | +0.0463 | 9.85e-38 | 9.85e-38 |

## dynamic_n100_d12

| policy | runs | F mean | F std | UAVs | unserved | served-all % | gap % (all-served) | runtime s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| greedy_insert | 270 | 0.5392 | 0.0735 | 14.39 | 0.52 | 52.6 | 18.79 | 29.9 |
| cold_restart | 270 | 0.5497 | 0.0693 | 14.98 | 0.54 | 51.9 | 19.96 | 92.7 |
| warm_alns | 270 | 0.4912 | 0.0597 | 14.27 | 0.53 | 52.6 | 6.33 | 93.0 |

Paired comparison of `warm_alns` against each other policy on the same scenario and seed. Wins use the lexicographic order (unserved, UAVs, F); ΔF is other minus reference, so positive favours the reference. Wilcoxon is the two-sided signed-rank test on F; Holm adjusts across the comparisons in this block.

| reference vs | pairs | wins | losses | ties | mean ΔF | median ΔF | Wilcoxon p | Holm p |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| greedy_insert | 270 | 234 | 36 | 0 | +0.0481 | +0.0433 | 5.22e-45 | 1.04e-44 |
| cold_restart | 270 | 248 | 22 | 0 | +0.0585 | +0.0507 | 2.25e-43 | 2.25e-43 |

## dynamic_n100_d25

| policy | runs | F mean | F std | UAVs | unserved | served-all % | gap % (all-served) | runtime s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| greedy_insert | 270 | 0.6760 | 0.0708 | 15.89 | 0.70 | 40.7 | 27.98 | 24.9 |
| cold_restart | 270 | 0.6545 | 0.1005 | 14.86 | 0.81 | 37.8 | 22.02 | 85.7 |
| warm_alns | 270 | 0.5750 | 0.0789 | 14.62 | 0.74 | 41.1 | 6.29 | 84.0 |

Paired comparison of `warm_alns` against each other policy on the same scenario and seed. Wins use the lexicographic order (unserved, UAVs, F); ΔF is other minus reference, so positive favours the reference. Wilcoxon is the two-sided signed-rank test on F; Holm adjusts across the comparisons in this block.

| reference vs | pairs | wins | losses | ties | mean ΔF | median ΔF | Wilcoxon p | Holm p |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| greedy_insert | 270 | 250 | 20 | 0 | +0.1010 | +0.0955 | 5.09e-46 | 1.02e-45 |
| cold_restart | 270 | 213 | 57 | 0 | +0.0794 | +0.0699 | 2.81e-45 | 2.81e-45 |

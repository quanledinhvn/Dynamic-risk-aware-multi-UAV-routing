## Epoch length

| policy | runs | F mean | F std | UAVs | unserved | served-all % | gap % (all-served) | runtime s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.025 | 90 | 0.7776 | 0.1727 | 6.01 | 0.88 | 40.0 | 10.52 | 44.0 |
| 0.05 | 90 | 0.7844 | 0.1838 | 6.08 | 0.93 | 41.1 | 11.23 | 24.7 |
| 0.1 | 90 | 0.7747 | 0.2008 | 6.02 | 1.52 | 18.9 | 13.04 | 15.2 |
| 0.2 | 90 | 0.7415 | 0.1686 | 5.67 | 3.94 | 0.0 | n/a | 10.6 |

Paired comparison of `0.05` against each other policy on the same scenario and seed. Wins use the lexicographic order (unserved, UAVs, F); ΔF is other minus reference, so positive favours the reference. Wilcoxon is the two-sided signed-rank test on F; Holm adjusts across the comparisons in this block.

| reference vs | pairs | wins | losses | ties | mean ΔF | median ΔF | Wilcoxon p | Holm p |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.025 | 90 | 26 | 41 | 23 | -0.0069 | +0.0000 | 0.018 | 0.035 |
| 0.1 | 90 | 58 | 23 | 9 | -0.0097 | -0.0042 | 0.050 | 0.050 |
| 0.2 | 90 | 90 | 0 | 0 | -0.0430 | -0.0326 | 1.73e-06 | 5.20e-06 |

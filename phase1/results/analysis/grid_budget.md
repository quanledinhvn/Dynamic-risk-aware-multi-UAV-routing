## Budget per epoch

| policy | runs | F mean | F std | UAVs | unserved | served-all % | gap % (all-served) | runtime s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 100 | 90 | 0.7872 | 0.1852 | 6.11 | 0.93 | 41.1 | 11.60 | 10.5 |
| 250 | 90 | 0.7871 | 0.1824 | 6.09 | 0.93 | 41.1 | 11.66 | 15.9 |
| 500 | 90 | 0.7844 | 0.1838 | 6.08 | 0.93 | 41.1 | 11.23 | 24.7 |
| 1000 | 90 | 0.7805 | 0.1827 | 6.08 | 0.93 | 41.1 | 10.27 | 43.7 |

Paired comparison of `500` against each other policy on the same scenario and seed. Wins use the lexicographic order (unserved, UAVs, F); ΔF is other minus reference, so positive favours the reference. Wilcoxon is the two-sided signed-rank test on F; Holm adjusts across the comparisons in this block.

| reference vs | pairs | wins | losses | ties | mean ΔF | median ΔF | Wilcoxon p | Holm p |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 100 | 90 | 31 | 11 | 48 | +0.0027 | +0.0000 | 0.008 | 0.025 |
| 250 | 90 | 19 | 9 | 62 | +0.0027 | +0.0000 | 0.116 | 0.116 |
| 1000 | 90 | 5 | 16 | 69 | -0.0039 | +0.0000 | 0.011 | 0.025 |

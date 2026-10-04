## Trigger

| policy | runs | F mean | F std | UAVs | unserved | served-all % | gap % (all-served) | runtime s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| base | 90 | 0.7844 | 0.1838 | 6.08 | 0.93 | 41.1 | 11.23 | 24.7 |
| event | 90 | 0.7781 | 0.1677 | 6.10 | 0.68 | 50.0 | 8.44 | 31.4 |
| hybrid | 90 | 0.7742 | 0.1725 | 6.13 | 0.68 | 51.1 | 7.13 | 40.5 |

Paired comparison of `base` against each other policy on the same scenario and seed. Wins use the lexicographic order (unserved, UAVs, F); ΔF is other minus reference, so positive favours the reference. Wilcoxon is the two-sided signed-rank test on F; Holm adjusts across the comparisons in this block.

| reference vs | pairs | wins | losses | ties | mean ΔF | median ΔF | Wilcoxon p | Holm p |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| event | 90 | 25 | 51 | 14 | -0.0063 | +0.0000 | 0.128 | 0.128 |
| hybrid | 90 | 23 | 55 | 12 | -0.0102 | -0.0011 | 0.044 | 0.089 |

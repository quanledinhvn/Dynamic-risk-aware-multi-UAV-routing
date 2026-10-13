# Contextual bandit diagnosis

## Epoch 0: static 2000-iteration solve, roulette vs contextual

81 instance x seed pairs (9 instances x {95, 88, 75} static customers x seeds 0-2), same seed for both selectors.

| selector | mean K | mean F | mean D | mean R |
|---|---:|---:|---:|---:|
| roulette | 12.47 | 0.4654 | 1297.6 | 0.0872 |
| contextual | 12.46 | 0.4784 | 1311.3 | 0.1049 |

Lexicographic (K, F): contextual better 35, roulette better 45, tie 1.  
F only: contextual better 34, roulette better 46, tie 1.  
K: contextual fewer 9, more 8, equal 64.

| class | n | F roulette | F contextual | K roulette | K contextual | R roulette | R contextual |
|---|---:|---:|---:|---:|---:|---:|---:|
| C | 27 | 0.4502 | 0.4659 | 9.07 | 9.11 | 0.108 | 0.123 |
| R | 27 | 0.4650 | 0.4724 | 15.59 | 15.56 | 0.022 | 0.030 |
| RC | 27 | 0.4810 | 0.4968 | 12.74 | 12.70 | 0.131 | 0.162 |

## Re-planning epochs only: identical roulette epoch 0, selectors swapped afterwards

12 scenarios (95+5, seeds 0-1), 400 iterations per epoch. Max destroy share is the largest share any destroy operator received, averaged over epochs; uniform is 20%.

| scenario | F roulette | F contextual | improving epochs r/c | epochs | max destroy share r/c |
|---|---:|---:|---|---:|---|
| c101-n95-d5-s0 | 0.6010 | 0.5992 | 4/2 | 21 | 23%/22% |
| c101-n95-d5-s1 | 0.6024 | 0.5938 | 6/7 | 21 | 24%/25% |
| r101-n95-d5-s0 | 0.4604 | 0.4567 | 6/5 | 20 | 24%/25% |
| r101-n95-d5-s1 | 0.4607 | 0.4575 | 7/8 | 20 | 24%/26% |
| rc101-n95-d5-s0 | 0.4752 | 0.4855 | 6/8 | 20 | 23%/23% |
| rc101-n95-d5-s1 | 0.5046 | 0.4788 | 7/8 | 20 | 23%/25% |
| c102-n95-d5-s0 | 0.5012 | 0.4974 | 5/5 | 21 | 24%/24% |
| c102-n95-d5-s1 | 0.4949 | 0.4890 | 7/5 | 21 | 24%/24% |
| r102-n95-d5-s0 | 0.5756 | 0.5387 | 10/9 | 20 | 24%/26% |
| r102-n95-d5-s1 | 0.4802 | 0.4768 | 6/7 | 20 | 23%/26% |
| rc102-n95-d5-s0 | 0.5120 | 0.4995 | 9/7 | 20 | 24%/25% |
| rc102-n95-d5-s1 | 0.4874 | 0.4820 | 6/7 | 20 | 23%/24% |

Mean F(contextual) - F(roulette) = -0.0084; contextual better in 11/12.

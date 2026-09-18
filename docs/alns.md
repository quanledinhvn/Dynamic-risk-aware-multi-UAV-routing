# Adaptive Large Neighborhood Search (ALNS)

Dưới đây là giả mã **ALNS đầy đủ theo phiên bản kinh điển**, gồm destroy, repair, chọn theo trọng số, Simulated Annealing, cơ chế thưởng và cập nhật trọng số thích nghi.

## Giả mã ALNS

```text
ALGORITHM ALNS(instance, parameters)

INPUT:
    instance                 dữ liệu bài toán

    D = {d1, d2, ..., dm}    tập destroy operators
    R = {r1, r2, ..., rn}    tập repair operators

    q_min, q_max             số nhiệm vụ bị tháo
    w0                       trọng số ban đầu

    σ1                       thưởng khi tìm được best-so-far mới
    σ2                       thưởng khi cải thiện lời giải hiện tại
    σ3                       thưởng khi lời giải xấu hơn nhưng được chấp nhận
    ρ ∈ (0, 1]               tốc độ cập nhật trọng số
    L                        độ dài một segment

    T0                       nhiệt độ ban đầu
    c ∈ (0, 1)               hệ số làm nguội

    stopping_condition       điều kiện dừng

OUTPUT:
    S_best                   lời giải tốt nhất tìm được


1.  S ← BuildInitialSolution(instance)
2.  S_best ← Copy(S)

3.  FOR mỗi destroy operator di ∈ D:
4.      weightD[i] ← w0
5.      scoreD[i]  ← 0
6.      countD[i]  ← 0

7.  FOR mỗi repair operator rj ∈ R:
8.      weightR[j] ← w0
9.      scoreR[j]  ← 0
10.     countR[j]  ← 0

11. T ← T0
12. iteration ← 0

13. WHILE stopping_condition chưa thỏa mãn:

14.     --------------------------------------------------
15.     // BƯỚC 1: CHỌN DESTROY VÀ REPAIR THEO TRỌNG SỐ
16.     --------------------------------------------------

17.     Chọn di ∈ D với xác suất:

                    weightD[i]
        P(di) = ---------------------
                 Σdk∈D weightD[k]

18.     Chọn rj ∈ R với xác suất:

                    weightR[j]
        P(rj) = ---------------------
                 Σrk∈R weightR[k]

19.     countD[i] ← countD[i] + 1
20.     countR[j] ← countR[j] + 1


21.     --------------------------------------------------
22.     // BƯỚC 2: DESTROY
23.     --------------------------------------------------

24.     q ← RandomInteger(q_min, q_max)

25.     (S_partial, U) ← di(Copy(S), q)

        // S_partial: lời giải sau khi tháo q nhiệm vụ
        // U: tập nhiệm vụ đã bị tháo


26.     --------------------------------------------------
27.     // BƯỚC 3: REPAIR
28.     --------------------------------------------------

29.     S_candidate ← rj(S_partial, U)

30.     EvaluateAndCheckConstraints(S_candidate)

31.     IF S_candidate không hợp lệ và không sử dụng penalty:
32.         accepted ← FALSE
33.         reward ← 0
34.         GOTO bước 53


35.     --------------------------------------------------
36.     // BƯỚC 4: QUYẾT ĐỊNH CHẤP NHẬN
37.     --------------------------------------------------

38.     Δ ← F(S_candidate) - F(S)

        // Bài toán cực tiểu hóa:
        // Δ < 0: ứng viên tốt hơn lời giải hiện tại
        // Δ > 0: ứng viên xấu hơn lời giải hiện tại

39.     IF Δ ≤ 0:
40.         accepted ← TRUE
41.     ELSE:
42.         p_accept ← exp(-Δ / T)
43.         accepted ← (RandomReal(0, 1) < p_accept)


44.     --------------------------------------------------
45.     // BƯỚC 5: THƯỞNG OPERATOR
46.     --------------------------------------------------

47.     IF F(S_candidate) < F(S_best):
48.         S_best ← Copy(S_candidate)
49.         reward ← σ1

50.     ELSE IF F(S_candidate) < F(S):
51.         reward ← σ2

52.     ELSE IF accepted:
53.         reward ← σ3

54.     ELSE:
55.         reward ← 0


56.     --------------------------------------------------
57.     // BƯỚC 6: CẬP NHẬT LỜI GIẢI HIỆN TẠI
58.     --------------------------------------------------

59.     IF accepted:
60.         S ← Copy(S_candidate)


61.     --------------------------------------------------
62.     // BƯỚC 7: GHI NHẬN ĐIỂM OPERATOR
63.     --------------------------------------------------

64.     scoreD[i] ← scoreD[i] + reward
65.     scoreR[j] ← scoreR[j] + reward

66.     iteration ← iteration + 1


67.     --------------------------------------------------
68.     // BƯỚC 8: CẬP NHẬT TRỌNG SỐ SAU MỖI SEGMENT
69.     --------------------------------------------------

70.     IF iteration mod L = 0:

71.         FOR mỗi destroy operator dk ∈ D:
72.             IF countD[k] > 0:
73.                 averageScore ← scoreD[k] / countD[k]

74.                 weightD[k] ←
                       (1 - ρ) × weightD[k]
                       + ρ × averageScore

75.             scoreD[k] ← 0
76.             countD[k] ← 0

77.         FOR mỗi repair operator rk ∈ R:
78.             IF countR[k] > 0:
79.                 averageScore ← scoreR[k] / countR[k]

80.                 weightR[k] ←
                       (1 - ρ) × weightR[k]
                       + ρ × averageScore

81.             scoreR[k] ← 0
82.             countR[k] ← 0


83.     --------------------------------------------------
84.     // BƯỚC 9: GIẢM NHIỆT ĐỘ
85.     --------------------------------------------------

86.     T ← c × T

87. RETURN S_best
```

## Các bộ operator có thể sử dụng

```text
D = {
    RandomRemoval,
    WorstRemoval,
    RelatedRemoval,
    RouteRemoval,
    RiskBasedRemoval,
    TimeCriticalRemoval
}

R = {
    GreedyInsertion,
    Regret2Insertion,
    Regret3Insertion,
    RiskAwareInsertion,
    PriorityInsertion
}
```

## Hàm mục tiêu

Với bài toán cực tiểu hóa:

$$
\begin{aligned}
F(S) ={}& \alpha D(S) + \beta E(S) + \gamma L(S) \\
        &+ \delta U(S) + M V(S)
\end{aligned}
$$

Trong đó:

- $D(S)$: tổng quãng đường hoặc chi phí bay.
- $E(S)$: mức phơi nhiễm rủi ro.
- $L(S)$: tổng độ trễ.
- $U(S)$: chi phí của nhiệm vụ chưa phục vụ.
- $V(S)$: mức vi phạm ràng buộc.
- $M$: hệ số phạt lớn.

## Mức thưởng thường dùng

Cần chọn:

$$
\sigma_1 > \sigma_2 > \sigma_3 \geq 0
$$

Ví dụ:

```text
σ1 = 20    // tạo best-so-far mới
σ2 = 10    // cải thiện lời giải hiện tại
σ3 = 2     // không cải thiện nhưng được SA chấp nhận
```

Cả destroy và repair được sử dụng trong vòng lặp đều nhận cùng mức thưởng. Sau một segment, trọng số được cập nhật:

$$
w_i \leftarrow (1 - \rho)w_i + \rho \frac{\pi_i}{n_i}
$$

với:

- $w_i$: trọng số hiện tại;
- $\pi_i$: tổng điểm nhận được;
- $n_i$: số lần được sử dụng;
- $\rho$: tốc độ phản ứng.

Nếu $n_i = 0$, giữ nguyên trọng số để tránh phép chia cho 0.

## Lưu ý về thứ tự tính thưởng

Phải so sánh `S_candidate` với `S` **trước khi gán**:

```text
S ← S_candidate
```

Nếu cập nhật `S` trước rồi mới kiểm tra:

```text
F(S_candidate) < F(S)
```

thì hai lời giải đã giống nhau và điều kiện luôn sai. Đây là lỗi khá phổ biến khi cài đặt ALNS.

## Mở rộng cho bài toán động

Đây là cấu trúc ALNS một mục tiêu chuẩn. Với bài toán động, mỗi khi xuất hiện sự kiện mới, ta giữ nguyên phần tuyến đã thực hiện, cập nhật trạng thái UAV và chạy lại ALNS cho phần kế hoạch còn lại.

Khi đó, hàm mục tiêu có thể được viết gọn dưới dạng:

$$
F(S) = \operatorname{Cost}(S) + \operatorname{Penalty}(S)
$$

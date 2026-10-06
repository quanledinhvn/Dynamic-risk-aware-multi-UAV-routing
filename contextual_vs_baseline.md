# So sánh Contextual ALNS và ALNS baseline

## Kết luận nhanh

Với giả định hai thuật toán được chạy trong môi trường tương đương:

- **Chất lượng nghiệm:** hai thuật toán gần như tương đương.
- **Số UAV:** Contextual tốt hơn nhẹ, nhưng chênh lệch chưa đủ mạnh để kết luận vượt trội.
- **Distance, risk delay và objective:** không có khác biệt đáng kể khi so sánh các nghiệm dùng cùng số UAV.
- **Tốc độ:** Contextual nhanh hơn rõ rệt, trung bình **2,13 lần**.
- **Tính khả thi:** cả hai đạt 100%.

Vì vậy, kết luận phù hợp nhất là:

> **Contextual ALNS giữ chất lượng nghiệm tương đương ALNS baseline nhưng giảm khoảng 53% thời gian chạy.**

## 1. Bảng so sánh chính

Dữ liệu gồm 56 instance Solomon, 10 seed cho mỗi instance, 100 khách hàng, 5 mức rủi ro và 1.000 iteration. Tổng cộng có 560 cặp chạy cho mỗi thuật toán.

| Chỉ số, càng thấp càng tốt | Contextual | Baseline | Chênh lệch | Đánh giá |
|---|---:|---:|---:|---|
| Số UAV | **8,189** | 8,221 | -0,032 UAV | Contextual tốt hơn nhẹ |
| Distance | 1.223,87 | **1.219,56** | +4,31, tương đương +0,35% | Gần như ngang nhau |
| Risk delay | 0,09108 | **0,08580** | +0,00529 | Baseline tốt hơn nhẹ |
| Objective | 0,41810 | **0,41401** | +0,00409, tương đương +0,99% | Baseline tốt hơn nhẹ nếu không xét số UAV |
| Runtime | **106,85 giây** | 227,61 giây | -120,76 giây, tương đương -53,06% | **Contextual nhanh hơn 2,13 lần** |
| Tỷ lệ khả thi | **100%** | **100%** | 0 | Ngang nhau |

Objective không nên được đọc riêng khỏi số UAV. Thuật toán đang tối ưu theo thứ tự từ điển:

$$
(K,F),
$$

trong đó $K$ là số UAV và $F$ là objective. Ít UAV hơn luôn được ưu tiên trước; chỉ khi hai nghiệm có cùng số UAV mới so sánh objective.

## 2. So sánh đúng theo tiêu chí tối ưu

### 2.1. Kết quả thắng, thua và hòa

| Cách tổng hợp | Contextual thắng | Baseline thắng | Hòa |
|---|---:|---:|---:|
| Theo 560 cặp cùng instance và seed | 281 | 267 | 12 |
| Theo trung bình của 56 instance | 27 | 28 | 1 |

Số lượt thắng gần cân bằng. Do đó chưa có bằng chứng một thuật toán tạo nghiệm tốt hơn ổn định trên mọi instance.

### 2.2. So sánh số UAV

Trên 560 cặp chạy:

- Contextual dùng ít UAV hơn ở 70 cặp;
- Baseline dùng ít UAV hơn ở 52 cặp;
- hai thuật toán dùng cùng số UAV ở 438 cặp.

Số UAV trung bình giảm từ 8,221 xuống 8,189. Xu hướng nghiêng về Contextual, nhưng kiểm định Wilcoxon cho $p=0{,}053$, vừa cao hơn ngưỡng 0,05. Vì vậy chỉ nên kết luận **Contextual có xu hướng dùng ít UAV hơn**, chưa nên tuyên bố cải thiện có ý nghĩa thống kê.

### 2.3. So sánh khi cùng số UAV

Đây là so sánh công bằng nhất đối với distance, risk delay và objective. Phân tích chỉ giữ 438 cặp mà hai thuật toán dùng cùng số UAV.

| Chỉ số | Chênh lệch Contextual − Baseline | Wilcoxon $p$ | Kết luận |
|---|---:|---:|---|
| Distance | +2,659 | 0,815 | Không khác biệt |
| Risk delay | -0,00077 | 0,789 | Không khác biệt |
| Objective | +0,00041 | 0,834 | Không khác biệt |

Trong 438 cặp này, Contextual thắng objective 211 lần, Baseline thắng 215 lần và hòa 12 lần. Như vậy, **chất lượng thứ cấp của hai thuật toán thực tế tương đương khi số UAV bằng nhau**.

Objective tổng thể của Contextual cao hơn chủ yếu vì Contextual đôi khi đạt số UAV thấp hơn và chấp nhận objective lớn hơn. Đây là đánh đổi phù hợp với chính sách lexicographic, không phải dấu hiệu Contextual chắc chắn tạo nghiệm kém hơn.

## 3. So sánh tốc độ

| Thuật toán | Runtime trung bình | Runtime trung vị |
|---|---:|---:|
| Contextual ALNS | **106,85 giây** | **29,77 giây** |
| ALNS baseline | 227,61 giây | 194,94 giây |

Contextual giảm trung bình 120,76 giây mỗi lượt chạy:

$$
\frac{227{,}61-106{,}85}{227{,}61}\times100\%=53{,}06\%.
$$

Hệ số tăng tốc là:

$$
\frac{227{,}61}{106{,}85}=2{,}13.
$$

Khác biệt runtime có ý nghĩa thống kê rất mạnh sau hiệu chỉnh Holm, với $p<10^{-9}$. Contextual cũng nhanh hơn trên cả ba họ instance:

| Họ instance | Contextual | Baseline | Mức giảm runtime |
|---|---:|---:|---:|
| C | 103,46 giây | 218,53 giây | 52,66% |
| R | 124,03 giây | 243,32 giây | 49,02% |
| RC | 85,74 giây | 214,68 giây | 60,06% |

Kết quả này cho thấy lợi thế tốc độ không chỉ xuất hiện ở một nhóm instance riêng lẻ.

## 4. Kết quả theo họ instance

| Họ | Số instance | Số UAV Contextual / Baseline | Objective Contextual / Baseline | Thắng / thua / hòa của Contextual |
|---|---:|---:|---:|---:|
| C | 17 | **7,118 / 7,182** | 0,45868 / **0,44713** | 78 / 80 / 12 |
| R | 23 | **8,578 / 8,587** | **0,40153 / 0,40163** | 120 / 110 / 0 |
| RC | 16 | **8,769 / 8,800** | 0,39879 / **0,39662** | 83 / 77 / 0 |

- Với họ C, Contextual dùng ít UAV hơn nhưng risk delay và objective cao hơn.
- Với họ R, hai thuật toán gần như bằng nhau về mọi chỉ số chất lượng.
- Với họ RC, Contextual dùng ít UAV hơn nhẹ và nhanh hơn nhiều.
- Không họ instance nào cho thấy một thuật toán áp đảo rõ ràng về chất lượng nghiệm.

## 5. Bằng chứng thống kê

Mỗi metric được lấy trung bình theo 10 seed trong từng instance, sau đó kiểm định trên 56 instance độc lập. Khoảng tin cậy 95% được bootstrap trên instance. Giá trị âm nghiêng về Contextual.

| Metric | Chênh lệch trung bình | Khoảng tin cậy 95% | Wilcoxon $p$ | Holm $p$ | Kết luận |
|---|---:|---:|---:|---:|---|
| Số UAV | -0,0321 | [-0,0661; +0,0018] | 0,0534 | 0,1602 | Chưa có ý nghĩa |
| Distance | +4,306 | [-1,916; +10,783] | 0,1694 | 0,2761 | Không khác biệt |
| Risk delay | +0,00529 | [-0,00036; +0,01252] | 0,1381 | 0,2761 | Không khác biệt |
| Objective | +0,00409 | [+0,00061; +0,00801] | 0,0258 | 0,1033 | Không còn ý nghĩa sau hiệu chỉnh Holm |
| Runtime | -120,76 giây | [-128,63; -112,24] | $7{,}97\times10^{-11}$ | $3{,}98\times10^{-10}$ | **Contextual nhanh hơn** |

Sau hiệu chỉnh đa kiểm định, runtime là chỉ số duy nhất khác biệt có ý nghĩa thống kê. Điều này củng cố kết luận: **lợi ích đã được chứng minh của Contextual nằm ở tốc độ, không phải ở cải thiện chất lượng nghiệm**.

## 6. Kết luận dùng trong báo cáo

> Thực nghiệm trên 56 instance Solomon, mỗi instance gồm 10 seed, cho thấy Contextual ALNS duy trì chất lượng nghiệm tương đương ALNS baseline theo tiêu chí lexicographic. Hai phương pháp có tỷ lệ thắng gần cân bằng ở cấp instance, lần lượt là 27 và 28, với 1 trường hợp hòa. Khi hai thuật toán sử dụng cùng số UAV, không ghi nhận khác biệt có ý nghĩa về distance, risk delay hoặc objective. Tuy nhiên, Contextual ALNS giảm runtime trung bình từ 227,61 xuống 106,85 giây, tương đương 53,06% và đạt hệ số tăng tốc 2,13 lần. Do đó, đóng góp chính của cơ chế contextual trong cấu hình này là nâng cao hiệu quả tính toán trong khi bảo toàn chất lượng nghiệm.

## 7. Phương pháp và khả năng tái lập

Hai bộ kết quả được ghép cặp theo `(instance, seed)` từ:

- [`benchmark/contextual_bandit/c100_r5_1000/raw.csv`](benchmark/contextual_bandit/c100_r5_1000/raw.csv);
- [`benchmark/alns/c100_r5_1000/raw.csv`](benchmark/alns/c100_r5_1000/raw.csv).

So sánh sử dụng Wilcoxon signed-rank hai phía, bootstrap percentile 95% với 20.000 mẫu và hiệu chỉnh Holm trên năm metric. Thiết kế dựa trên khuyến nghị so sánh thuật toán theo cặp trên nhiều bộ dữ liệu của [Demšar (2006)](https://www.jmlr.org/papers/v7/demsar06a.html) và hướng dẫn benchmarking của [Bartz-Beielstein và cộng sự (2020)](https://arxiv.org/abs/2007.03488).

Để phát triển kết quả này thành thực nghiệm chính thức của bài báo, nên chạy thêm seed 10–29, bổ sung đường cong nghiệm tốt nhất theo thời gian và ghi lại tần suất cùng thời gian thực thi của từng cặp destroy–repair operator.

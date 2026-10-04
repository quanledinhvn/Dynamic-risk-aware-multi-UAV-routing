# Contextual Bandit ALNS Optimization Study

## Phạm vi

Thực nghiệm dùng duy nhất instance được khai báo trong
`configs/benchmark_p1_c25_r5.json`, tức `C101`, 5 vùng rủi ro và 100 iteration.
Mặc dù tên tệp chứa `c25`, nội dung hiện tại đặt `customers` bằng 100. Các phép
so sánh giữ nguyên hàm mục tiêu, tập toán tử và acceptance policy.

## Chẩn đoán runtime

Với seed 0 trước khi tối ưu:

| Thuật toán | UAV | Objective | Runtime (giây) |
|---|---:|---:|---:|
| Baseline roulette | 12 | 0.647133 | 17.209 |
| Contextual mặc định | 11 | 0.559251 | 26.407 |

Profile contextual cho thấy `RelatedRemoval` chiếm khoảng 55 trên 58 giây khi
chạy dưới profiler. Hàm này tính lại bốn cực đại chuẩn hóa trên mọi cặp khách
hàng cho từng phép so sánh trong lúc sắp xếp. Đây là chi phí lặp thừa và không
thay đổi kết quả toán học.

Hai tối ưu được áp dụng:

1. Tính ánh xạ khách hàng, chỉ số và bốn cực đại đúng một lần trong mỗi lần gọi
   `RelatedRemoval.apply`.
2. Duy trì $A_a^{-1}$ bằng cập nhật Sherman--Morrison sau mỗi quan sát, thay vì
   giải hai hệ tuyến tính cho mỗi arm tại mỗi lần chọn.

Sau khi tối ưu, cùng seed và cùng route:

| Thuật toán | Runtime trước | Runtime sau | Tăng tốc |
|---|---:|---:|---:|
| Baseline roulette | 17.209 | 1.592 | 10.81 lần |
| Contextual mặc định | 26.407 | 1.761 | 14.99 lần |

Contextual sau tối ưu chỉ chậm hơn baseline khoảng 10.7%, thay vì 53.4%.

## Nghiên cứu chất lượng selector

Disjoint LinUCB hiện có 15 arm và 9 hệ số cho mỗi arm. Với ngân sách 100
iteration, mô hình phải ước lượng 135 hệ số từ chỉ 100 phản hồi bandit. Đây là
chế độ dữ liệu rất thưa. Lý thuyết LinUCB cũng nhấn mạnh vai trò của độ đa dạng
context đối với tốc độ học; context trong một search ngắn có tương quan mạnh
giữa progress và temperature.

Ba hướng đã được thử:

- Quét 60 tổ hợp của `context_window`, `linucb_exploration` và
  `linucb_regularization`.
- Kiểm tra cấu hình tốt nhất trên 10 seed, vẫn chỉ dùng instance C101.
- Prototype selector phân rã thành bandit destroy và bandit repair để chia sẻ
  phản hồi giữa các cặp và giảm độ thưa dữ liệu.

Trên seed 0 trong config:

| Phương án | UAV | Objective |
|---|---:|---:|
| Baseline | 12 | 0.647133 |
| Contextual mặc định: $(100, 0.5, 1.0)$ | 11 | 0.559251 |
| Contextual tuning: $(10, 1.0, 0.25)$ | 10 | 0.661775 |

Tuple trong bảng lần lượt là context window, exploration và regularization.
Objective chỉ được so sánh khi số UAV bằng nhau vì score là thứ tự từ điển.

Kiểm tra bổ sung trên seed 0--9:

| Phương án | UAV trung bình | Min--max UAV | Runtime trung bình (giây) |
|---|---:|---:|---:|
| Baseline | 11.6 | 11--12 | 1.964 |
| Contextual mặc định | 11.5 | 11--12 | 1.862 |
| Contextual tuning | 11.4 | 10--12 | 2.003 |
| Contextual phân rã, tuning | 11.3 | 11--12 | 1.956 |

Selector phân rã có trung bình tốt nhưng không thắng ổn định selector cặp đã
tuning theo so sánh từng seed, nên chưa được đưa vào code chính. Cấu hình
$(10, 1.0, 0.25)$ được ghi vào file benchmark vì đạt kết quả tốt nhất cho seed
chính và vẫn cải thiện số UAV trung bình trong kiểm tra nhiều seed. Kết quả 10
seed chỉ là kiểm tra độ nhạy, chưa đủ để tuyên bố ý nghĩa thống kê.

## Cơ sở nghiên cứu và hướng tiếp theo

Các công trình về điều khiển ALNS bằng học tăng cường cho thấy operator nên
được điều kiện hóa theo trạng thái search, nhưng thường cần huấn luyện qua nhiều
instance thay vì học lại từ đầu trong 100 bước. Nghiên cứu contextual bandit
không dừng cũng cho thấy một policy cố định có thể là đối chứng không phù hợp
khi phân phối reward thay đổi theo pha search.

- [Online Control of Adaptive Large Neighborhood Search using Deep Reinforcement Learning](https://arxiv.org/abs/2211.00759)
- [Graph Reinforcement Learning for Operator Selection in the ALNS Metaheuristic](https://arxiv.org/abs/2302.14678)
- [Efficient Contextual Bandits in Non-stationary Worlds](https://proceedings.mlr.press/v75/luo18a.html)
- [Stochastic Linear Contextual Bandits with Diverse Contexts](https://proceedings.mlr.press/v108/wu20c.html)

Hướng có tiềm năng lớn nhất tiếp theo là warm-start mô hình qua nhiều instance,
đưa kích thước phá nghiệm vào context, hoặc học prior cho từng họ operator.
Các hướng này cần benchmark 20--30 seed và nhiều instance để tránh tuning quá
mức vào C101 seed 0.

## Thực nghiệm tiếp theo: context, reward và discount

Một lưới 240 lượt chạy đã so sánh sáu tập đặc trưng, bốn mức exploration, hai
mức regularization và năm seed. Hai cấu hình tốt nhất đều bỏ temperature khỏi
context. Kiểm tra 20 seed cho kết quả:

| Phương án | UAV trung bình | Min--max UAV | Thắng baseline |
|---|---:|---:|---:|
| Baseline | 11.55 | 11--12 | -- |
| Full context, tuning | 11.40 | 10--12 | 12/20 |
| Không temperature, $(2.0, 1.0)$ | 11.20 | 11--12 | 12/20 |
| Không temperature, $(1.0, 0.25)$ | 11.30 | 11--12 | 13/20 |

Hai số trong tuple là exploration và regularization; mọi cấu hình dùng
`context_window=10`. Kiểm định dấu hai phía chưa đạt ý nghĩa thống kê ở mức
$0.05$, vì vậy kết quả này được xem là bằng chứng định hướng thay vì kết luận
cuối cùng.

Reward liên tục được thử với bốn ngưỡng chuẩn hóa mức cải thiện và hai mức
thưởng accepted-worse. Ứng viên tốt nhất trong năm seed đầu không tổng quát hóa
trên 20 seed: đạt 11.25 UAV, so với 11.20 của reward rời rạc, và thua 11 trên
19 cặp không hòa. Do đó reward gốc được giữ nguyên.

Discounted LinUCB được thử với hệ số $0.8$, $0.9$, $0.95$, $0.98$ và $0.99$.
Không hệ số nào vượt phiên bản không discount trên mười seed; tốt nhất đạt
11.3 UAV so với 11.2. Discounting không được đưa vào code.

Tùy chọn `include_temperature` được thêm vào cấu hình và provenance CSV. Giá
trị mặc định là `true` để giữ tương thích. File benchmark chính tiếp tục dùng
full context vì nó đạt 10 UAV trên seed 0 được khai báo trong file; khi đánh giá
nhiều seed, có thể đặt `include_temperature=false`, exploration bằng `2.0` và
regularization bằng `1.0` để ưu tiên độ ổn định trung bình.

## Lệnh tái lập

```bash
cd phase1
./.venv/bin/python -m uav_routing.experiment \
  --config configs/benchmark_p1_c25_r5.json \
  --algorithm contextual \
  --workers 1 \
  --output-dir results/benchmark_p1_c25_r5_contextual
```

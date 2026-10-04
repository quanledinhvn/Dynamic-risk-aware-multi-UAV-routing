# Thử nghiệm chọn macro-action bằng contextual bandit

## Câu hỏi nghiên cứu

Kiểm tra liệu contextual bandit có vượt ALNS roulette thích nghi khi hai bên
nhận cùng portfolio hành động và cùng mô hình bài toán. Các chính sách chỉ nằm
trong `experiments/contextual_policy_ablation.py`; solver mặc định không đổi.

## Thiết kế

Portfolio gồm các cặp destroy–repair có mục đích: xóa route dễ hấp thụ +
regret/greedy; related + regret; worst + greedy; risk-priority + risk regret;
random + regret. Phiên bản sau thêm `risk_relocate`: giữ nguyên số UAV và thử
chuyển tối đa hai khách có đóng góp risk delay lớn sang vị trí khả thi giúp
giảm score. Toán tử này được kiểm thử trong `tests/test_experimental.py`.

Các selector thử nghiệm:

- `roulette`: một pool adaptive cho mỗi macro-action, cập nhật mỗi 20 iteration.
- `bandit_bias`: Disjoint LinUCB chỉ có bias, kiểm soát lợi ích của context.
- `bandit_legacy`: Disjoint LinUCB dùng context chín chiều hiện tại.
- `bandit_structural`: Disjoint LinUCB dùng tiến độ, trì trệ, tỷ lệ route ngắn,
  chiều dài route ngắn nhất, proxy khả năng hấp thụ theo tải và mức tập trung
  risk delay. Proxy chỉ kiểm tra tải, không xác nhận khả thi thời gian.
- `shared_structural`: một mô hình tuyến tính chia sẻ hệ số giữa các action và
  có tương tác giữa loại action với context.
- `shared_dense`: cùng mô hình chia sẻ, thưởng 1 khi giảm UAV; khi giữ nguyên
  UAV và giảm objective, thưởng liên tục tối đa 0.5; không thưởng accepted-worse.

Các run dùng 100 khách, 5 vùng rủi ro, cùng score $(K,F)$ và acceptance gốc.
Mỗi chính sách được chạy lại từ cùng instance/seed; quỹ đạo ngẫu nhiên khác
nhau sau khi chọn action khác nhau. Thời gian tính context được tính vào runtime.

## Kết quả không có action `risk_relocate`

Sàng lọc trên C101/R101/RC101, seed 0–4, 100 iteration:

| Chính sách | UAV trung bình | Thắng/thua roulette theo $(K,F)$ | Giây trung bình |
|---|---:|---:|---:|
| Roulette | 16.00 | — | 4.00 |
| Bandit context cũ | 15.93 | 6/9 | 4.59 |
| Bandit context cấu trúc | 15.80 | 9/6 | 5.27 |
| Mô hình chia sẻ + reward liên tục | 15.67 | 5/10 | 5.09 |

Roulette 130 iteration đạt 15.87 UAV trong 5.09 giây; context cấu trúc 100
iteration thắng/thua 9/6 trong 5.27 giây. Tuy nhiên trên C103/R103/RC103,
seed 0–4, context cấu trúc thua context cũ 10/15 cặp và thua roulette 130
iteration 9/15 cặp. Cải thiện ở tập sàng lọc không tổng quát hóa.

## Oracle một bước

Trên 18 snapshot lấy từ roulette (ba instance sàng lọc, hai seed, ba mốc
iteration), thử cùng sáu macro-action hai lần mỗi snapshot. Với reward một bước
trung bình, action cố định tốt nhất đạt 0.336; chọn action tốt nhất riêng cho
từng snapshot đạt 0.384. Đây là **cận lạc quan trong mẫu** vì dùng chính kết quả
thử để chọn action, không phải chất lượng policy có thể đạt được. Hai action
xóa route đạt trung bình 0.336 và 0.335; các action khác đạt 0.065–0.161.
Điều này gợi ý portfolio hiện tại thiếu hành động chuyên biệt có lợi thế lớn
ở trạng thái khác, nhưng 18 snapshot quá ít để kết luận chung.

## Thêm action giảm risk objective

Sau khi thêm `risk_relocate`, pilot C101/R101/RC101 với ba seed cho
`shared_dense` 15.44 UAV trung bình so với roulette 16.00, nhưng chỉ thắng
5/9 cặp theo score và tốn 5.08 so với 3.99 giây. Vì vậy kiểm tra tiếp trên
C103/R103/RC103 với seed 0–19; roulette chạy 105 iteration để thời gian gần
với contextual 100 iteration.

| Chỉ số trên 60 cặp | `shared_dense` 100 | Roulette 105 |
|---|---:|---:|
| UAV trung bình | 12.267 | 12.317 |
| Runtime trung bình, giây | 4.93 | 5.30 |
| Thắng/thua theo $(K,F)$ | 29/31 | 31/29 |

Ở 55 cặp có cùng $K$, objective của `shared_dense` cao hơn roulette trung bình
0.00685. Theo từng instance: C103 thắng/thua 10/10, R103 8/12, RC103 11/9.
Không có bằng chứng rằng biến thể này thắng ALNS roulette thích nghi. Các
instance này đã được xem trong ablation trước, nên đây cũng chưa phải tập
kiểm tra hoàn toàn kín.

## Transfer prior và kích thước phá nghiệm

`experiments/warm_shared_ablation.py` cập nhật mô hình chia sẻ qua 9 run
C101/R101/RC101 (ba seed mỗi instance), lưu prior trong `shared_prior.npz`,
rồi đánh giá độc lập từng run trên C103/R103/RC103. Với seed 0–4, warm start
thắng/thua selector không warm 7/8 cặp và thắng/thua roulette 105 iteration
8/7 cặp. Không có lợi thế đủ rõ để mở rộng phép thử này.

Thử thêm hai macro-action `related_large` và `random_large` với $q\in[6,8]$.
Pilot ba seed trên C101/R101/RC101 cho `bandit_structural` thắng/thua roulette
5/4 cặp, nhưng dùng 15.89 thay vì 15.67 UAV trung bình và tốn 4.63 thay vì
3.99 giây. Không có tín hiệu để đưa $q$ lớn vào đánh giá cuối.

## Tái lập

Dữ liệu thô nằm trong `results/contextual_policy_ablation/`. Ví dụ cho phép so
60 cặp chính:

```bash
./.venv/bin/python experiments/contextual_policy_ablation.py \
  --instances c103 r103 rc103 --seeds 5 --iterations 100 \
  --policies shared_dense \
  --output results/contextual_policy_ablation/risk_action_holdout_shared_100.csv

./.venv/bin/python experiments/contextual_policy_ablation.py \
  --instances c103 r103 rc103 --seed-start 5 --seeds 15 \
  --iterations 100 --policies shared_dense \
  --output results/contextual_policy_ablation/risk_action_holdout_shared_5_19.csv

./.venv/bin/python experiments/contextual_policy_ablation.py \
  --instances c103 r103 rc103 --seeds 5 --iterations 105 \
  --policies roulette \
  --output results/contextual_policy_ablation/risk_action_holdout_roulette_105.csv

./.venv/bin/python experiments/contextual_policy_ablation.py \
  --instances c103 r103 rc103 --seed-start 5 --seeds 15 \
  --iterations 105 --policies roulette \
  --output results/contextual_policy_ablation/risk_action_holdout_roulette_5_19.csv
```

Các lượt trước khi thêm `risk_relocate` dùng cờ
`--without-risk-relocate`; script `experiments/macro_oracle_probe.py` cũng cố
định portfolio sáu action này. Transfer prior được tái lập bằng
`experiments/warm_shared_ablation.py` với tệp prior lưu trong cùng thư mục kết
quả. Log và CSV của từng lượt được giữ để phân biệt các portfolio.

## Kết luận và giới hạn

Các cách đã thử không làm contextual thắng ALNS roulette một cách tái lập.
Action mới có thể cải thiện score riêng lẻ nhưng cũng làm tăng chi phí mỗi
iteration; context cấu trúc, chia sẻ tham số, reward liên tục, transfer prior
và chọn $q$ lớn chưa có bằng chứng tổng quát hóa. Bước kế tiếp hợp lý là thiết
kế hành động có hiệu quả thật sự khác nhau theo trạng thái, rồi đo khoảng cách
oracle một bước trên nhiều snapshot độc lập hơn trước khi mở rộng mô hình học.

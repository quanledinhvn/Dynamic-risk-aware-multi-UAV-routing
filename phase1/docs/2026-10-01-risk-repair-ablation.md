# Ablation: route elimination và risk-aware regret repair

## Cơ chế thử nghiệm

Các toán tử nằm trong `src/uav_routing/experimental.py`, không thay tập toán tử
mặc định. `AbsorbableRouteRemoval` xếp route theo tỷ lệ khách có ít nhất một vị
trí chèn khả thi trên route khác, rồi ưu tiên route ngắn khi tỷ lệ bằng nhau.
`RouteEliminationRepair` chèn lại bằng regret nhưng chỉ vào route hiện hữu;
nếu không thể phục hồi nghiệm đầy đủ, trả thất bại. `RiskRegretRepair` cho phép
mở route mới. Cả hai dùng thay đổi objective của toàn bộ nghiệm sau khi chèn,
nên chi phí trễ rủi ro phát sinh cho khách phía sau đã được tính. Thứ tự chọn
khách ưu tiên ít route thay thế, regret giữa hai route, rồi mức khẩn cấp
$p_i/\max(1,l_i-e_i)$.

Đây là heuristic một bước, chưa có ejection chain hay chứng minh tối ưu.
Khả năng chèn từng khách khi xếp route là điều kiện cần, không bảo đảm cả route
có thể được hấp thụ đồng thời.

## Thiết kế thực nghiệm

Chạy `experiments/risk_repair_ablation.py` trên C101, R101, RC101, 100 khách,
5 vùng rủi ro, seed 0–9. Mỗi thuật toán nhận cùng portfolio theo chính sách;
ALNS roulette dùng `segment_length=20`. Bandit dùng window 10, exploration
1.0, regularization 0.25. Khởi tạo, score từ điển và acceptance giữ nguyên.
Chính sách `route_elimination` thay `route` destroy bằng
`absorbable_route`, thêm `route_elimination` repair. Pilot 3 seed đã thử riêng
`risk_regret` và `combined`; chúng chưa thắng ổn định nên lượt 10 seed tập trung
vào `route_elimination`. Ba instance và các seed trong pilot xuất hiện lại ở
lượt 10 seed, vì vậy đây vẫn là nghiên cứu thăm dò, không phải đánh giá held-out.

Chạy lại từ thư mục `phase1`:

```bash
./.venv/bin/python experiments/risk_repair_ablation.py \
  --seeds 10 --iterations 100 \
  --policies original route_elimination \
  --output results/risk_repair_ablation/main_10_seeds.csv

./.venv/bin/python experiments/risk_repair_ablation.py \
  --seeds 10 --iterations 200 --policies original \
  --output results/risk_repair_ablation/original_200_iterations.csv
```

## Kết quả

| Instance | Thuật toán | UAV gốc 100 | UAV mới 100 | Thắng/thua theo $(K,F)$ | Giây gốc/mới |
|---|---|---:|---:|---:|---:|
| C101 | ALNS | 11.7 | 11.0 | 9/1 | 1.76/3.15 |
| C101 | Contextual | 11.4 | 11.0 | 7/3 | 1.89/3.22 |
| R101 | ALNS | 21.2 | 19.8 | 10/0 | 1.33/2.56 |
| R101 | Contextual | 21.0 | 19.9 | 8/2 | 1.30/2.08 |
| RC101 | ALNS | 17.5 | 16.7 | 8/2 | 1.34/2.33 |
| RC101 | Contextual | 17.7 | 16.7 | 9/1 | 1.34/2.28 |

Như vậy toán tử mới thắng bản gốc ở 51/60 cặp instance–seed–thuật toán
với cùng 100 iteration. Objective $F$ chỉ được so khi $K$ bằng nhau;
không nên diễn giải trung bình $F$ giữa các nghiệm có số UAV khác nhau.

So với bản gốc chạy 200 iteration, thời gian trung bình gần hơn:

| Instance | Thuật toán | UAV mới 100 | UAV gốc 200 | Thắng/thua | Giây mới/gốc 200 |
|---|---|---:|---:|---:|---:|
| C101 | ALNS | 11.0 | 11.4 | 7/3 | 3.15/3.62 |
| C101 | Contextual | 11.0 | 11.3 | 5/5 | 3.22/3.65 |
| R101 | ALNS | 19.8 | 20.8 | 9/1 | 2.56/2.57 |
| R101 | Contextual | 19.9 | 20.7 | 8/2 | 2.08/2.48 |
| RC101 | ALNS | 16.7 | 17.2 | 7/3 | 2.33/2.68 |
| RC101 | Contextual | 16.7 | 17.3 | 7/3 | 2.28/2.68 |

So 200 với 100 iteration chỉ xấp xỉ cân bằng thời gian, không dừng từng run
tại đúng cùng số giây. Kết luận chắc nhất là neighborhood mới giúp cả hai
thuật toán trên ba instance này. Với portfolio gốc, contextual thắng ALNS ở
20/30 cặp; với portfolio mới, contextual thắng 16/30. Chưa có bằng chứng
contextual bandit khai thác toán tử mới tốt hơn roulette thích nghi.

### Tách đóng góp của hai thành phần

Thử thêm trên seed 0–4 của cùng ba instance, cùng 100 iteration. `guided_destroy`
chỉ thay `RouteRemoval` bằng `AbsorbableRouteRemoval`; `strict_repair` chỉ thêm
`RouteEliminationRepair`. Bảng dưới gộp 15 run mỗi thuật toán, vì vậy trung bình
UAV chỉ dùng để so chính sách trên cùng tập này, không mô tả một instance riêng.

| Thuật toán | Gốc | Chỉ guided destroy | Chỉ strict repair | Kết hợp |
|---|---:|---:|---:|---:|
| ALNS: UAV trung bình | 16.87 | 15.87 | 16.73 | 15.87 |
| Contextual: UAV trung bình | 16.80 | 15.80 | 16.67 | 15.80 |

`guided_destroy` thắng gốc 13/15 cặp cho cả ALNS và contextual. `strict_repair`
thắng gốc 9/15 cặp với ALNS, 7/15 với contextual. Kết hợp thắng `guided_destroy`
9/15 cặp ở ALNS nhưng chỉ 7/15 ở contextual; số UAV trung bình bằng nhau.
Do đó phần lợi ích có bằng chứng rõ nhất đến từ **chọn route dễ hấp thụ**.
Repair cấm mở route chưa chứng minh được đóng góp thêm; không nên đưa riêng
repair này vào mặc định dựa trên các số liệu hiện có.

```bash
./.venv/bin/python experiments/risk_repair_ablation.py \
  --seeds 5 --iterations 100 \
  --policies guided_destroy strict_repair \
  --output results/risk_repair_ablation/components_5_seeds.csv
```

## Giới hạn và bước kế tiếp

- Dữ liệu chỉ gồm ba instance, 10 seed và có trùng với pilot. Cần tập C/R/RC
  held-out và 20–30 seed trước khi đưa toán tử vào mặc định.
- Repair loại route có thể thất bại dù mỗi khách đều có chỗ chèn riêng. Thử
  beam search hoặc ejection chain ngắn để xử lý xung đột giữa các phép chèn.
- Đo tỷ lệ candidate khác nghiệm hiện tại, thất bại repair và cải thiện theo
  từng cặp toán tử. Chọn `route_elimination` repair có điều kiện theo destroy
  thay vì mở rộng mọi tích Descartes arm có thể giảm độ thưa của bandit.
- Muốn kết luận lợi ích của selector, chạy đối chứng thời gian bằng nhau và
  cùng portfolio trên instance chưa dùng để chọn chính sách.

# Tổng kết phần rolling horizon + ALNS (nhánh `f/hai`)

Tài liệu này tóm tắt bằng ngôn ngữ dễ hiểu những gì đã làm trên nhánh `f/hai` từ 30/09 đến 05/10/2026: xây bộ mô phỏng động, chạy benchmark, kiểm định thống kê và phân tích thành phần. Chi tiết kỹ thuật nằm trong [design spec](2026-09-30-rolling-horizon-design.md), [kế hoạch triển khai](2026-09-30-rolling-horizon-implementation-plan.md) và [báo cáo ablation](2026-10-04-ablation.md).

## 1. Bài toán, nói đơn giản

Một đội UAV xuất phát từ kho để phục vụ nhiều điểm trong vùng thiên tai. Đầu ngày ta biết một danh sách điểm cần đến. Trong ngày, tình hình thay đổi:

- có **điểm mới** xuất hiện cần phục vụ;
- **vùng nguy hiểm** mới xuất hiện hoặc dịch chuyển, làm một số điểm trở nên khẩn cấp hơn;
- **hạn chót** của một số điểm bị siết lại.

Câu hỏi: UAV nên lập lại kế hoạch như thế nào khi thông tin đến dần?

## 2. Các thuật ngữ cần biết

| Thuật ngữ | Nghĩa |
|---|---|
| **ALNS** | Thuật toán tối ưu tuyến của Pha 1. Mỗi vòng lặp (iteration) nó tháo vài điểm khỏi kế hoạch, chèn lại ở chỗ tốt hơn, và giữ kế hoạch tốt nhất tìm được. |
| **Rolling horizon** | Thay vì lập kế hoạch một lần, ta lập lại nhiều lần trong ngày. Mỗi lần lập lại gọi là một **epoch**. |
| **Khóa tiền tố (locking)** | Tại mỗi epoch, phần kế hoạch UAV đã thực sự bay thì không được đổi; chỉ phần còn lại mới được tối ưu. |
| **Warm start** | Khi lập lại, bắt đầu từ kế hoạch epoch trước và sửa dần, thay vì vẽ lại từ trang trắng. |
| **Trigger** | Quy tắc *khi nào* lập lại: theo đồng hồ (`periodic`), ngay khi có sự kiện (`event`), hoặc cả hai (`hybrid`). |
| **Độ dài epoch** | Khoảng cách giữa hai lần lập lại, tính theo tỷ lệ của cả ngày (0.05 nghĩa là 20 lần một ngày). |
| **Ngân sách mỗi epoch** | Số vòng lặp ALNS được phép chạy ở mỗi lần lập lại. |
| **Triage** | Bước chèn các điểm mới vào kế hoạch ngay khi chúng xuất hiện. Điểm nào không chèn được vào đâu thì bị đánh dấu **unserved** (không phục vụ). |
| **$F$** | Điểm số của một kế hoạch: trộn tổng quãng đường và độ trễ ở các điểm khẩn cấp. Càng thấp càng tốt. Lưu ý: $F$ **không tính** điểm bị bỏ, nên phải luôn đọc $F$ cùng số unserved. |
| **Clairvoyant** | Lời giải tham chiếu "biết trước tương lai": chạy ALNS Pha 1 một lần trên toàn bộ thông tin của cả ngày, cùng ngân sách. Không thể đạt được trong thực tế, chỉ dùng để đo khoảng cách. |
| **Gap** | Khoảng cách tương đối giữa $F$ của phương pháp và $F$ của clairvoyant, chỉ tính trên các lượt phục vụ đủ mọi điểm. |
| **Cặp (pair)** | Hai phương pháp chạy trên cùng một kịch bản và cùng seed, rồi so trực tiếp. Mọi kiểm định đều theo cặp. |
| **Wilcoxon, Holm** | Kiểm định thống kê theo cặp cho biết khác biệt có phải do may rủi không; Holm hiệu chỉnh khi so nhiều cặp cùng lúc. |

## 3. Đã xây dựng gì

Toàn bộ nằm trong `phase1/src/uav_routing/dynamic/`, cộng vài thay đổi nhỏ tương thích ngược ở lõi Pha 1 (kết quả tĩnh của Pha 1 được giữ nguyên tuyệt đối, có test snapshot bảo vệ).

1. **Kịch bản động**: định dạng JSON và bộ sinh từ dữ liệu Solomon. Điểm động lấy từ các dòng Solomon kế tiếp, nên tọa độ và cửa sổ thời gian là thật. Đã sinh 540 kịch bản: 25 khách hàng (+5, +12, +25 điểm động) và 100 khách hàng (95+5, 88+12, 75+25), mỗi loại 10 seed.
2. **Bộ mô phỏng**: đồng hồ, tiết lộ sự kiện, khóa tiền tố, chiếu kế hoạch cũ sang tình hình mới, triage, rồi gọi bộ giải.
3. **Bốn chính sách**: `greedy_insert` (chỉ chèn, không tối ưu), `cold_restart` (tối ưu lại từ đầu), `warm_alns` (tối ưu từ kế hoạch cũ, phương pháp đề xuất) và clairvoyant làm tham chiếu.
4. **Công cụ chạy**: CLI mô phỏng một kịch bản, bộ chạy benchmark song song ra CSV, và công cụ phân tích thống kê theo cặp.
5. **Tăng tốc**: sau khi gộp nhánh perf, phát hiện 94 % thời gian ở 100 khách hàng nằm trong một bảng chuẩn hóa bị tính lại liên tục; cache lại giúp mỗi vòng lặp nhanh gấp 13 lần, kết quả không đổi.

Số test: 211 → 654, tất cả xanh.

## 4. Đã chạy gì

| Bộ | Lượt mỗi chính sách | Cặp so sánh mỗi mức | Thời gian máy |
|---|---:|---:|---|
| 25 khách hàng, 3 mức động | 2 700 | 900 | 6 h 20 |
| 100 khách hàng, 3 mức động | 810 | 270 | 6 h 04 |
| Lưới sensitivity (trigger, độ dài epoch, ngân sách), 9 cấu hình | 90 | 90 | 1 h 20 |

Kết quả thô: `results/dynamic_n25_d*`, `results/dynamic_n100_d*`, `results/ablation/`; bảng đã tính: `results/analysis/`.

## 5. Kết quả chính

### 5.1. So với các cách làm đơn giản hơn trong cùng điều kiện động

- `warm_alns` tốt nhất ở mọi kích thước và mức độ động, thắng 80–92 % số cặp; mọi $p$ sau hiệu chỉnh Holm đều dưới $10^{-37}$.
- Ở 100 khách hàng, `cold_restart` **không** tốt hơn `greedy_insert` và dùng nhiều UAV hơn: 500 vòng lặp mỗi epoch không đủ để vẽ lại kế hoạch 100 điểm từ đầu. Vậy giá trị nằm ở **warm start**, không phải ở việc "có chạy lại ALNS".

### 5.2. So với clairvoyant (ALNS Pha 1 biết trước mọi thứ)

| Bộ | Gap trung vị (lượt phục vụ đủ) | Trong 10 % | Điểm bị bỏ mỗi lượt |
|---|---:|---:|---:|
| 25, +5 | 3.0 % | 75 % | 0.28 |
| 25, +25 | 10.8 % | 45 % | 1.85 |
| 100, 95+5 | 2.6 % | 79 % | 0.21 |
| 100, 75+25 | 6.0 % | 73 % | 0.74 |

Cái giá của việc không biết trước tương lai chủ yếu là **điểm bị bỏ** (cửa sổ đóng trước khi kịp biết), không phải $F$ xấu hơn.

### 5.3. Sensitivity (đổi một thiết lập, giữ nguyên phần còn lại)

| Thiết lập | Phát hiện |
|---|---|
| Trigger | Lập lại ngay khi có sự kiện giảm số điểm bị bỏ từ 0.93 xuống 0.68 mỗi lượt, tăng tỷ lệ phục vụ đủ từ 41 % lên 50 %, mà tốn **ít** tính toán hơn periodic. |
| Độ dài epoch | Lập lại thưa là thảm họa: 0.2 ngày bỏ 3.9 điểm mỗi lượt và không lượt nào phục vụ đủ. Lập lại dày gấp đôi giúp ít nhưng tốn gấp đôi thời gian. |
| Ngân sách mỗi epoch | Không đổi số điểm bị bỏ (do triage quyết định). Gấp mười ngân sách chỉ cải thiện $F$ dưới 1 %. |

Thông điệp: **thời điểm nhận thông tin** quyết định số điểm bị mất, không phải sức mạnh tìm kiếm.

## 6. Ablation theo đúng nghĩa: bỏ từng thành phần

Hệ thống đầy đủ theo kế hoạch nhóm là rolling horizon + ALNS + contextual bandit (+ NSGA-III). Ablation chuẩn là bỏ từng thành phần và đo mất mát. Mục 5.3 ở trên là **sensitivity** (đổi tham số), không phải ablation; hai thứ này hay bị gọi chung nhưng khác nhau.

| Bỏ thành phần | Chạy thay bằng | Trạng thái |
|---|---|---|
| Không bỏ gì (hệ thống đầy đủ) | rolling horizon + ALNS có contextual bandit | **chưa chạy được**: bộ giải bandit chưa nhận warm start, tiền tố khóa và $D_{\mathrm{ref}}$ chung |
| Bỏ contextual bandit | rolling horizon + ALNS roulette | **đã chạy** (`warm_alns`) |
| Bỏ warm start | lập lại từ đầu mỗi epoch | **đã chạy** (`cold_restart`) |
| Bỏ tối ưu ALNS | chỉ chèn điểm mới | **đã chạy** (`greedy_insert`) |
| Bỏ rolling horizon | một kế hoạch với toàn bộ thông tin | **đã chạy** dưới dạng clairvoyant; đây là cận trên, không phải biến thể yếu hơn |
| Bỏ toán tử risk-priority | ALNS chỉ theo quãng đường | **chưa chạy**, cần thêm cờ cấu hình |

Hai hàng liên quan bandit là quan trọng nhất cho báo cáo và đang chờ phần tích hợp của Quân. Vị trí của NSGA-III trong "hệ thống đầy đủ" cũng cần nhóm chốt: nếu nó là lớp đa mục tiêu bên ngoài thì mọi kết quả hiện tại là "đầy đủ trừ bandit trừ NSGA-III"; nếu nó là phương pháp cạnh tranh thì nó là một cột baseline, không phải một hàng ablation.

## 7. Còn lại

1. Bộ giải contextual bandit cần ba tham số như `run_alns` (`initial_solution`, `constraints`, `d_ref`), rồi đăng ký thành chính sách thứ tư. Cần quyết định giữ hay đặt lại trạng thái LinUCB giữa các epoch.
2. Cờ cấu hình cho toán tử risk-priority, đóng băng priority, latest depot departure, và `carry_weights` (đang có trong config nhưng chưa dùng).
3. Đổi tên mục 4–6 của [báo cáo ablation](2026-10-04-ablation.md) thành "Sensitivity" và thêm bảng ở mục 6 trên làm phần ablation chính thức.
4. Kiểm định theo lớp instance (C, R, RC).

## 8. Lệnh hay dùng

```bash
cd phase1
uv run pytest tests -q                                   # kiểm thử
uv run python -m uav_routing.dynamic.cli simulate \
  --scenario ../dataset/solomon_dynamic/c101-n25-d5-s0.json --policy warm_alns \
  --epoch-fraction 0.05 --iterations-epoch0 2000 --iterations-per-epoch 500 --seed 0
uv run python -m uav_routing.dynamic.experiment \
  --config configs/dynamic/benchmark_n25_d5.json --workers 16 --output-dir results/dynamic_n25_d5
uv run python -m uav_routing.dynamic.analysis \
  --results results/dynamic_n25_d5 --reference warm_alns --output results/analysis/main_policies.md
```

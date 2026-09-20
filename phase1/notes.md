Mình đã khảo sát toàn bộ `phase1`. Đây là một baseline ALNS được tổ chức khá rõ, với nguyên tắc quan trọng nhất:

> `Evaluator` là nơi duy nhất tính lịch trình, kiểm tra ràng buộc và tính hàm mục tiêu; `alns.py` chỉ điều phối quá trình tìm kiếm.

Toàn bộ 139 test hiện đều pass.

## 1. Kiến trúc tổng thể

```text
                         INPUT
          ┌─────────────────────────────────┐
          │ Solomon-RISK file               │
          │ configs/benchmark.json          │
          └───────────────┬─────────────────┘
                          │
                          v
              ┌──────────────────────┐
              │ parser.py            │
              │ geometry.py          │
              │                      │
              │ - đọc khách hàng     │
              │ - đọc vùng risk      │
              │ - ma trận khoảng cách│
              │ - risk priority      │
              └──────────┬───────────┘
                         │
                         v
              ┌──────────────────────┐
              │ models.py            │
              │                      │
              │ Instance             │
              │ Solution             │
              │ RouteEvaluation      │
              │ SolutionEvaluation   │
              └──────────┬───────────┘
                         │
             ┌───────────┴───────────────┐
             │                           │
             v                           v
   ┌───────────────────┐       ┌─────────────────────┐
   │ initial.py        │       │ evaluator.py        │
   │                   │       │                     │
   │ nghiệm tham lam   │──────>│ lịch trình          │
   │ ban đầu S₀        │       │ feasibility         │
   │ D_ref             │       │ distance/risk/score │
   └─────────┬─────────┘       └──────────┬──────────┘
             │                            │
             └──────────────┬─────────────┘
                            v
                  ┌───────────────────────┐
                  │ alns.py               │
                  │                       │
                  │ current / best        │
                  │ destroy + repair      │
                  │ acceptance            │
                  │ reward + cooling      │
                  └───────┬───────────────┘
                          │
             ┌────────────┴────────────┐
             │                         │
             v                         v
   ┌───────────────────┐     ┌──────────────────────┐
   │ cli.py            │     │ experiment.py        │
   │ một instance      │     │ instance × seed      │
   │ JSON kết quả      │     │ raw/aggregate CSV    │
   └───────────────────┘     └──────────────────────┘
```

Phần tìm kiếm bên trong ALNS:

```text
Current solution
      │
      v
AdaptivePool chọn destroy operator
      │
      v
┌────────────────────────────┐
│ destroy.py                 │
│ random / worst / related   │
│ route / risk-priority      │
└─────────────┬──────────────┘
              │
              v
 Partial solution + removed customers
              │
              v
AdaptivePool chọn repair operator
              │
              v
┌────────────────────────────┐
│ repair.py                  │
│ greedy / regret-2 /        │
│ risk-priority              │
└─────────────┬──────────────┘
              │
              v
     Complete candidate
              │
              v
         Evaluator
              │
        feasible?
         /        \
       no          yes
       │            │
    discard     acceptance
                    │
          ┌─────────┴──────────┐
          │                    │
     update current       update best
          │                    │
          └─────────┬──────────┘
                    v
          reward operator weights
                    │
                    v
              cool temperature
```

## 2. Thứ tự đọc code hiệu quả nhất

Không nên đọc theo thứ tự tên file. Mình đề xuất 4 lượt.

### Lượt 1: Hiểu bài toán và dữ liệu

Đọc theo thứ tự:

1. [README.md](/Users/ledinhquan/Hust/Dynamic%20risk-aware%20multi-UAV%20routing/phase1/README.md)
2. [models.py](/Users/ledinhquan/Hust/Dynamic%20risk-aware%20multi-UAV%20routing/phase1/src/uav_routing/models.py:13)
3. [tiny_valid.txt](/Users/ledinhquan/Hust/Dynamic%20risk-aware%20multi-UAV%20routing/phase1/tests/fixtures/tiny_valid.txt)
4. [parser.py](/Users/ledinhquan/Hust/Dynamic%20risk-aware%20multi-UAV%20routing/phase1/src/uav_routing/parser.py:15)
5. [geometry.py](/Users/ledinhquan/Hust/Dynamic%20risk-aware%20multi-UAV%20routing/phase1/src/uav_routing/geometry.py:10)

Sau lượt này, cần trả lời được:

- Một `Customer` chứa gì?
- `Instance` được xây từ file như thế nào?
- Vì sao ma trận khoảng cách có kích thước \(n+1\)?
- Vị trí 0 trong ma trận biểu diễn depot như thế nào?
- Risk priority được tính ra sao?

Lưu ý: customer ID không nhất thiết bằng index trong ma trận. Code tạo ánh xạ riêng từ ID sang index.

## 3. Lượt 2: Hiểu “trọng tài” của hệ thống

Đọc [evaluator.py](/Users/ledinhquan/Hust/Dynamic%20risk-aware%20multi-UAV%20routing/phase1/src/uav_routing/evaluator.py:15) thật kỹ.

Đây là file quan trọng nhất của Phase 1.

### `Evaluator.route()`

Với route:

```text
(3, 7, 2)
```

code hiểu là:

```text
depot -> 3 -> 7 -> 2 -> depot
```

Tại mỗi khách hàng:

```text
arrival
   = departure trước + khoảng cách

service_start
   = max(arrival, ready_time)

departure
   = service_start + service_time
```

Sau đó kiểm tra:

- Bắt đầu phục vụ có quá due date không?
- Tổng demand có vượt capacity không?
- UAV có về depot trước hạn không?

### `Evaluator.solution()`

Phương thức này kiểm tra thêm:

- Có vượt số UAV tối đa không?
- Có khách hàng bị phục vụ hai lần không?
- Có thiếu khách hàng không?
- Có ID không tồn tại không?
- Mọi route có khả thi không?

Sau đó tính:

```text
score = (vehicle_count, objective)
```

Đây là so sánh từ điển. Ví dụ:

```text
(3 UAV, objective 0.90) tốt hơn (4 UAV, objective 0.20)
```

Số UAV luôn được ưu tiên trước objective.

Objective là:

\[
F(S)=\alpha\frac{D(S)}{D_{\mathrm{ref}}}+\beta R(S)
\]

Một chi tiết tinh tế: evaluator vẫn tính distance, risk delay và objective cho partial solution, dù nó báo `missing_customers`. `repair.py` dùng các giá trị số này để so sánh vị trí chèn; chỉ candidate hoàn chỉnh cuối cùng mới bắt buộc `feasible=True`.

Nên đọc kèm [test_evaluator.py](/Users/ledinhquan/Hust/Dynamic%20risk-aware%20multi-UAV%20routing/phase1/tests/test_evaluator.py). Các test ngắn hơn code và thể hiện rất rõ hợp đồng mong muốn.

## 4. Lượt 3: Hiểu cách tạo và biến đổi nghiệm

### Nghiệm ban đầu

Đọc [initial.py](/Users/ledinhquan/Hust/Dynamic%20risk-aware%20multi-UAV%20routing/phase1/src/uav_routing/initial.py:11).

Khách hàng được sắp theo:

```text
due date tăng
→ risk priority giảm
→ customer ID tăng
```

Sau đó lần lượt:

```text
thử chèn vào mọi vị trí của mọi route
        │
        ├─ có vị trí khả thi → chọn mức tăng distance nhỏ nhất
        │
        └─ không có          → mở route mới
```

Khoảng cách của nghiệm tham lam trở thành \(D_{\mathrm{ref}}\). Nó chỉ dùng để chuẩn hóa distance, không phải nghiệm tối ưu.

### Repair trước, destroy sau

Nên đọc [repair.py](/Users/ledinhquan/Hust/Dynamic%20risk-aware%20multi-UAV%20routing/phase1/src/uav_routing/repair.py:44) trước `destroy.py`, vì repair chứa insertion engine — phần cốt lõi nhất của neighborhood.

Mỗi lựa chọn chèn có:

```text
Insertion
├── customer_id
├── route_index
├── position
├── delta_k       # thay đổi số UAV
├── delta_f       # thay đổi objective
└── solution      # nghiệm sau khi chèn
```

Các vị trí được sắp theo:

```text
(delta_k, delta_f, route_index, position)
```

Vì vậy:

```text
chèn vào route hiện tại: delta_k = 0
mở route mới:            delta_k = 1
```

Solver luôn ưu tiên tận dụng route hiện có trước khi mở thêm UAV.

Ba repair operator:

- `GreedyRepair`: chọn cặp khách hàng–vị trí có chi phí tốt nhất toàn cục.
- `Regret2Repair`: ưu tiên khách hàng sẽ “thiệt” nhiều nhất nếu bỏ lỡ vị trí tốt nhất.
- `RiskPriorityRepair`: chèn khách hàng có risk priority cao trước.

Sau đó đọc [destroy.py](/Users/ledinhquan/Hust/Dynamic%20risk-aware%20multi-UAV%20routing/phase1/src/uav_routing/destroy.py:100):

- `RandomRemoval`: tháo ngẫu nhiên.
- `WorstRemoval`: tháo khách hàng đóng góp chi phí lớn.
- `RelatedRemoval`: tháo nhóm khách hàng tương tự nhau.
- `RouteRemoval`: tháo toàn bộ một route để tạo cơ hội giảm UAV.
- `RiskPriorityRemoval`: tháo các khách hàng priority cao để sắp xếp lại sớm hơn.

## 5. Lượt 4: Đọc vòng lặp ALNS

Đi thẳng tới [`_run_alns()`](/Users/ledinhquan/Hust/Dynamic%20risk-aware%20multi-UAV%20routing/phase1/src/uav_routing/alns.py:116).

Mỗi vòng lặp thực hiện:

```text
1. Lấy q trong [q_min, q_max]
2. Roulette chọn một destroy
3. Roulette chọn một repair
4. Destroy current solution
5. Repair partial solution
6. Evaluator kiểm tra candidate
7. Acceptance quyết định nhận hay bỏ
8. Cập nhật best solution
9. Thưởng destroy và repair đã dùng
10. Định kỳ cập nhật trọng số
11. Giảm temperature
```

Acceptance ở [alns.py:72](/Users/ledinhquan/Hust/Dynamic%20risk-aware%20multi-UAV%20routing/phase1/src/uav_routing/alns.py:72):

```text
candidate ít UAV hơn    → luôn nhận
candidate nhiều UAV hơn → luôn loại
cùng số UAV:
    objective tốt hơn   → nhận
    objective bằng      → nhận
    objective xấu hơn   → nhận theo xác suất SA
```

Simulated Annealing chỉ cho phép tạm thời xấu hơn về objective, không bao giờ xấu hơn về số UAV.

Đọc tiếp [adaptive.py](/Users/ledinhquan/Hust/Dynamic%20risk-aware%20multi-UAV%20routing/phase1/src/uav_routing/adaptive.py:17) để hiểu cách operator tốt được tăng xác suất lựa chọn.

## 6. Hai entry point

### Giải một instance

Luồng bắt đầu tại [cli.py:68](/Users/ledinhquan/Hust/Dynamic%20risk-aware%20multi-UAV%20routing/phase1/src/uav_routing/cli.py:68):

```text
CLI arguments
  → ALNSConfig
  → parse_instance()
  → run_alns()
  → result_to_dict()
  → JSON
```

### Chạy benchmark

Luồng bắt đầu tại [experiment.py:104](/Users/ledinhquan/Hust/Dynamic%20risk-aware%20multi-UAV%20routing/phase1/src/uav_routing/experiment.py:104):

```text
benchmark.json
    │
    v
mọi instance × mọi seed
    │
    v
solve từng lần
    │
    ├─ checkpoint raw.csv
    └─ checkpoint aggregate.csv
```

## 7. Hiểu hai file cấu hình đang mở

[default.json](/Users/ledinhquan/Hust/Dynamic%20risk-aware%20multi-UAV%20routing/phase1/configs/default.json) mô tả đầy đủ tham số ALNS, nhưng hiện chưa có code nào trực tiếp đọc file này.

CLI chỉ nhận:

```text
iterations, seed, alpha, beta
```

Các tham số còn lại lấy default từ `ALNSConfig`.

[benchmark.json](/Users/ledinhquan/Hust/Dynamic%20risk-aware%20multi-UAV%20routing/phase1/configs/benchmark.json) được `experiment.py` đọc trực tiếp và chứa:

```text
instances
seeds
customers
alns
```

## 8. Cách đọc thực hành trong IDE

Đặt breakpoint tại các vị trí sau:

1. `cli.py:89` — sau khi parse instance.
2. `alns.py:126` — sau khi tạo nghiệm ban đầu.
3. `alns.py:164` — đầu một iteration.
4. `alns.py:168` — trước destroy.
5. `alns.py:171` — trước repair.
6. `alns.py:177` — đánh giá candidate.
7. `alns.py:179` — acceptance.
8. `alns.py:192` — cập nhật best.

Chạy chỉ 2–5 iterations để quan sát:

```bash
cd phase1

uv run python -m uav_routing.cli solve \
  --instance ../dataset/solomon_risk/c101.txt \
  --customers 25 \
  --iterations 5 \
  --seed 42
```

Trong debugger, theo dõi:

```text
current.routes
destroyed.removed
destroyed.partial.routes
repaired.solution.routes
current_evaluation.score
candidate_evaluation.score
best_evaluation.score
temperature
reward
```

Nếu chỉ có khoảng một giờ để đọc, ưu tiên theo thứ tự:

```text
models.py
→ evaluator.py
→ initial.py
→ repair.py
→ alns.py::_run_alns
→ destroy.py
→ adaptive.py
→ cli.py / experiment.py
```

Đó là đường ngắn nhất để hiểu logic thuật toán thay vì sa vào chi tiết parser và xuất file.
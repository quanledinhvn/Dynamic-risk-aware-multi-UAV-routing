# Thiết kế Contextual Bandit cho ALNS

## 1. Mục tiêu và câu hỏi nghiên cứu

Xây dựng một phiên bản Contextual Bandit ALNS riêng để chọn cặp destroy--repair
theo trạng thái tìm kiếm hiện tại. Baseline roulette trong `alns.py` và
`adaptive.py` tiếp tục là phiên bản mặc định và giữ nguyên public API để làm đối
chứng.

Câu hỏi nghiên cứu chính là:

> Với cùng ngân sách iteration, việc chọn cặp destroy--repair bằng Contextual
> Bandit có cải thiện chất lượng nghiệm của ALNS mà không tạo overhead runtime
> quá lớn so với roulette adaptive truyền thống trong bài toán risk-aware
> multi-UAV routing hay không?

Phiên bản đầu chỉ triển khai Disjoint LinUCB cho bài toán tĩnh của Pha 1. Việc
chọn kích thước phá nghiệm $q$, discounted learning cho dữ liệu động, continuous
reward và huấn luyện chung qua nhiều instance không thuộc phạm vi triển khai
đầu tiên.

## 2. Nguyên tắc thiết kế

- Mỗi arm là một cặp `(destroy_name, repair_name)` hợp lệ.
- Với năm destroy và ba repair hiện có, selector mặc định có 15 arms.
- Context chỉ chứa thông tin có sẵn trước khi chọn arm.
- Reward chỉ được tính sau khi candidate đã được repair, đánh giá và quyết định
  acceptance.
- Roulette và LinUCB dùng chung operator, evaluator, acceptance policy, cooling
  schedule, reward classification và stopping condition.
- Baseline tiếp tục chạy qua `run_alns`; phiên bản mới chạy qua
  `run_contextual_alns` trong package `contextual`.
- Không đặt LinUCB, context history hoặc contextual solver trong các module
  baseline.
- Không thêm dependency machine-learning; LinUCB chỉ dùng NumPy.
- Mọi lựa chọn ngẫu nhiên, kể cả phá hòa giữa các arm có cùng điểm, dùng
  `numpy.random.Generator` đã được truyền vào ALNS.
- Cùng instance, cấu hình và seed phải tái lập route, metric và thống kê
  selector; runtime không cần giống nhau.
- Thuật ngữ `vehicle` tiếp tục được dùng trong code lõi VRPTW; `UAV` được dùng
  trong tài liệu nghiệp vụ.

## 3. Action space

Một action là:

$$
a=(d_i,r_j),
$$

trong đó $d_i$ là destroy operator và $r_j$ là repair operator. Danh sách arm
được tạo theo thứ tự Cartesian product ổn định của danh sách destroy rồi danh
sách repair. Tên arm trong output có dạng `destroy_name+repair_name`.

Chọn nguyên cặp thay vì hai bandit độc lập để mô hình học trực tiếp tương tác
giữa destroy và repair, đồng thời tránh gán cùng một reward cho hai quyết định
độc lập như baseline hiện tại.

Kích thước phá nghiệm $q$ vẫn được lấy đều từ đoạn cấu hình
`[q_min, q_max]`. Giữ quyết định này ngoài action space giúp giới hạn số arm và
cô lập ảnh hưởng của cơ chế chọn operator trong ablation đầu tiên.

## 4. Context vector

Context có đúng chín chiều và được tạo trước khi chọn arm:

$$
x_t=[
1,
p_t,
\tau_t,
s_t,
a_t,
i_t,
g^K_t,
g^F_t,
R(S_t)
].
$$

Các thành phần là:

1. `bias`: hằng số $1$.
2. `progress`: với iteration đánh số từ $0$, dùng
   $p_t=t/\max(1,T-1)$.
3. `temperature`: nhiệt độ logarithmic chuẩn hóa về $[0,1]$:

   $$
   \tau_t=
   \frac{\log(T_t/T_{\min})}
        {\log(T_0/T_{\min})}.
   $$

   Kết quả được clip về $[0,1]$. Nếu $T_0=T_{\min}$, quy ước
   $\tau_t=1$.
4. `stagnation`: số iteration kể từ best-so-far gần nhất chia cho
   `context_window`, sau đó clip về $[0,1]$.
5. `acceptance_rate`: tỷ lệ candidate được chấp nhận trong tối đa
   `context_window` iteration gần nhất; bằng $0$ khi chưa có lịch sử.
6. `improvement_rate`: tỷ lệ candidate tốt hơn current được dùng ở đầu
   iteration tương ứng, trong cùng cửa sổ; bằng $0$ khi chưa có lịch sử.
7. `vehicle_gap`: khoảng cách số vehicle giữa current và best:

   $$
   g^K_t=
   \frac{\max(0,K(S_t)-K(S_{best}))}
        {\max(1,K_{max})}.
   $$

8. `objective_gap`: nếu current và best có cùng số vehicle:

   $$
   g^F_t=
   \min\left(
   1,
   \frac{\max(0,F(S_t)-F(S_{best}))}
        {\max(|F(S_{best})|,10^{-12})}
   \right).
   $$

   Nếu số vehicle khác nhau, quy ước $g^F_t=0$ để không trộn hai tầng của
   objective từ điển.
9. `risk_delay`: $R(S_t)$ của current solution, đã nằm trong $[0,1]$ đối với
   nghiệm khả thi.

Mọi phần tử context phải hữu hạn. Context extractor từ chối vector sai kích
thước hoặc chứa `NaN`/vô cực thay vì truyền dữ liệu lỗi vào selector.

Các đặc trưng cố định như số customer và số risk zone không được đưa vào phiên
bản đầu vì bandit được khởi tạo mới cho mỗi lần chạy; chúng không thay đổi giữa
các iteration của cùng một run.

## 5. Search history

`SearchHistory` là state mutable riêng, không đặt trong các domain dataclass bất
biến. Nó lưu:

- số iteration kể từ best-so-far gần nhất;
- cửa sổ boolean candidate được accepted;
- cửa sổ boolean candidate cải thiện current trước action;
- tổng số iteration đã ghi nhận.

Sau mỗi iteration:

- nếu candidate tạo best-so-far mới, stagnation đặt về $0$;
- nếu không, stagnation tăng một;
- repair thất bại hoặc candidate không khả thi ghi `False` cho accepted và
  improved;
- accepted-worse ghi `True` cho accepted và `False` cho improved;
- cửa sổ không vượt `context_window`.

Context của iteration $t$ chỉ dùng history kết thúc ở iteration $t-1$.

## 6. Disjoint LinUCB

Mỗi arm $a$ có ma trận $A_a$ và vector $b_a$ riêng. Khởi tạo:

$$
A_a=\lambda I,
\qquad
b_a=0,
$$

trong đó `linucb_regularization` là $\lambda>0$.

Tại một context $x_t$, selector tính:

$$
\hat\theta_a=A_a^{-1}b_a,
$$

$$
u_{t,a}=
x_t^T\hat\theta_a+
\alpha_{ucb}\sqrt{x_t^TA_a^{-1}x_t}.
$$

Arm có $u_{t,a}$ lớn nhất được chọn. `numpy.linalg.solve` được dùng thay cho
nghịch đảo ma trận trực tiếp. Các arm có điểm bằng nhau trong dung sai số học
được phá hòa bằng RNG của solver.

Sau khi nhận reward $r_t$:

$$
A_a\leftarrow A_a+x_tx_t^T,
$$

$$
b_a\leftarrow b_a+r_tx_t.
$$

Chỉ arm đã chọn được cập nhật. `linucb_exploration` phải không âm và
`linucb_regularization` phải dương.

## 7. Reward

Outcome classification của baseline được giữ nguyên:

- `reward_best` nếu tạo best-so-far mới;
- `reward_improve` nếu tốt hơn current nhưng không tốt hơn best;
- `reward_accepted` nếu candidate xấu hơn được chấp nhận;
- `0` nếu equal, rejected, repair thất bại hoặc candidate không khả thi.

Roulette tiếp tục nhận raw reward để bảo toàn hành vi baseline. LinUCB nhận
reward chuẩn hóa:

$$
r_t=
\frac{r^{raw}_t}
     {\max(\text{reward\_best},
           \text{reward\_improve},
           \text{reward\_accepted})}.
$$

Với cấu hình mặc định, các mức là $1$, $0.5$, $0.1$ và $0$. Khi dùng LinUCB,
ít nhất một mức reward phải dương; mọi mức phải không âm. Việc giữ reward cũ
giúp ablation đầu tiên chỉ thay selection policy.

## 8. Tách biệt baseline và contextual ALNS

Baseline giữ nguyên vị trí và entry point hiện tại:

```text
src/uav_routing/
├── adaptive.py
└── alns.py
```

- `adaptive.py` tiếp tục chứa `AdaptivePool` và `OperatorStats`.
- `alns.py` tiếp tục chứa `ALNSSolver` và `run_alns`.
- Không thêm context, LinUCB hoặc pair selector vào hai module này.
- Lệnh không chỉ định algorithm phải chạy đúng baseline hiện tại.

Toàn bộ phần mới nằm trong package riêng:

```text
src/uav_routing/contextual/
├── __init__.py
├── config.py
├── context.py
├── linucb.py
├── selector.py
└── alns.py
```

Trách nhiệm từng module:

- `config.py`: `ContextualBanditConfig` và validation cho hyperparameter.
- `context.py`: `SearchHistory`, chuẩn hóa feature và tạo context vector.
- `linucb.py`: thuật toán `DisjointLinUCB` không phụ thuộc ALNS.
- `selector.py`: ánh xạ Cartesian product destroy--repair thành arm, chuẩn hóa
  reward và thống kê arm.
- `alns.py`: `ContextualALNSSolver`, contextual search loop và
  `run_contextual_alns`.
- `__init__.py`: export public API của phiên bản contextual.

### 8.1. Cấu trúc thư mục đầy đủ sau khi triển khai

```text
phase1/
├── configs/
│   ├── default.json                         # baseline hiện có
│   ├── benchmark.json                       # baseline hiện có
│   └── contextual/
│       └── benchmark.json                   # contextual benchmark mới
├── docs/
│   ├── 2026-09-19-alns-baseline-design.md
│   ├── 2026-09-20-alns-baseline-implementation-plan.md
│   ├── 2026-09-27-contextual-bandit-alns-design.md
│   └── 2026-09-27-contextual-bandit-implementation-plan.md
├── src/uav_routing/
│   ├── __init__.py
│   ├── adaptive.py                          # baseline giữ nguyên
│   ├── alns.py                              # baseline giữ nguyên
│   ├── cli.py                               # dispatch theo --algorithm
│   ├── config.py                            # ALNSConfig baseline giữ nguyên
│   ├── destroy.py
│   ├── evaluator.py
│   ├── experiment.py                        # dispatch benchmark
│   ├── geometry.py
│   ├── initial.py
│   ├── models.py
│   ├── parser.py
│   ├── repair.py
│   └── contextual/
│       ├── __init__.py
│       ├── alns.py
│       ├── config.py
│       ├── context.py
│       ├── linucb.py
│       └── selector.py
├── tests/
│   ├── contextual/
│   │   ├── test_alns.py
│   │   ├── test_config.py
│   │   ├── test_context.py
│   │   ├── test_linucb.py
│   │   └── test_selector.py
│   ├── test_alns.py                         # baseline tests hiện có
│   ├── test_cli.py
│   ├── test_experiment.py
│   └── test_integration.py
├── results/                                 # generated, không phải source
│   ├── baseline/
│   └── contextual/
└── README.md
```

Không chuyển hoặc đổi tên các module baseline hiện có. Test contextual nằm
trong thư mục riêng; các integration test chung tiếp tục nằm ở `tests/`.

Contextual solver dùng lại `Instance`, `Solution`, operator, `Evaluator`,
`build_initial_solution`, `accept_score`, `classify_reward` và
`cool_temperature` hiện có. Nó không sao chép cách tính objective, feasibility,
acceptance hoặc reward classification. Vòng orchestration của contextual solver
được đặt riêng vì có thêm context extraction, history update và cập nhật bandit.

Public API của package mới là:

```python
class ContextualALNSSolver:
    def __init__(
        self,
        instance: Instance,
        alns_config: ALNSConfig,
        bandit_config: ContextualBanditConfig,
    ): ...

    def run(self) -> ContextualSearchResult: ...

def run_contextual_alns(
    instance: Instance,
    alns_config: ALNSConfig,
    bandit_config: ContextualBanditConfig | None = None,
) -> ContextualSearchResult: ...
```

`selector.py` dùng `OperatorPair = tuple[str, str]`. Mỗi contextual run tích lũy
`PairSelectionStats` gồm:

- `destroy_name`;
- `repair_name`;
- `total_uses`;
- `total_raw_reward`;
- `average_raw_reward`.

`SearchResult` của baseline không thay đổi. `ContextualSearchResult` chứa các
trường nghiệm và evaluation tương ứng, đồng thời thay `operator_stats` bằng
`pair_selection_stats` để output phản ánh đúng action space của LinUCB.

## 9. Luồng một iteration

Chỉ contextual ALNS thực hiện luồng sau:

1. Tạo context từ state và history trước iteration.
2. Lấy $q$ ngẫu nhiên như baseline.
3. Selector chọn một cặp destroy--repair.
4. Chạy destroy và repair.
5. Đánh giá candidate, acceptance và reward như baseline.
6. Cập nhật current và best nếu phù hợp.
7. Ghi arm, context và reward vào selector.
8. Cập nhật search history từ outcome.
9. Giảm nhiệt độ.

Thứ tự lấy $q$ trước khi selector chọn operator giữ cùng vị trí logic với
baseline. Baseline search loop không bị thay thế bởi luồng này.

Kết quả nội bộ của bước 5 phải được biểu diễn bằng một record thay vì chỉ trả
`float`, để reward, accepted, improved và new-best được dùng nhất quán bởi
selector và history.

## 10. Cấu hình

`ALNSConfig` và các file cấu hình baseline hiện có không bổ sung field
Contextual Bandit. Package mới định nghĩa:

```text
context_window = 100
linucb_exploration = 0.5
linucb_regularization = 1.0
```

Validation:

- `context_window` là số nguyên dương, không nhận `bool`;
- `linucb_exploration` hữu hạn và không âm;
- `linucb_regularization` hữu hạn và dương;
- reward lớn nhất trong `ALNSConfig` phải dương khi chạy contextual ALNS.

CLI `solve` và benchmark bổ sung:

```text
--algorithm baseline|contextual
```

Giá trị mặc định là `baseline`. CLI dispatch trực tiếp tới `run_alns` hoặc
`run_contextual_alns`; không truyền selector vào baseline solver.

Quy tắc chọn algorithm theo thứ tự ưu tiên:

1. Giá trị `--algorithm` trên command line, nếu có.
2. Khóa `algorithm` trong benchmark config, nếu có.
3. `baseline` nếu cả hai đều không có.

Các config benchmark hiện có không cần thêm khóa và tiếp tục chạy baseline. Một
config mới `configs/contextual/benchmark.json` chứa cùng ALNS parameter cùng
khối `contextual_bandit` cho ba hyperparameter trên. Benchmark config không có
`algorithm` được hiểu là `baseline`; config contextual phải khai báo
`"algorithm": "contextual"`.

Ví dụ config contextual tối thiểu hợp lệ:

```json
{
  "algorithm": "contextual",
  "instances": [
    "../dataset/solomon_risk/c101.txt"
  ],
  "seeds": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
  "customers": 25,
  "risks": 5,
  "alns": {
    "iterations": 10000,
    "seed": 0,
    "alpha": 0.5,
    "beta": 0.5
  },
  "contextual_bandit": {
    "context_window": 100,
    "linucb_exploration": 0.5,
    "linucb_regularization": 1.0
  }
}
```

## 11. Output và benchmark

### 11.1. Chạy CLI cho một instance

Không truyền `--algorithm` vẫn chạy baseline:

```bash
uv run python -m uav_routing.cli solve \
  --instance ../dataset/solomon_risk/c101.txt \
  --customers 25 \
  --risks 5 \
  --iterations 10000 \
  --seed 42 \
  --output results/baseline/c101-seed42.json
```

Có thể ghi rõ baseline:

```bash
uv run python -m uav_routing.cli solve \
  --algorithm baseline \
  --instance ../dataset/solomon_risk/c101.txt \
  --customers 25 \
  --risks 5 \
  --iterations 10000 \
  --seed 42 \
  --output results/baseline/c101-seed42.json
```

Chạy contextual ALNS:

```bash
uv run python -m uav_routing.cli solve \
  --algorithm contextual \
  --instance ../dataset/solomon_risk/c101.txt \
  --customers 25 \
  --risks 5 \
  --iterations 10000 \
  --seed 42 \
  --output results/contextual/c101-seed42.json
```

`stdout` vẫn in một JSON object; thông báo tiến trình chỉ đi vào `stderr` như
baseline hiện tại.

JSON dùng schema chung. Baseline có `contextual_bandit=null`, giữ thống kê
roulette trong `operators` và để `pair_selection_stats` rỗng:

```json
{
  "algorithm": "baseline",
  "instance": "c101",
  "customers": 25,
  "risks": 5,
  "seed": 42,
  "iterations": 10000,
  "alpha": 0.5,
  "beta": 0.5,
  "vehicles": 3,
  "distance": 321.5,
  "risk_delay": 0.18,
  "objective": 0.61,
  "runtime_seconds": 2.4,
  "feasible": true,
  "contextual_bandit": null,
  "operators": [
    {
      "name": "destroy:random",
      "weight": 4.2,
      "total_uses": 1960,
      "segment_uses": 0,
      "segment_score": 0.0
    }
  ],
  "pair_selection_stats": [],
  "routes": []
}
```

Contextual ALNS có cấu hình bandit, để `operators` rỗng và báo thống kê theo
cặp arm:

```json
{
  "algorithm": "contextual",
  "instance": "c101",
  "customers": 25,
  "risks": 5,
  "seed": 42,
  "iterations": 10000,
  "alpha": 0.5,
  "beta": 0.5,
  "vehicles": 3,
  "distance": 315.2,
  "risk_delay": 0.15,
  "objective": 0.57,
  "runtime_seconds": 2.8,
  "feasible": true,
  "contextual_bandit": {
    "context_window": 100,
    "linucb_exploration": 0.5,
    "linucb_regularization": 1.0
  },
  "operators": [],
  "pair_selection_stats": [
    {
      "destroy_name": "random",
      "repair_name": "greedy",
      "total_uses": 620,
      "total_raw_reward": 840.0,
      "average_raw_reward": 1.3548387097
    }
  ],
  "routes": []
}
```

Các số trong hai ví dụ chỉ minh họa schema, không phải expected benchmark.
Trường `routes` thực tế giữ nguyên cấu trúc route và schedule đầy đủ của
baseline.

### 11.2. Chạy benchmark

Baseline, tương thích config hiện có:

```bash
uv run python -m uav_routing.experiment \
  --config configs/benchmark.json \
  --algorithm baseline \
  --workers 8 \
  --output-dir results/baseline/benchmark
```

Contextual ALNS:

```bash
uv run python -m uav_routing.experiment \
  --config configs/contextual/benchmark.json \
  --algorithm contextual \
  --workers 8 \
  --output-dir results/contextual/benchmark
```

Với config contextual, có thể bỏ `--algorithm contextual` vì khóa trong config
đã chọn đúng algorithm. Nếu command line và config khác nhau, command line
thắng.

Khi hoàn tất, benchmark in một dòng ra `stdout`:

```text
completed 10 runs; algorithm=contextual; raw=results/contextual/benchmark/raw.csv; aggregate=results/contextual/benchmark/aggregate.csv
```

Mỗi output directory chứa:

```text
results/<algorithm>/benchmark/
├── raw.csv
└── aggregate.csv
```

`raw.csv` có schema ổn định:

```text
instance,customers,risks,algorithm,seed,iterations,alpha,beta,
context_window,linucb_exploration,linucb_regularization,
vehicles,distance,risk_delay,objective,runtime_seconds,feasible,routes
```

`aggregate.csv` nhóm theo instance, kích thước bài toán, algorithm, ngân sách,
objective weights và hyperparameter bandit:

```text
instance,customers,risks,algorithm,iterations,alpha,beta,
context_window,linucb_exploration,linucb_regularization,runs,
vehicles_mean,vehicles_std,vehicles_best,vehicles_worst,
distance_mean,distance_std,distance_best,distance_worst,
risk_delay_mean,risk_delay_std,risk_delay_best,risk_delay_worst,
objective_mean,objective_std,objective_best,objective_worst,
runtime_mean,runtime_std
```

Với baseline, ba cột hyperparameter bandit để trống. Với contextual, chúng chứa
giá trị thực và là một phần của grouping key để các cấu hình LinUCB khác nhau
không bị trộn.

### 11.3. Hợp đồng output

JSON của một lần solve luôn có:

- `algorithm`, nhận `baseline` hoặc `contextual`;
- `contextual_bandit`, là `null` với baseline;
- `operators`, chỉ có dữ liệu với baseline;
- `pair_selection_stats`, chỉ có dữ liệu với contextual;
- các metric và `routes` hiện có.

Pair statistics chỉ được lưu trong JSON solve, không nhúng vào CSV benchmark.
CLI và benchmark không tự động trộn kết quả của hai algorithm vào cùng output
directory; tài liệu và config mặc định luôn dùng hai đường dẫn riêng.

## 12. Kiểm thử và tiêu chí nghiệm thu

Kiểm thử được phát triển theo TDD và tuân theo quy tắc skeleton của dự án.

### Unit tests

- Context có đúng thứ tự chín feature, finite và đúng các trường hợp biên.
- History không vượt window và cập nhật đúng failed, rejected, improved,
  accepted-worse và new-best.
- LinUCB khởi tạo đúng regularization, chọn theo exploitation/uncertainty, chỉ
  cập nhật arm được chọn và phá hòa tái lập bằng RNG.
- Contextual config từ chối hyperparameter không hợp lệ mà không thay đổi
  validation của `ALNSConfig` baseline.

### Integration tests

- `run_alns` bảo toàn deterministic baseline hiện tại.
- `run_contextual_alns` chạy end-to-end, trả nghiệm hoàn chỉnh và khả thi.
- Hai lần chạy LinUCB cùng instance, config và seed cho cùng route, evaluation
  và selection statistics.
- Tổng `total_uses` của pair statistics bằng số iteration.
- Không truyền `--algorithm` chạy baseline; `--algorithm contextual` chạy
  contextual solver.
- CLI từ chối algorithm không thuộc `baseline|contextual` và giữ stdout là JSON
  hợp lệ cho cả hai phiên bản.
- Baseline JSON có `contextual_bandit=null` và pair stats rỗng; contextual JSON
  có bandit config, `operators` rỗng và đủ 15 pair stats.
- Benchmark CLI override khóa algorithm trong config; config không có algorithm
  mặc định về baseline.
- Header CSV đúng schema đã đặc tả; aggregate không gộp hai algorithm hoặc hai
  bộ hyperparameter LinUCB khác nhau.

### Definition of done

- Toàn bộ test hiện có tiếp tục pass.
- Không có dependency mới ngoài NumPy.
- `run_alns`, `ALNSSolver`, `SearchResult` và baseline config giữ nguyên API.
- Baseline vẫn là algorithm mặc định.
- Contextual ALNS chỉ được bật qua `--algorithm contextual`, contextual config
  hoặc gọi trực tiếp `run_contextual_alns`.
- Cả hai phiên bản dùng cùng operator, evaluator, reward classification,
  acceptance và stopping condition.
- README mô tả context, action, reward, lệnh chạy và giới hạn của phiên bản
  tĩnh.

## 13. Ngoài phạm vi

- Context chứa event động, pin, nhiệm vụ mới hoặc risk-map delta.
- Discounted hoặc sliding-window LinUCB.
- Chọn $q$, cooling rate hoặc acceptance policy bằng bandit.
- Continuous/delayed reward và deep reinforcement learning.
- Huấn luyện chung hoặc chuyển mô hình giữa các instance.
- Thay đổi objective, destroy operator hoặc repair operator hiện có.

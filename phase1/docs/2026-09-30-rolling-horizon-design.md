# Thiết kế Rolling Horizon cho Pha 2

## 1. Mục tiêu và câu hỏi nghiên cứu

Pha 2 mở rộng baseline ALNS tĩnh của Pha 1 thành một bộ giải **động** theo cơ chế rolling horizon: mô phỏng thời gian trôi, tiết lộ dần các sự kiện (nhiệm vụ mới, vùng risk thay đổi, deadline bị siết) và tái tối ưu phần kế hoạch chưa thực hiện tại mỗi epoch, trong khi giữ nguyên phần tuyến mà các UAV đã cam kết.

Câu hỏi nghiên cứu chính:

> Với cùng ngân sách tính toán, tái tối ưu rolling horizon bằng ALNS có warm start và khóa tiền tố tuyến cho kết quả thực hiện (realized) tốt hơn bao nhiêu so với (a) chèn tham lam từng sự kiện và (b) giải lại từ đầu tại mỗi epoch, và khoảng cách tới nghiệm clairvoyant tĩnh là bao nhiêu khi mức độ động $\delta$ và độ dài epoch $\Delta$ thay đổi?

Thiết kế này giữ nguyên toàn bộ mô hình, ràng buộc, hàm mục tiêu và mã nguồn Pha 1 ở chế độ tĩnh: mọi thay đổi trong `uav_routing` đều có giá trị mặc định tái tạo đúng kết quả cũ. Phần động nằm trong subpackage `uav_routing.dynamic`, tương tự cách nhánh contextual bandit đặt code trong `uav_routing.contextual`.

## 2. Phạm vi

### Trong phạm vi

- Mô phỏng rời rạc theo epoch với đồng hồ $t$ và danh sách sự kiện có thời điểm tiết lộ.
- Ba loại sự kiện: nhiệm vụ mới xuất hiện, vùng risk xuất hiện hoặc thay đổi, deadline của nhiệm vụ chưa phục vụ bị siết.
- Khóa tiền tố tuyến (locked prefix) theo trạng thái thực thi của UAV tại $t$.
- Warm start: chiếu nghiệm epoch trước sang instance mới rồi chạy ALNS với ngân sách cố định.
- Bộ sinh kịch bản động xác định từ file Solomon-RISK và seed.
- CLI `simulate`, benchmark kịch bản × seed × chính sách, CSV thô và tổng hợp.
- Ba chính sách đối chứng: `greedy_insert`, `cold_restart`, `warm_alns`, cùng tham chiếu `clairvoyant`.

### Ngoài phạm vi

- Pin, gió, vùng cấm bay, đổi hướng UAV đang bay.
- Đa chuyến (một UAV bay nhiều route).
- Request bank với penalty trong ALNS; Pha 2 dùng triage chèn khả thi (mục 8.3).
- Contextual bandit và NSGA-III; giao diện được giữ tương thích để ghép sau (mục 12).
- Dự đoán sự kiện tương lai (stochastic, sampling).

## 3. Mô hình động

### 3.1. Kịch bản

Một kịch bản $\Sigma$ gồm:

- instance nền $I_0$: depot, $n_0$ khách hàng tĩnh, các vùng risk ban đầu, $K_{\max}$, $Q$;
- danh sách sự kiện $E=\{(\tau_j,\epsilon_j)\}$ sắp theo thời điểm tiết lộ $\tau_j$;
- horizon $T=l_0$, tức due date của depot.

Sự kiện $\epsilon_j$ thuộc một trong ba loại:

| Loại | Nội dung | Ảnh hưởng |
|---|---|---|
| `customer_arrival` | Khách hàng mới $i$ với tọa độ, demand, $[e_i,l_i]$, service time; $e_i \geq \tau_j$ | Tập khách hàng, ma trận khoảng cách, priority |
| `risk_update` | Vùng $z$ mới hoặc thay tâm/bán kính | Priority của khách hàng chưa khóa |
| `deadline_update` | $l_i \leftarrow l_i' < l_i$ cho khách hàng $i$ chưa khóa | Feasibility của phần tuyến tự do |

Mức độ động của kịch bản theo Larsen:

$$
\delta=\frac{n_{\mathrm{dyn}}}{n_0+n_{\mathrm{dyn}}},
$$

với $n_{\mathrm{dyn}}$ là số khách hàng xuất hiện sau $t=0$.

### 3.2. Sinh kịch bản từ Solomon

Với file Solomon có 100 khách hàng và giới hạn $n_0$ khách hàng tĩnh, các khách hàng tĩnh là $n_0$ dòng đầu tiên, đúng như Pha 1. Các khách hàng động là $n_{\mathrm{dyn}}$ dòng kế tiếp của cùng file; mỗi khách hàng động nhận thời điểm tiết lộ:

$$
\tau_i \sim \mathcal{U}\left(0,\ \rho\, l_i\right),
\qquad
e_i \leftarrow \max(e_i,\tau_i),
$$

với $\rho\in(0,1)$ là tham số kịch bản. Cách này dùng đúng tọa độ và time window thật của Solomon thay vì sinh ngẫu nhiên.

Sự kiện risk: chọn $m_r$ thời điểm đều trên $(0,T)$; tại mỗi thời điểm sinh một vùng mới hoặc dịch một vùng hiện có với bán kính trong $[2,10]$, giống bộ sinh `generate_solomon_risk.py`.

Sự kiện deadline: chọn $m_d$ khách hàng chưa xuất hiện trong danh sách sự kiện khác, tại thời điểm $\tau < e_i$ siết $l_i \leftarrow e_i + \theta (l_i - e_i)$ với $\theta\in[0.5,0.9]$.

Mọi lựa chọn dùng một `numpy.random.Generator` từ seed kịch bản. Kịch bản được lưu dưới dạng JSON trong `dataset/solomon_dynamic/` để nhóm dùng chung; instance nền không bị sửa.

### 3.3. Instance tại thời điểm $t$

Instance hiện hành $I_t$ là kết quả áp dụng mọi sự kiện có $\tau_j \leq t$ lên $I_0$. Hàm áp dụng là thuần túy: nhận `Instance` bất biến, trả `Instance` mới với ma trận khoảng cách và priority tính lại. Khách hàng mới được thêm vào cuối tuple `customers` với `id` giữ nguyên từ file Solomon nên luôn duy nhất.

Priority của khách hàng **đã khóa** được đóng băng tại giá trị lúc khóa. Điều này bảo đảm risk delay thực hiện của một nhiệm vụ phản ánh mức khẩn cấp tại thời điểm nó được phục vụ, và `Evaluator` không cần thay đổi cách tính $R(S)$.

## 4. Trạng thái thực thi và khóa tiền tố

### 4.1. Quy tắc khóa

Cho nghiệm $S$ với lịch tuyến do `Evaluator` tính. Tại thời điểm $t$, khách hàng $i$ trên tuyến $k$ bị **khóa** khi UAV đã thực sự rời điểm đứng trước $i$:

$$
\operatorname{departure}_{\mathrm{prev}(i)} < t.
$$

Với khách hàng đầu tiên của tuyến, UAV rời depot muộn nhất có thể để đến đúng lúc cửa sổ mở:

$$
\operatorname{departure}_{\mathrm{depot}}=\max\left(t_{\mathrm{free}},\ e_{i}-d_{0i}\right),
$$

trong đó $t_{\mathrm{free}}$ là thời điểm khởi hành sớm nhất được gán cho tuyến. Nhờ vậy một tuyến mở cho khách hàng có cửa sổ xa vẫn tự do cho đến sát giờ bay, thay vì bị cam kết ngay ở epoch kế tiếp. Bất đẳng thức chặt bảo đảm $t=0$ không khóa gì và một UAV đúng lúc khởi hành vẫn có thể được lập lại kế hoạch.

Tiền tố khóa $P_k(t)$ của tuyến $k$ là dãy dài nhất các khách hàng liên tiếp từ đầu tuyến thỏa điều kiện trên. Theo quy tắc này, khách hàng mà UAV đang bay tới cũng bị khóa, vì Pha 2 không cho phép đổi hướng giữa chừng. Tiền tố không bao giờ ngắn lại giữa hai epoch.

Tuyến có $P_k(t)$ trùng toàn bộ tuyến là tuyến đã hoàn tất hoặc đang hoàn tất; UAV của nó không nhận thêm nhiệm vụ.

### 4.2. Bất biến thứ tự tuyến

Trong suốt một epoch, các tuyến có tiền tố khóa khác rỗng chiếm các chỉ số $0,\dots,L-1$ theo thứ tự cố định; các tuyến tự do (chưa khởi hành) đứng sau. Vì destroy chỉ xóa tuyến rỗng và tuyến khóa không bao giờ rỗng, chỉ số của tuyến khóa không đổi. Tuyến mới do repair mở luôn được nối vào cuối.

### 4.3. Ràng buộc tìm kiếm

Một `SearchConstraints` gồm:

- `locked_prefixes`: tuple $L$ tiền tố, tuyến $k<L$ phải bắt đầu đúng bằng $P_k$;
- `free_departure`: thời điểm khởi hành sớm nhất $t$ cho tuyến $k \geq L$;
- `d_ref`: quãng đường tham chiếu cố định của kịch bản.

`Evaluator` kiểm tra ràng buộc tiền tố và báo vi phạm `locked_prefix` như một vi phạm feasibility. Tuyến $k \geq L$ được lập lịch với departure ban đầu bằng `free_departure` thay vì $0$. Tuyến $k<L$ vẫn lập lịch từ $0$ vì đã khởi hành thật.

Giá trị mặc định (không tiền tố, `free_departure = 0`) tái tạo đúng hành vi Pha 1.

## 5. Hàm mục tiêu và metric thực hiện

### 5.1. Trong một epoch

ALNS tối ưu đúng $\operatorname{Score}(S)=(K(S),F(S))$ của Pha 1 trên nghiệm **toàn horizon** (gồm cả phần đã thực hiện), với:

$$
F(S)=\alpha\frac{D(S)}{D_{\mathrm{ref}}}+\beta R(S),
\qquad
D_{\mathrm{ref}}=D(S_0),
$$

trong đó $S_0$ là nghiệm greedy tĩnh tại $t=0$ và $D_{\mathrm{ref}}$ không đổi qua các epoch để $F$ so sánh được giữa các epoch. Phần đã thực hiện đóng góp hằng số vào $D$ và $R$ nên không ảnh hưởng thứ tự ứng viên; giữ nó trong nghiệm cho phép dùng lại `Evaluator`, `Solution` và toàn bộ operator mà không cần biểu diễn "depot ảo".

### 5.2. Kết quả thực hiện của kịch bản

Sau epoch cuối, nghiệm thực hiện $S^{\ast}$ là nghiệm toàn horizon với mọi tuyến đã khóa hoàn toàn. Báo cáo:

- $K(S^{\ast})$, $D(S^{\ast})$, $R(S^{\ast})$ với priority đã đóng băng, $F(S^{\ast})$;
- số khách hàng không được phục vụ $U$ và khối lượng priority không phục vụ $\sum_{i\in U}p_i$;
- số epoch, số lần tái tối ưu, runtime từng epoch và tổng;
- khoảng cách tới clairvoyant:

$$
\mathrm{gap}=\frac{F(S^{\ast})-F(S^{\mathrm{clv}})}{F(S^{\mathrm{clv}})},
$$

với $S^{\mathrm{clv}}$ là nghiệm ALNS tĩnh trên instance cuối $I_T$ khi biết trước mọi sự kiện tại $t=0$ và dùng cùng số vòng lặp tổng.

Khách hàng không phục vụ được xử lý ở mục 8.3, không đưa vào $F$.

## 6. Vòng lặp rolling horizon

```text
ALGORITHM RollingHorizon(Σ, config)

1.  I ← I_0;  t ← 0
2.  (S, D_ref) ← BuildInitialSolution(I)         // greedy Pha 1
3.  S ← ALNS(I, S, constraints=∅, iterations_0)   // epoch 0
4.  epochs ← []

5.  WHILE t < T:
6.      t_next ← NextDecisionTime(t, Δ, E, trigger)
7.      events ← {ε_j : t < τ_j ≤ t_next}
8.      t ← t_next
9.      locks ← LockedPrefixes(S, I, t)           // mục 4.1
10.     I ← ApplyEvents(I, events, frozen=locks)  // mục 3.3
11.     (S_proj, pool) ← Project(S, I, locks)     // mục 8.1
12.     (S_init, rejected) ← Triage(S_proj, pool, I, locks)  // mục 8.3
13.     IF events = ∅ AND pool = ∅ AND trigger = event: CONTINUE
14.     S ← ALNS(I, S_init, constraints=locks, iterations_epoch)
15.     epochs.append(Record(t, events, locks, S, rejected, runtime))

16. RETURN Realized(S, I), epochs
```

`NextDecisionTime` theo `trigger`:

- `periodic`: $t+\Delta$;
- `event`: $\tau$ của sự kiện kế tiếp;
- `hybrid`: $\min(t+\Delta,\ \tau_{\text{next}})$.

Mặc định là `periodic` để số epoch không phụ thuộc nội dung sự kiện, giúp so sánh chính sách công bằng theo ngân sách.

## 7. Ba chính sách và tham chiếu

| Chính sách | Bước 14 | Warm start |
|---|---|---|
| `greedy_insert` | Không chạy ALNS; nghiệm epoch là $S_{\mathrm{init}}$ | Có |
| `cold_restart` | Xây lại greedy cho phần tự do rồi ALNS | Không |
| `warm_alns` | ALNS từ $S_{\mathrm{init}}$ | Có |
| `clairvoyant` | Một lần ALNS tĩnh trên $I_T$ | Không áp dụng |

`cold_restart` giữ nguyên tiền tố khóa và ràng buộc; chỉ khác ở nghiệm khởi đầu. Đây là ablation trực tiếp của warm start.

## 8. Chiếu nghiệm và warm start

### 8.1. Chiếu

`Project` nhận nghiệm $S$ của epoch trước, instance mới $I$ và các tiền tố khóa:

1. Sắp lại tuyến để tuyến khóa đứng trước theo bất biến 4.2.
2. Với mỗi tuyến, giữ tiền tố; loại khách hàng không còn trong $I$; đánh giá tuyến trên $I$; khi tuyến vi phạm, tháo khách hàng tự do **đầu tiên** có $s_i > l_i$ (nếu chỉ vi phạm hạn về depot hoặc tải trọng thì tháo khách hàng tự do cuối cùng), lặp cho đến khi tuyến khả thi hoặc không còn khách hàng tự do; khách hàng bị tháo vào `pool`.
3. Mọi khách hàng của $I$ chưa xuất hiện trong nghiệm (khách hàng mới, khách hàng bị tháo, khách hàng `rejected` được thử lại) vào `pool`, sắp theo `id`.
4. Xóa tuyến tự do rỗng; tuyến khóa luôn được giữ.

Kết quả là nghiệm một phần khả thi theo ràng buộc tuyến, và tập `pool` cần chèn.

### 8.2. Chèn ban đầu

`Triage` chèn `pool` bằng `RiskPriorityRepair` (priority giảm dần, rồi due date), dùng `feasible_insertions` đã tôn trọng tiền tố. Chèn thành công tạo $S_{\mathrm{init}}$ hoàn chỉnh trên tập khách hàng còn phục vụ được.

### 8.3. Khách hàng không chèn được

Khách hàng không có vị trí chèn khả thi nào được ghi vào `rejected` của epoch và **loại khỏi instance của epoch đó** để `Evaluator` giữ ngữ nghĩa hard feasibility. Họ được thử lại ở mỗi epoch sau cho đến khi $t > l_i - d_{0i}$, khi đó trở thành `lost`. Hai metric $U$ và $\sum_{i\in U}p_i$ ghi nhận tổn thất này.

Đây là quyết định có chủ đích thay cho request bank với penalty của Ropke và Pisinger; request bank là hướng mở rộng tự nhiên nếu $U$ lớn trong thực nghiệm.

### 8.4. ALNS với ràng buộc

`run_alns` nhận thêm `initial_solution`, `constraints` và `d_ref`. Các operator tôn trọng ràng buộc như sau:

- destroy: tập ứng viên tháo là khách hàng **tự do**; `RouteRemoval` chỉ tháo phần tự do của tuyến được chọn;
- repair: `feasible_insertions` chỉ xét vị trí $\geq |P_k|$ trên tuyến khóa và mọi vị trí trên tuyến tự do; tuyến mới nhận `free_departure`;
- acceptance, reward, cooling, adaptive weights không đổi.

Nhiệt độ và trọng số operator được khởi tạo lại mỗi epoch theo mặc định; `carry_weights` là tùy chọn cấu hình cho ablation.

## 9. Cấu hình

```python
@dataclass(frozen=True)
class RollingHorizonConfig:
    policy: str = "warm_alns"          # greedy_insert | cold_restart | warm_alns
    trigger: str = "periodic"          # periodic | event | hybrid
    epoch_length: float = 60.0         # Δ, cùng đơn vị với time window
    epoch_fraction: float | None = None  # nếu đặt, Δ = epoch_fraction × horizon
    iterations_epoch0: int = 2_000
    iterations_per_epoch: int = 500
    carry_weights: bool = False
    seed: int = 42
```

Cấu hình ALNS bên trong vẫn là `ALNSConfig`. Tổng ngân sách $\text{iterations}_0 + m\,\text{iterations}_{\text{epoch}}$ được ghi vào kết quả để clairvoyant dùng cùng ngân sách.

## 10. Kiến trúc mã nguồn

```text
phase1/src/uav_routing/
├── evaluator.py        # + SearchConstraints, free_departure, kiểm tra locked_prefix
├── destroy.py          # + lọc khách hàng tự do
├── repair.py           # + vị trí chèn hợp lệ theo tiền tố, departure tuyến mới
├── alns.py             # + initial_solution, constraints, d_ref
└── dynamic/
    ├── __init__.py
    ├── models.py       # Event, Scenario, LockState, EpochRecord, SimulationResult
    ├── config.py       # RollingHorizonConfig
    ├── scenario.py     # đọc/ghi JSON, sinh kịch bản từ Solomon-RISK
    ├── events.py       # apply_events(instance, events, frozen) -> Instance
    ├── locking.py      # locked_prefixes(solution, instance, t) -> LockState
    ├── projection.py   # project(...), triage(...)
    ├── horizon.py      # run_rolling_horizon(scenario, config) -> SimulationResult
    ├── policies.py     # greedy_insert, cold_restart, warm_alns, clairvoyant
    ├── cli.py          # uav_routing.dynamic.cli simulate
    └── experiment.py   # scenario × seed × policy, raw/aggregate CSV

dataset/scripts/generate_solomon_dynamic.py
dataset/solomon_dynamic/<instance>-n<n0>-d<n_dyn>-s<seed>.json
phase1/configs/dynamic/*.json
phase1/tests/dynamic/
```

Nguyên tắc giữ nguyên từ Pha 1: `Evaluator` là nguồn duy nhất tính lịch, feasibility và mục tiêu, kể cả ràng buộc tiền tố; mọi ngẫu nhiên qua một `Generator`; dữ liệu miền bất biến.

## 11. Định dạng kịch bản

```json
{
  "instance": "../solomon_risk/c101.txt",
  "static_customers": 25,
  "risks": 5,
  "seed": 7,
  "horizon": 1236.0,
  "events": [
    {"time": 118.0, "type": "customer_arrival",
     "customer": {"id": 26, "x": 40, "y": 66, "demand": 10,
                  "ready_time": 118.0, "due_date": 500.0, "service_time": 90}},
    {"time": 300.0, "type": "risk_update",
     "zone": {"id": 6, "x": 35, "y": 60, "radius": 8}},
    {"time": 420.0, "type": "deadline_update", "customer_id": 12, "due_date": 700.0}
  ]
}
```

Bộ đọc từ chối sự kiện có thời điểm âm, vượt horizon, không tăng dần, khách hàng trùng `id`, bán kính không dương hoặc deadline mới lớn hơn deadline cũ.

## 12. Tương thích với contextual bandit và NSGA-III

- `ContextualALNSSolver` dùng chung `_operators`, `Evaluator` và `RepairContext`; khi nhận cùng ba tham số `initial_solution`, `constraints`, `d_ref` nó thay thế được `warm_alns` mà không sửa `horizon.py`. Bước 14 gọi qua một callable `solver(instance, initial, constraints, d_ref, config, rng)`.
- NSGA-III có thể dùng `Project` và `LockState` để đóng băng tiền tố trong population; phần này thuộc nhánh khác.

## 13. Kiểm thử

### 13.1. Hồi quy tĩnh

- Toàn bộ 211 test Pha 1 vượt qua không sửa.
- Kết quả `run_alns` với tham số mặc định trên `c101`, 25 khách hàng, seed 42, 200 vòng lặp trùng đúng route và metric với trước khi thay đổi (snapshot test).

### 13.2. Unit tests

- `locked_prefixes`: khách hàng đang bay tới bị khóa; khách hàng chưa khởi hành không khóa; $t=0$ không khóa gì; $t \geq$ depot return khóa toàn tuyến.
- `apply_events`: thêm khách hàng mở rộng ma trận đúng kích thước; risk update chỉ đổi priority khách hàng tự do; deadline update bị từ chối nếu nới lỏng hoặc trúng khách hàng đã khóa.
- `Evaluator` với `constraints`: vi phạm `locked_prefix` khi tiền tố bị đổi; tuyến tự do khởi hành đúng `free_departure`; tuyến khóa vẫn từ $0$.
- destroy không bao giờ trả khách hàng khóa; `RouteRemoval` giữ nguyên tiền tố.
- `feasible_insertions` không sinh vị trí trong tiền tố.
- `project`: tháo đúng khách hàng khi deadline siết; giữ bất biến thứ tự tuyến.
- `triage`: khách hàng không chèn được vào `rejected`, không làm hỏng nghiệm.
- Bộ sinh kịch bản: cùng seed cho cùng JSON; $e_i \geq \tau_i$; sự kiện tăng dần.

### 13.3. Integration tests

- Kịch bản không sự kiện, `iterations_per_epoch = 0`: nghiệm thực hiện trùng nghiệm tĩnh epoch 0.
- Kịch bản nhỏ 5 khách hàng tĩnh + 2 động: mọi tiền tố khóa của epoch $j$ là tiền tố của nghiệm epoch $j+1$.
- Cùng kịch bản, cấu hình, seed cho cùng `SimulationResult`.
- `clairvoyant` trên $I_T$ có $F$ không lớn hơn `warm_alns` trên kịch bản không sự kiện với cùng ngân sách.
- CLI `simulate` chạy được với kịch bản nhỏ và xuất JSON đúng schema; benchmark tạo `raw.csv` và `aggregate.csv`.

## 14. Kế hoạch thực nghiệm

- Instance: chín instance Pha 1, $n_0 = 25$, $n_{\mathrm{dyn}} \in \{5, 12, 25\}$ tương ứng $\delta \approx 0.17,\ 0.32,\ 0.5$.
- $\Delta \in \{30, 60, 120\}$; `trigger` cố định `periodic`, thêm `event` cho một cấu hình.
- 10 seed phát triển, 20 đến 30 seed cho kết quả chính; kiểm định Wilcoxon signed-rank theo cặp kịch bản giữa `warm_alns` và từng chính sách khác.
- Ngân sách: `iterations_epoch0 = 2000`, `iterations_per_epoch = 500`; clairvoyant nhận tổng ngân sách tương đương.
- Báo cáo gap tới clairvoyant, $U$, runtime mỗi epoch và độ nhạy theo $\delta$, $\Delta$.

Nhánh `origin/perf/route-local-repair-delta` nên được gộp trước khi chạy thực nghiệm lớn vì mỗi epoch đánh giá lại các tuyến toàn horizon.

## 15. Tài liệu tham khảo

- Pillac, Gendreau, Guéret, Medaglia (2013). A review of dynamic vehicle routing problems. *European Journal of Operational Research*.
- Ropke, Pisinger (2006). An adaptive large neighborhood search heuristic for the pickup and delivery problem with time windows. *Transportation Science*. Cơ sở của ALNS và request bank.
- Psaraftis (1988). Dynamic vehicle routing problems. Đề xuất rolling horizon cho bài toán động.
- Larsen (2000). The dynamic vehicle routing problem. Định nghĩa degree of dynamism.
- Hong (2012). An improved LNS algorithm for real-time vehicle routing problem with time windows. *Computers & Operations Research*. LNS tái tối ưu theo sự kiện.
- DNSGA-II-ALNS (2025). A warm-start evolutionary algorithm for dynamic multi-objective optimization of heterogeneous VRPTW. *Applied Sciences* 16(17):8572. Warm-start projection cho VRPTW động, hữu ích khi ghép NSGA-III.
- Multiperiod UAV path planning with dynamic emergency priorities for geohazards monitoring (2022). *IEEE*. Priority thay đổi theo thời gian tương tự risk update.

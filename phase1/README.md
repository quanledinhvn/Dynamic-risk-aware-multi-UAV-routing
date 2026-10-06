# Giai đoạn 1 — Định tuyến đa UAV tĩnh có xét đến rủi ro

Phương pháp cơ sở ALNS có khả năng tái lập cho bài toán định tuyến đa UAV tĩnh. Phiên bản contextual dùng Disjoint LinUCB để chọn cặp toán tử và chỉ chạy khi được chọn rõ ràng. Dữ liệu VRPTW Solomon được bổ sung các vùng rủi ro hình tròn; chương trình không cần bộ giải tối ưu hóa bên ngoài.

## Phạm vi

- Các UAV đồng nhất xuất phát từ và quay về cùng một kho.
- Ràng buộc cứng: tải trọng, cửa sổ thời gian, hạn về kho, số UAV tối đa và phục vụ mỗi khách hàng đúng một lần.
- Khoảng cách Euclid bằng thời gian di chuyển vì vận tốc cố định là `1`.
- Bộ dữ liệu Solomon-RISK gồm `C101`, `C102`, `C103`, `R101`, `R102`, `R103`, `RC101`, `RC102`, `RC103`; lệnh `solve` mặc định chọn 25 khách hàng đầu tiên của tệp được chỉ định.
- Chưa xét: pin, gió, vùng cấm bay, bất định và thay đổi trực tuyến.
- Baseline roulette là thuật toán mặc định; contextual là một nhánh thử nghiệm riêng trên cùng bài toán tĩnh và cùng hàm mục tiêu.

## Cài đặt

- Python 3.11 trở lên.
- [uv](https://docs.astral.sh/uv/).

```bash
cd phase1
uv sync
```

Chương trình dùng NumPy; kiểm thử dùng pytest.

## Định dạng đầu vào

- Các phần theo đúng thứ tự: `VEHICLE`, `CUSTOMER`, `RISK`.
- Phương tiện: `NUMBER CAPACITY`.
- Kho/khách hàng: 7 trường số gồm `id`, `x`, `y`, nhu cầu, thời điểm sẵn sàng, hạn phục vụ và thời gian phục vụ.
- Vùng rủi ro: 4 trường số gồm `id`, tọa độ tâm `x`, `y` và bán kính.
- Kho có ID `0`; mọi ID phải duy nhất.
- Tải trọng và bán kính phải dương.
- Số khách hàng trong tệp không được ít hơn giá trị yêu cầu.

## Mô hình và hàm mục tiêu

Mức ưu tiên của khách hàng $i$ đối với vùng rủi ro $z$:

$$
p_i=\max_{z}\max\left(0,1-\frac{d_{iz}}{r_z}\right).
$$

Độ trễ chuẩn hóa khi bắt đầu phục vụ tại $s_i$ trong cửa sổ $[e_i,l_i]$:

$$
q_i=\frac{s_i-e_i}{\max(1,l_i-e_i)}.
$$

Độ trễ rủi ro có trọng số:

$$
R(S)=\frac{\sum_i p_iq_i}{\sum_i p_i},
$$

Quy ước $R(S)=0$ nếu mọi mức ưu tiên đều bằng `0`. Nghiệm tham lam xác định $S_0$ cho khoảng cách tham chiếu:

$$
D_{\mathrm{ref}}=D(S_0).
$$

Hàm mục tiêu thứ cấp:

$$
F(S)=\alpha\frac{D(S)}{D_{\mathrm{ref}}}+\beta R(S),
\qquad \alpha+\beta=1.
$$

So sánh nghiệm theo thứ tự từ điển:

$$
\operatorname{Score}(S)=(K(S),F(S)),
$$

Vì vậy, giảm số UAV được ưu tiên hơn giảm chi phí khoảng cách–rủi ro.

`score_policy="emergency_gate"` thay thứ tự cố định bằng hai chế độ tại ngưỡng
`risk_threshold` là $\tau$:

$$
\operatorname{Score}_{\mathrm{gate}}(S)=
\begin{cases}
(1,R(S),K(S),F(S)), & R(S)>\tau,\\
(0,K(S),F(S),R(S)), & R(S)\leq\tau.
\end{cases}
$$

Mọi nghiệm an toàn được ưu tiên hơn nghiệm chưa an toàn. Khi cả hai nghiệm chưa
an toàn, giảm risk đứng trước số UAV; khi cả hai đã an toàn, số UAV lại đứng
trước objective. Policy được dùng nhất quán để lưu `best`, acceptance và tính
reward. Mặc định vẫn là `lexicographic`; cấu hình
`configs/benchmark_p1_c25_r5.json` bật `emergency_gate` với $\tau=0.2$.

## Contextual Bandit ALNS

Một action là một cặp destroy–repair. Năm destroy và ba repair mặc định tạo 15 arm; kích thước phá nghiệm vẫn được lấy đều từ khoảng `q_min`–`q_max`, không phải một phần của action.

Trước mỗi iteration, selector tạo vector chín đặc trưng: `bias` (luôn bằng 1), tiến độ iteration, nhiệt độ đã chuẩn hóa theo log, số iteration kể từ best gần nhất chia cho `context_window`, tỷ lệ chấp nhận gần đây, tỷ lệ cải thiện current gần đây, chênh lệch số UAV giữa current và best, chênh lệch objective khi hai nghiệm dùng cùng số UAV, và độ trễ rủi ro của current. Các tỷ lệ dùng tối đa `context_window` iteration trước đó; các đặc trưng được giới hạn trong $[0,1]$. Khi `include_temperature=false`, selector bỏ đặc trưng nhiệt độ trước khi đưa context vào LinUCB; tùy chọn này hữu ích với search ngắn khi temperature gần đồng tuyến với progress.

Reward giữ bốn mức rời rạc của baseline: `reward_best` khi có best mới, `reward_improve` khi cải thiện current, `reward_accepted` khi chấp nhận nghiệm xấu hơn, và $0$ khi không có cải thiện được thưởng. LinUCB nhận reward chuẩn hóa bằng raw reward chia cho mức reward lớn nhất; với cấu hình mặc định, các mức lần lượt là $1$, $0.5$, $0.1$ và $0$. Baseline tiếp tục cập nhật roulette bằng raw reward.

Disjoint LinUCB giữ mô hình riêng cho từng cặp, dùng `linucb_exploration` để cân bằng điểm dự đoán và độ bất định, và `linucb_regularization` để khởi tạo mô hình. Mô hình được khởi tạo mới cho mỗi lượt chạy: chưa học qua nhiều instance, chưa xử lý risk map thay đổi trực tuyến, reward trễ hoặc phiên bản LinUCB có quên dữ liệu cũ.

Tùy chọn `short_route_warm_start=true` thử hấp thụ các route có tối đa 5 khách hàng trước vòng lặp contextual. Mỗi vòng quét xét tối đa 8 route ngắn, thử ba repair hiện có và nhận lần giảm số UAV đầu tiên; tối đa 3 vòng quét. `d_ref` vẫn lấy từ nghiệm greedy gốc, còn thời gian warm start được tính vào runtime. Mặc định tùy chọn này tắt để giữ kết quả cũ. Khi so cơ chế bandit với baseline, cần dùng cùng cơ chế khởi tạo ở cả hai phía để tách tác dụng của warm start.

API công khai của package `uav_routing.contextual` gồm `ContextualBanditConfig`, `ContextualALNSSolver`, `ContextualSearchResult` và `run_contextual_alns`. Baseline giữ API `run_alns` hiện có.

## Giải một bộ dữ liệu

Không truyền `--algorithm` sẽ chạy baseline. Có thể chỉ định rõ thuật toán và lưu hai kết quả ở hai đường dẫn riêng:

```bash
uv run python -m uav_routing.cli solve \
  --algorithm baseline \
  --instance ../dataset/solomon_risk/c101.txt \
  --customers 25 \
  --risks 5 \
  --iterations 10000 \
  --seed 42 \
  --alpha 0.5 \
  --beta 0.5 \
  --score-policy emergency_gate \
  --risk-threshold 0.2 \
  --output results/baseline/c101-seed42.json
```

```bash
uv run python -m uav_routing.cli solve \
  --algorithm contextual \
  --instance ../dataset/solomon_risk/c101.txt \
  --customers 25 \
  --risks 5 \
  --iterations 10000 \
  --seed 42 \
  --alpha 0.5 \
  --beta 0.5 \
    --output results/contextual/c101-seed42.json
```

Với lệnh `solve --algorithm contextual`, thêm `--short-route-warm-start` để bật bước hấp thụ route ngắn.

Kết quả JSON gồm:

- Bộ dữ liệu, seed, số vòng lặp và thời gian chạy.
- Số UAV, khoảng cách, độ trễ rủi ro, giá trị mục tiêu và tính khả thi.
- Lộ trình và thời điểm đến, phục vụ, rời đi tại mỗi điểm.
- `algorithm` là `baseline` hoặc `contextual`.
- `score_policy` và `risk_threshold` ghi lại chính sách xếp hạng nghiệm.
- `contextual_bandit` là `null` với baseline hoặc chứa năm tham số contextual: `context_window`, `linucb_exploration`, `linucb_regularization`, `include_temperature` và `short_route_warm_start`.
- `operators` chứa trọng số và số lần dùng roulette với baseline, và là mảng rỗng với contextual.
- `pair_selection_stats` là mảng rỗng với baseline; contextual báo đủ 15 cặp cùng số lần dùng, tổng raw reward và raw reward trung bình. Tổng số lần dùng bằng số iteration.

Tùy chọn `--output` ghi tệp theo cơ chế nguyên tử.

## Chạy benchmark

Hai cấu hình `configs/benchmark.json` và `configs/contextual/benchmark.json` dùng cùng workload và cùng tham số ALNS: `C101`, 100 khách hàng, 5 vùng rủi ro, 10 seed (`0`–`9`) và 100 iteration. Cấu hình contextual bổ sung `"algorithm": "contextual"` cùng `contextual_bandit` với `context_window=100`, `linucb_exploration=0.5` và `linucb_regularization=1.0`.

```bash
uv run python -m uav_routing.experiment \
  --config configs/benchmark.json \
  --algorithm baseline \
  --workers 8 \
  --output-dir results/baseline/benchmark
```

```bash
uv run python -m uav_routing.experiment \
  --config configs/contextual/benchmark.json \
  --algorithm contextual \
  --workers 8 \
  --output-dir results/contextual/benchmark
```

Với benchmark, `--algorithm` trên command line ưu tiên hơn khóa `algorithm` trong JSON; nếu cả hai không có thì dùng `baseline`. Vì vậy có thể bỏ `--algorithm contextual` ở lệnh thứ hai. Tham số `--iterations` và `--seeds` trên command line ghi đè workload trong config mà không sửa file.

Kiểm tra nhanh với hai thư mục riêng:

```bash
uv run python -m uav_routing.experiment \
  --config configs/benchmark.json \
  --iterations 1 \
  --seeds 0 \
  --workers 1 \
  --output-dir results/baseline/smoke

uv run python -m uav_routing.experiment \
  --config configs/contextual/benchmark.json \
  --iterations 1 \
  --seeds 0 \
  --workers 1 \
  --output-dir results/contextual/smoke
```

- `raw.csv`: một dòng cho mỗi cặp bộ dữ liệu/seed. Cột theo thứ tự: `instance,customers,risks,algorithm,seed,iterations,alpha,beta,score_policy,risk_threshold,context_window,linucb_exploration,linucb_regularization,include_temperature,short_route_warm_start,vehicles,distance,risk_delay,objective,runtime_seconds,feasible,routes`.
- `aggregate.csv`: nhóm theo `instance,customers,risks,algorithm,iterations,alpha,beta,score_policy,risk_threshold,context_window,linucb_exploration,linucb_regularization,include_temperature,short_route_warm_start`. Header đầy đủ:

```text
instance,customers,risks,algorithm,iterations,alpha,beta,score_policy,risk_threshold,context_window,linucb_exploration,linucb_regularization,include_temperature,short_route_warm_start,runs,vehicles_mean,vehicles_std,vehicles_best,vehicles_worst,distance_mean,distance_std,distance_best,distance_worst,risk_delay_mean,risk_delay_std,risk_delay_best,risk_delay_worst,objective_mean,objective_std,objective_best,objective_worst,runtime_mean,runtime_std
```

- Ba cột hyperparameter LinUCB để trống trong CSV baseline và chứa giá trị thực trong CSV contextual. Thống kê cặp toán tử chỉ nằm trong JSON của lệnh `solve`, không nằm trong CSV.
- Chỉ số tổng hợp: số lượt chạy, trung bình, độ lệch chuẩn mẫu, tốt nhất và kém nhất; độ lệch chuẩn bằng `0` nếu chỉ có một lượt.
- `--workers N` chạy tối đa `N` cặp bộ dữ liệu/seed đồng thời bằng nhiều process; mặc định là `1`.
- Khi chạy song song, process chính ghi kết quả mỗi job vào JSON nguyên tử trong `.tmp/<run-id>` và chỉ tạo CSV sau khi mọi job thành công.
- Thư mục tạm được xóa sau khi tổng hợp thành công và được giữ lại nếu benchmark thất bại.
- Khi gọi API với `solver` tùy biến và nhiều worker, callable phải hỗ trợ pickle; CLI mặc định luôn dùng solver hợp lệ.
- Benchmark dừng nếu gặp nghiệm không khả thi.

## Chạy benchmark trên AWS

Xem hướng dẫn cài đặt, dry run, kiểm soát chi phí và xử lý sự cố tại [runbook SkyPilot](../infra/skypilot/README.md).

Luồng detached lưu artifact và marker trạng thái trên S3, vì vậy có thể chạy `download --cluster <name>` sau khi EC2 đã autodown. Xem chi tiết bucket, prefix, giới hạn Spot và cleanup trong [runbook SkyPilot](../infra/skypilot/README.md).

Từ thư mục `phase1`, chạy preflight rồi thực hiện toàn bộ luồng benchmark:

```bash
cd ..
scripts/sky_benchmark.sh check
scripts/sky_benchmark.sh run
```

## Khả năng tái lập

- Mỗi lượt chạy dùng một `numpy.random.Generator` khởi tạo từ seed.
- Cùng đầu vào, giới hạn khách hàng, cấu hình và seed sẽ cho cùng lộ trình, giá trị mục tiêu và thống kê toán tử hoặc cặp toán tử.
- Thời gian chạy có thể khác nhau.

## Kiểm thử

```bash
uv run pytest tests -q
```

Bao phủ bộ phân tích cú pháp, hình học, ràng buộc, hàm mục tiêu, baseline và contextual ALNS, khả năng tái lập, CLI và benchmark.

## Giai đoạn 2 — Rolling horizon

Phần động nằm trong subpackage `uav_routing.dynamic`. Thiết kế đầy đủ ở [docs/2026-09-30-rolling-horizon-design.md](docs/2026-09-30-rolling-horizon-design.md); kế hoạch triển khai ở [docs/2026-09-30-rolling-horizon-implementation-plan.md](docs/2026-09-30-rolling-horizon-implementation-plan.md).

### Mô hình động

- Một **kịch bản** gồm instance Solomon-RISK nền, $n_0$ khách hàng tĩnh và danh sách sự kiện có thời điểm tiết lộ: khách hàng mới (`customer_arrival`), vùng risk mới hoặc thay đổi (`risk_update`), deadline bị siết (`deadline_update`).
- Mô phỏng chạy theo **epoch**. Tại mỗi epoch $t$, mọi khách hàng mà UAV đã thực sự rời điểm đứng trước bị **khóa** và không thể thay đổi; UAV rời depot muộn nhất có thể cho khách hàng đầu tiên. Priority của khách hàng đã khóa được đóng băng.
- Nghiệm được **chiếu** sang instance mới: khách hàng vi phạm deadline mới bị tháo, khách hàng mới được chèn theo risk priority. Khách hàng không chèn được đâu bị `rejected`, thử lại mỗi epoch và trở thành `lost` khi không còn kịp bay tới.
- ALNS Pha 1 chạy trên nghiệm toàn horizon với `SearchConstraints` (tiền tố khóa và thời điểm khởi hành của tuyến tự do). Với tham số mặc định, Pha 1 cho kết quả không đổi; `tests/test_static_snapshot.py` khóa điều này.
- $D_{\mathrm{ref}}$ được tính một lần tại epoch 0 và dùng cho toàn kịch bản.

### Chính sách

| Chính sách | Mô tả |
|---|---|
| `greedy_insert` | Chỉ chèn sự kiện mới, không chạy ALNS |
| `cold_restart` | Xây lại phần tự do từ đầu rồi chạy ALNS |
| `warm_alns` | ALNS từ nghiệm epoch trước (mặc định) |
| clairvoyant | Một lần ALNS tĩnh trên instance cuối với cùng ngân sách; dùng làm tham chiếu cho `gap` |

### Sinh kịch bản

Khách hàng động là các dòng Solomon ngay sau $n_0$ dòng tĩnh, với thời điểm tiết lộ $\tau_i \sim \mathcal{U}(0, \rho\, l_i)$ và $e_i \leftarrow \max(e_i, \tau_i)$.

```bash
uv run python ../dataset/scripts/generate_solomon_dynamic.py \
  --instances c101 c102 c103 r101 r102 r103 rc101 rc102 rc103 \
  --static 25 --dynamic 5 12 25 --seeds 0 1 2 3 4 5 6 7 8 9 \
  --output ../dataset/solomon_dynamic
```

Tên file có dạng `<instance>-n<n0>-d<n_dyn>-s<seed>.json`. Định dạng JSON được mô tả ở mục 11 của design spec.

### Mô phỏng một kịch bản

```bash
uv run python -m uav_routing.dynamic.cli simulate \
  --scenario ../dataset/solomon_dynamic/c101-n25-d5-s0.json \
  --policy warm_alns \
  --trigger periodic \
  --epoch-length 60 \
  --iterations-epoch0 2000 \
  --iterations-per-epoch 500 \
  --seed 42 \
  --output results/dynamic/c101-n25-d5-s0-warm.json
```

JSON gồm cấu hình, số UAV, quãng đường, risk delay, objective, khách hàng không phục vụ, lịch sử từng epoch (thời điểm, sự kiện tiết lộ, số khách hàng khóa, `rejected`, objective, số vòng lặp, runtime) và các tuyến kèm lịch phục vụ.

### Benchmark động

```bash
uv run python -m uav_routing.dynamic.experiment \
  --config configs/dynamic/smoke.json \
  --workers 2 \
  --output-dir results/dynamic-smoke
```

- Độ dài epoch nên đặt theo tỷ lệ horizon bằng `epoch_fraction` (mặc định trong cấu hình là `0.05`), vì horizon của `R1`/`RC1` (230) ngắn hơn nhiều so với `C1` (1236); `epoch_length` cố định được dùng khi không đặt `epoch_fraction`.
- `raw.csv`: một dòng cho mỗi kịch bản × seed × chính sách, kèm `clairvoyant_objective` và `gap`. `gap` chỉ có ý nghĩa khi `unserved = 0`, vì objective không tính khách hàng bị bỏ; luôn đọc `gap` cùng `unserved` và `unserved_priority`.
- `aggregate.csv`: thống kê theo kịch bản, chính sách, trigger và độ dài epoch.
- Clairvoyant chạy một lần cho mỗi cặp kịch bản/seed với ngân sách `iterations_epoch0 + số epoch × iterations_per_epoch`.
- Các cấu hình chính: `configs/dynamic/benchmark_n25_d{5,12,25}.json`.
- Có thể ghi đè `--seeds`, `--policies`, `--epoch-length`, `--iterations-epoch0`, `--iterations-per-epoch` từ dòng lệnh.

### Phân tích thống kê

```bash
uv run python -m uav_routing.dynamic.analysis \
  --results results/dynamic_n25_d5 results/dynamic_n100_d5 \
  --reference warm_alns --output results/analysis/main_policies.md
```

So sánh theo cặp trên cùng kịch bản và seed: thắng/thua theo thứ tự từ điển $(U, K, F)$, kiểm định Wilcoxon signed-rank trên $F$ với hiệu chỉnh Holm. Chế độ `--grid LABEL=DIR ...` so sánh các cấu hình của cùng một chính sách. Kết quả ablation và kết luận ở [docs/2026-10-04-ablation.md](docs/2026-10-04-ablation.md).

### Khả năng tái lập

Cùng kịch bản, cấu hình ALNS, cấu hình rolling horizon và seed cho cùng nghiệm thực hiện, lịch sử epoch và metric. Seed của từng epoch được dẫn xuất xác định từ seed cấu hình và chỉ số epoch.

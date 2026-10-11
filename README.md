# Dynamic Risk-Aware Multi-UAV Routing

Dự án nghiên cứu bài toán lập tuyến cho nhiều UAV trong môi trường có ràng buộc
về sức chứa, cửa sổ thời gian, hạn quay về depot và vùng rủi ro. Mục tiêu là
giảm số UAV sử dụng, quãng đường di chuyển và độ trễ phục vụ các khách hàng có
mức ưu tiên rủi ro cao.

Repository hiện cung cấp:

- **ALNS tĩnh** với nhiều destroy/repair operator và cơ chế cập nhật trọng số;
- **Contextual ALNS** dùng LinUCB để chọn cặp operator theo trạng thái tìm kiếm;
- **Rolling horizon động** cho sự kiện khách hàng mới, cập nhật rủi ro và thay
  đổi deadline;
- **NSGA-III** làm baseline tối ưu đa mục tiêu;
- công cụ sinh dữ liệu, chạy benchmark lặp lại, tổng hợp CSV và triển khai
  benchmark trên AWS bằng SkyPilot.

## Mô hình bài toán

Dữ liệu đầu vào dựa trên Solomon VRPTW và được mở rộng bằng các vùng rủi ro.
Mỗi khách hàng có vị trí, nhu cầu, cửa sổ thời gian và thời gian phục vụ. Độ ưu
tiên rủi ro được suy ra từ khoảng cách tới các vùng rủi ro.

ALNS so sánh nghiệm theo thứ tự từ điển: trước hết giảm số UAV, sau đó tối ưu
hàm mục tiêu kết hợp

```text
F(S) = alpha * D(S) / D_ref + beta * R(S)
```

trong đó `D(S)` là tổng quãng đường, `D_ref` là quãng đường của nghiệm tham
chiếu và `R(S)` là độ trễ có trọng số rủi ro. NSGA-III giữ riêng các mục tiêu để
xây dựng tập nghiệm Pareto.

## Yêu cầu

- Python 3.11 trở lên;
- [uv](https://docs.astral.sh/uv/) để quản lý môi trường và dependency;
- LaTeX chỉ cần thiết khi biên dịch báo cáo;
- AWS CLI và SkyPilot chỉ cần thiết khi chạy benchmark trên AWS.

## Cài đặt

Hai implementation được đóng gói độc lập:

```bash
git clone <repository-url>
cd "Dynamic risk-aware multi-UAV routing"

cd phase1
uv sync --dev

cd ../phase1_NSGA
uv sync --dev
```

`uv` tạo môi trường riêng và cài đúng phiên bản dependency từ `uv.lock` của
từng thư mục.

## Chạy nhanh

### ALNS tĩnh

Từ thư mục `phase1`:

```bash
uv run python -m uav_routing.cli solve \
  --instance ../dataset/solomon_risk/c101.txt \
  --customers 25 \
  --risks 5 \
  --iterations 1000 \
  --seed 42 \
  --output results/c101.json
```

Kết quả JSON gồm số UAV, quãng đường, risk delay, objective, thời gian chạy và
lịch trình chi tiết của từng tuyến.

Để chạy Contextual ALNS, thêm lựa chọn thuật toán:

```bash
uv run python -m uav_routing.cli solve \
  --instance ../dataset/solomon_risk/c101.txt \
  --customers 25 \
  --risks 5 \
  --iterations 1000 \
  --algorithm contextual \
  --short-route-warm-start \
  --output results/c101-contextual.json
```

### Mô phỏng động

Rolling horizon hỗ trợ các policy `greedy_insert`, `cold_restart`, `warm_alns`
và `contextual_warm_alns`; việc tái tối ưu có thể được kích hoạt định kỳ, theo
sự kiện hoặc kết hợp cả hai.

```bash
cd phase1
uv run python -m uav_routing.dynamic.cli simulate \
  --scenario ../dataset/solomon_dynamic/c101-n25-d5-s0.json \
  --policy warm_alns \
  --trigger periodic \
  --epoch-fraction 0.05 \
  --iterations-epoch0 2000 \
  --iterations-per-epoch 500 \
  --output results/dynamic-c101.json
```

### NSGA-III

Từ thư mục `phase1_NSGA`:

```bash
uv run uav-routing-nsga \
  ../dataset/solomon_risk/c101.txt \
  --customers 25 \
  --risk-zones 5 \
  --population 28 \
  --generations 100 \
  --seed 42 \
  --output results/c101-pareto.json
```

Đầu ra chứa tập Pareto cùng vector mục tiêu và các tuyến tương ứng.

## Chạy benchmark

Các benchmark đều hỗ trợ nhiều seed, chạy song song và xuất dữ liệu thô cùng
thống kê tổng hợp.

### ALNS và Contextual ALNS

```bash
cd phase1

# Baseline ALNS
uv run python -m uav_routing.experiment \
  --config configs/benchmark_p1_c25_r1.json \
  --workers 4 \
  --output-dir results/alns

# Contextual ALNS
uv run python -m uav_routing.experiment \
  --config configs/contextual/benchmark.json \
  --workers 4 \
  --output-dir results/contextual
```

Mỗi thư mục kết quả có:

- `raw.csv`: kết quả của từng instance và seed;
- `aggregate.csv`: mean, standard deviation, best và worst theo từng cấu hình.

### Benchmark động

```bash
cd phase1
uv run python -m uav_routing.dynamic.experiment \
  --config configs/dynamic/benchmark_n25_d5.json \
  --workers 4 \
  --output-dir results/dynamic-n25-d5
```

Benchmark động so sánh mỗi policy với nghiệm clairvoyant có cùng ngân sách
iteration và báo cáo thêm optimality gap, số nhiệm vụ chưa phục vụ cùng runtime
theo epoch.

### Benchmark NSGA-III

```bash
cd phase1_NSGA
uv run uav-routing-nsga-benchmark \
  --config configs/benchmark.json \
  --workers 4 \
  --output-dir results/nsga3
```

Kết quả của mỗi lần chạy được ghi vào thư mục chỉ định bởi `--output-dir`.
Thư mục `benchmark/` lưu các snapshot kết quả đã được chọn để phục vụ phân
tích và tái lập, không phải thư mục đầu ra khi chạy lệnh trên. Nội dung hiện có:

- `alns/`: hai benchmark ALNS tĩnh trên 56 instance Solomon;
- `contextual/`: benchmark Contextual ALNS trên bộ 56 instance và các phép thử
  nhỏ trên 3 instance với các ngân sách iteration khác nhau;
- `nsga/`: benchmark NSGA-III, gồm số liệu tổng hợp và các nghiệm Pareto thô;
- `dynamic/full/`: bộ benchmark động đầy đủ cho 6 mức $n \in \{25, 100\}$ và
  $d \in \{5, 12, 25\}$, cùng cấu hình, dữ liệu thô, số liệu tổng hợp, phân tích
  và log chạy.

## Kiểm thử và kiểm tra mã nguồn

```bash
cd phase1
uv run pytest
uv run ruff check .

cd ../phase1_NSGA
uv run pytest
uv run ruff check .
```

Có thể chạy nhanh một nhóm test cụ thể, ví dụ:

```bash
cd phase1
uv run pytest tests/contextual tests/dynamic -q
```

## Dữ liệu

```text
dataset/
├── solomon/             # Bộ Solomon VRPTW gốc
├── solomon_risk/        # Solomon mở rộng với vùng rủi ro
├── solomon_dynamic/     # Scenario động dạng JSON
├── solomon_visualize/   # File trực quan hóa dữ liệu
└── scripts/             # Script sinh dữ liệu risk/dynamic và HTML
```

Sinh lại dữ liệu mở rộng trong môi trường `phase1`:

```bash
cd phase1
uv run python ../dataset/scripts/generate_solomon_risk.py
uv run python ../dataset/scripts/generate_solomon_dynamic.py
uv run python ../dataset/scripts/generate_solomon_html.py
```

Hai script sinh dữ liệu đầu tiên hỗ trợ `--help` để xem các tùy chọn về nguồn,
thư mục đích, số khách hàng động, số sự kiện và seed. Script HTML tái tạo trực
tiếp các trang trong `dataset/solomon_visualize/`.

Các benchmark cố định seed để có thể tái lập kết quả. Khi so sánh thuật toán,
nên giữ nguyên tập instance, seed, số khách hàng, số vùng rủi ro và ngân sách
iteration/generation.

## Cấu trúc repository

```text
.
├── phase1/              # ALNS, Contextual ALNS và rolling horizon động
│   ├── src/uav_routing/
│   ├── configs/
│   ├── experiments/
│   ├── results/
│   └── tests/
├── phase1_NSGA/         # Baseline NSGA-III
│   ├── src/uav_routing_nsga/
│   ├── configs/
│   └── tests/
├── dataset/             # Instance tĩnh và scenario động
├── benchmark/           # Artifact benchmark dùng trong phân tích
├── infra/skypilot/      # Cấu hình chạy benchmark trên AWS
├── reports/             # Báo cáo LaTeX và PDF
├── scripts/             # Wrapper vận hành benchmark
└── meeting/             # Ghi chú tiến độ
```

## Benchmark trên AWS

Wrapper SkyPilot tự động preflight, tạo EC2, chạy benchmark, đồng bộ artifact
lên S3, tải kết quả về và hủy cluster:

```bash
scripts/sky_benchmark.sh check
scripts/sky_benchmark.sh run \
  --config phase1/configs/benchmark_p1_c25_r1.json \
  --workers 8 \
  --region ap-southeast-1 \
  --instance-type c7a.2xlarge
```

Xem hướng dẫn về AWS credentials, Spot instance, checkpoint, kiểm soát chi phí
và xử lý sự cố tại [`infra/skypilot/README.md`](infra/skypilot/README.md).

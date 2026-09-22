# Thiết kế quy trình benchmark bằng SkyPilot

## 1. Mục tiêu

Bổ sung một quy trình chạy benchmark Phase 1 trên một máy EC2 do SkyPilot quản lý. Người dùng khởi chạy từ thư mục gốc của repository, theo dõi log, tải kết quả về máy local và hủy cluster bằng các lệnh nhất quán.

Quy trình phải:

- đồng bộ working tree hiện tại, bao gồm các tệp chưa commit;
- dùng lại CLI benchmark hiện có, không thay đổi thuật toán ALNS;
- mặc định chạy trên AWS bằng máy CPU, không yêu cầu GPU;
- không ghi thông tin xác thực AWS vào repository;
- tải kết quả về local trước khi hủy cluster;
- cung cấp đường thoát an toàn để không để EC2 chạy ngoài ý muốn;
- có thể kiểm thử phần điều phối mà không thực sự tạo tài nguyên AWS.

## 2. Phạm vi

### Trong phạm vi

- Một SkyPilot task YAML dành cho benchmark Phase 1.
- Một shell script local làm giao diện cho các thao tác `check`, `launch`, `logs`, `download`, `down` và `run`.
- Cấu hình qua tham số dòng lệnh với các giá trị mặc định phù hợp repository.
- On-Demand là chế độ mặc định; Spot là tùy chọn rõ ràng.
- Tải `raw.csv`, `aggregate.csv` và log benchmark về `phase1/results/`.
- Hướng dẫn cài SkyPilot, cấu hình AWS credentials và xử lý sự cố cơ bản.
- Unit test cho shell orchestration bằng SkyPilot CLI giả lập.

### Ngoài phạm vi

- AWS Batch, Terraform, CloudFormation hoặc Kubernetes.
- Managed Jobs và tự động phục hồi Spot.
- Chia 90 cặp instance/seed thành nhiều EC2 độc lập.
- Thay đổi định dạng cấu hình benchmark hoặc mã solver.
- Tự tạo AWS account, IAM user hoặc access key.
- Dashboard web, cảnh báo chi phí hoặc lưu kết quả lâu dài trên S3.

## 3. Giao diện người dùng

Script chính đặt tại `scripts/sky_benchmark.sh` và được gọi từ bất kỳ thư mục làm việc nào. Script tự xác định repository root dựa trên vị trí của chính nó.

Các lệnh:

```bash
scripts/sky_benchmark.sh check

scripts/sky_benchmark.sh launch \
  --config phase1/configs/benchmark_p1_c25_r1.json

scripts/sky_benchmark.sh logs
scripts/sky_benchmark.sh download
scripts/sky_benchmark.sh down

scripts/sky_benchmark.sh run \
  --config phase1/configs/benchmark_p1_c25_r1.json
```

Giá trị mặc định:

| Tham số | Mặc định |
|---|---|
| Cluster | `uav-benchmark` |
| Cloud | `aws` |
| Instance type | `c7a.2xlarge` |
| Disk | `30` GiB |
| Workers | `8` |
| Config | `phase1/configs/benchmark_p1_c25_r1.json` |
| Spot | tắt |
| Autodown | 15 phút idle |

Các tùy chọn được hỗ trợ:

- `--cluster NAME`
- `--config PATH`
- `--instance-type TYPE`
- `--workers N`
- `--spot`
- `--keep-cluster-on-failure`

Script từ chối tham số không hợp lệ, config nằm ngoài repository, số worker không dương hoặc config không tồn tại.

## 4. Thành phần

### `infra/skypilot/benchmark.yaml`

YAML khai báo:

- `workdir: .` để SkyPilot đồng bộ repository hiện tại;
- `resources.infra: aws` và dung lượng đĩa mặc định;
- các biến môi trường bắt buộc `BENCHMARK_CONFIG`, `BENCHMARK_WORKERS` và `BENCHMARK_OUTPUT_DIR`;
- bước `setup` cài `uv` nếu chưa có rồi chạy `uv sync --frozen` trong `phase1`;
- bước `run` giới hạn mỗi process NumPy còn một thread, chạy test smoke và sau đó chạy benchmark thật;
- log benchmark được ghi đồng thời ra terminal và tệp trong output directory.

Loại máy và chế độ Spot được truyền bằng cờ của `sky launch`, nhờ đó một YAML có thể dùng cho nhiều loại EC2 mà không chỉnh tệp.

### `scripts/sky_benchmark.sh`

Script chịu trách nhiệm:

1. phân tích và kiểm tra tham số;
2. xác nhận `sky` tồn tại và AWS được SkyPilot nhận diện;
3. sinh run ID theo UTC để kết quả không ghi đè lần chạy trước;
4. gọi `sky launch` ở chế độ detached với YAML, autodown và các biến môi trường;
5. tải kết quả bằng `sky rsync down`;
6. hủy cluster bằng `sky down` theo chính sách của lệnh đang chạy.

Script không gọi trực tiếp AWS CLI. AWS credentials vẫn do cơ chế tiêu chuẩn của AWS/SkyPilot quản lý.

### `phase1/tests/test_sky_benchmark_script.py`

Test tạo một executable `sky` giả trong thư mục tạm và đặt nó lên đầu `PATH`. Executable ghi lại argv để test xác minh script gọi đúng lệnh mà không kết nối AWS.

### Tài liệu

`phase1/README.md` có một mục ngắn liên kết đến hướng dẫn chi tiết tại `infra/skypilot/README.md`. Hướng dẫn bao gồm cài đặt, cấu hình credentials, ví dụ lệnh, cách xem chi phí và quy tắc cleanup.

## 5. Luồng dữ liệu

```text
Working tree local
        |
        | sky launch + workdir sync
        v
SkyPilot provision EC2 trong AWS account
        |
        | setup: cài uv, uv sync --frozen
        v
Smoke test benchmark
        |
        | thành công
        v
Benchmark đầy đủ với ProcessPoolExecutor
        |
        +--> log trên terminal
        |
        +--> remote output directory
                    |
                    | sky rsync down
                    v
        phase1/results/sky/<run-id>/
                    |
                    | sky down
                    v
              EC2 bị terminate
```

Run ID có dạng `YYYYMMDDTHHMMSSZ`. Output remote và local cùng dùng run ID để ánh xạ một-một. Script in đường dẫn local ở cuối lượt chạy thành công.

## 6. Hành vi từng lệnh

### `check`

Kiểm tra binary SkyPilot, file YAML, config benchmark, cú pháp số worker và kết quả `sky check aws`. Lệnh chỉ đọc trạng thái và không provision tài nguyên.

### `launch`

Provision hoặc dùng lại cluster đã đặt tên, đồng bộ workdir và gửi benchmark ở chế độ detached. Lệnh cấu hình `--idle-minutes-to-autostop 15 --down --wait-for jobs`, vì vậy cluster được giữ tối đa 15 phút idle sau khi job kết thúc để người dùng tải kết quả hoặc điều tra thủ công, rồi tự terminate nếu bị quên. Script ghi state sau khi SkyPilot đã nhận job.

### `logs`

Gọi CLI log của SkyPilot cho cluster đã chọn. Lệnh không thay đổi trạng thái cluster.

### `download`

Tải output directory của run gần nhất về local. Metadata tối thiểu của run gần nhất được lưu trong một tệp state bị Git bỏ qua tại `.sky-benchmark/<cluster>.state`. Nếu không có state hoặc remote output không tồn tại, lệnh thất bại mà không tạo thư mục kết quả rỗng.

### `down`

Hiển thị cluster đích và gọi `sky down`. Lệnh không xóa kết quả local. Lệnh thành công cả khi cluster đã không còn tồn tại, để cleanup có tính idempotent.

### `run`

Thực hiện `check`, `launch`, `logs`, `download` và `down` theo thứ tự. `logs` chạy ở chế độ follow để chờ job kết thúc và chuyển mã lỗi của job về script trước khi download. Nếu launch, job hoặc download thất bại, mặc định script cố lấy phần log hiện có, sau đó hủy cluster để giới hạn chi phí. `--keep-cluster-on-failure` vô hiệu hóa cleanup khi lỗi và in rõ lệnh `down` mà người dùng cần chạy sau khi debug.

## 7. Xử lý lỗi và an toàn chi phí

- Mọi lỗi được in ra `stderr` kèm bước thất bại.
- Script bật chế độ shell nghiêm ngặt và quote mọi đường dẫn.
- Cleanup chỉ nhắm tới đúng tên cluster đã được validate; không dùng glob.
- `run` cài `trap` trước khi provision để xử lý interrupt và lỗi không mong đợi.
- `download` phải hoàn tất trước `down` trong đường thành công.
- Nếu download thất bại, script không tuyên bố benchmark hoàn tất dù remote job thành công.
- Autodown sau 15 phút idle là lớp bảo vệ bổ sung, không thay thế cleanup chủ động.
- Spot chỉ được bật khi người dùng truyền `--spot`; flow đầu tiên không cung cấp checkpoint hoặc recovery.
- Không log AWS access key, secret key, session token hoặc nội dung `~/.aws`.
- Script không mở port dịch vụ công khai.

## 8. Kiểm thử

Test orchestration bao phủ:

- `check` báo lỗi khi không tìm thấy SkyPilot;
- config không tồn tại bị từ chối trước khi gọi SkyPilot;
- workers bằng không hoặc không phải số nguyên bị từ chối;
- `launch` truyền đúng cluster, instance type, worker, config và output directory;
- `--spot` thêm đúng cờ và mặc định không dùng Spot;
- `download` dùng remote/local path từ state;
- `down` chỉ tác động đúng cluster;
- `run` gọi theo thứ tự launch, logs, download, down khi thành công;
- `run` vẫn cleanup khi launch hoặc download thất bại;
- `--keep-cluster-on-failure` giữ cluster và in cảnh báo chi phí;
- đường dẫn config có khoảng trắng được truyền nguyên vẹn;
- state hỏng hoặc thiếu không dẫn đến lệnh rsync sai đích.

Validation thủ công có hai mức:

1. `sky launch --dryrun` để xác minh task và lựa chọn tài nguyên mà không tạo EC2;
2. một smoke run trên On-Demand với một seed và hai iterations trước benchmark đầy đủ.

## 9. Tiêu chí hoàn thành

- Người dùng mới có thể chạy preflight bằng một lệnh.
- Một lệnh `run` có thể provision, benchmark, tải kết quả và terminate cluster.
- Working tree chưa commit được đồng bộ lên EC2.
- Kết quả local có `raw.csv`, `aggregate.csv` và log benchmark.
- Không cần SSH key, `scp`, `tmux`, Docker, S3 hoặc AWS Batch.
- Các lỗi chính có thông báo hành động tiếp theo rõ ràng.
- Toàn bộ test hiện có và test orchestration mới đều vượt qua.

## 10. Tài liệu tham khảo

- [SkyPilot CLI](https://docs.skypilot.co/en/latest/reference/cli.html)
- [SkyPilot environment variables](https://docs.skypilot.co/en/latest/running-jobs/environment-variables.html)
- [SkyPilot YAML task model](https://docs.skypilot.co/en/latest/reference/yaml-spec.html)

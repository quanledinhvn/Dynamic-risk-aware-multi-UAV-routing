# Chạy benchmark Phase 1 trên AWS bằng SkyPilot

Hướng dẫn này chạy benchmark trên một EC2 instance do SkyPilot quản lý. Wrapper luôn tải kết quả về máy local trước khi chủ động hủy cluster trong luồng thành công.

## Điều kiện cần

- Python 3.11 trở lên và `uv`.
- Một AWS account có quyền tạo, xem và terminate EC2 instance cùng các tài nguyên mạng liên quan.
- AWS credentials được cấu hình ở máy local bằng cơ chế chuẩn của AWS SDK.
- `rsync` có trong `PATH` để tải artifact qua SSH alias do SkyPilot tạo.
- Chạy các lệnh trong repository này; wrapper có thể được gọi từ bất kỳ current directory nào.

Wrapper không gọi AWS CLI và không đọc hoặc in access key, secret key hay session token.

## Cài SkyPilot với AWS support

```bash
uv tool install "skypilot[aws]"
sky --version
```

Nếu `sky` chưa có trong `PATH`, làm theo hướng dẫn mà `uv tool` in ra rồi mở lại shell.

## Cấu hình AWS credentials

Một lựa chọn phổ biến là cài AWS CLI và chạy:

```bash
aws configure
```

Cũng có thể dùng AWS SSO, environment variables hoặc shared credentials file theo chính sách của tổ chức. Không ghi credentials vào repository, command history, log benchmark hay tệp cấu hình SkyPilot. Xác nhận SkyPilot nhận diện AWS bằng:

```bash
sky check aws
```

## Preflight không tạo EC2

Từ repository root, kiểm tra wrapper, config, `rsync` và kết nối SkyPilot với AWS:

```bash
scripts/sky_benchmark.sh check
```

Kiểm tra task và lựa chọn tài nguyên bằng dry run; lệnh này không tạo EC2:

```bash
sky launch --dryrun \
  --cluster uav-benchmark \
  --instance-type c7a.2xlarge \
  --env BENCHMARK_CONFIG=phase1/configs/benchmark_p1_c25_r1.json \
  --env BENCHMARK_WORKERS=8 \
  --env BENCHMARK_OUTPUT_DIR=phase1/results/sky/dryrun \
  infra/skypilot/benchmark.yaml
```

Bộ pytest của wrapper cũng hoàn toàn offline:

```bash
cd phase1
uv run pytest tests/test_sky_benchmark_script.py -q
```

Các test này không xác minh AWS account, IAM permission, service quota, loại instance đang sẵn có hoặc việc thực thi thật trên EC2.

## Chạy benchmark

Luồng mặc định dùng AWS On-Demand, cluster `uav-benchmark`, instance `c7a.2xlarge`, đĩa 30 GiB, 8 worker và tự động down sau 15 phút idle:

```bash
scripts/sky_benchmark.sh run
```

Có thể chọn config, worker, instance và cluster:

```bash
scripts/sky_benchmark.sh run \
  --config phase1/configs/benchmark_p1_c25_r1.json \
  --workers 8 \
  --instance-type c7a.2xlarge \
  --cluster uav-benchmark
```

`run` thực hiện preflight, launch, theo dõi job, tải artifact rồi hủy cluster. Nếu launch, log-follow hoặc download thất bại, wrapper cố lấy log hiện có và hủy cluster để giới hạn chi phí.

## Theo dõi, tải kết quả và hủy cluster thủ công

Các bước tương đương khi muốn điều khiển riêng từng giai đoạn:

```bash
scripts/sky_benchmark.sh launch
scripts/sky_benchmark.sh logs
scripts/sky_benchmark.sh download
scripts/sky_benchmark.sh down
```

`launch` ghi metadata của lượt gần nhất vào `.sky-benchmark/<cluster>.state`. `download` chỉ dùng state đã được kiểm tra và gọi system `rsync` qua SSH alias của cluster; không dùng `source` hoặc `eval` trên nội dung state.

Nếu một luồng thủ công gặp lỗi, hãy chạy `scripts/sky_benchmark.sh down` trước khi rời máy, trừ khi bạn chủ ý giữ cluster để debug và đang theo dõi chi phí.

## On-Demand và Spot

On-Demand là mặc định. Spot chỉ được bật rõ ràng:

```bash
scripts/sky_benchmark.sh run --spot
```

Luồng này không có checkpoint hoặc bảo đảm recovery. EC2 Spot có thể bị thu hồi và làm mất tiến trình hay artifact chưa tải về.

Để giữ cluster sau lỗi nhằm điều tra:

```bash
scripts/sky_benchmark.sh run --keep-cluster-on-failure
```

Wrapper sẽ in lệnh cleanup cần chạy. Tùy chọn này có thể tiếp tục phát sinh chi phí cho tới khi cluster được hủy hoặc cơ chế autodown có hiệu lực.

## Kiểm soát chi phí

Kiểm tra cluster và báo cáo chi phí định kỳ:

```bash
sky status
sky cost-report
```

Autodown 15 phút là lớp bảo vệ bổ sung, không thay thế cleanup chủ động. Sau một lỗi hoặc lần chạy thủ công, xác minh cluster đã biến mất bằng `sky status`; nếu còn tồn tại, chạy:

```bash
scripts/sky_benchmark.sh down --cluster uav-benchmark
```

## Kết quả local

Mỗi lượt dùng run ID UTC dạng `YYYYMMDDTHHMMSSZ`. Artifact được tải về:

```text
phase1/results/sky/<run-id>/raw.csv
phase1/results/sky/<run-id>/aggregate.csv
phase1/results/sky/<run-id>/benchmark.log
```

Wrapper chỉ báo thành công sau khi download hoàn tất. Lệnh `down` không xóa kết quả local.

## Xử lý sự cố

- `SkyPilot chưa được cài đặt`: cài lại bằng `uv tool install "skypilot[aws]"` và kiểm tra `PATH`.
- `sky check aws` thất bại: kiểm tra credentials, IAM permissions và region theo chính sách AWS của bạn.
- Không provision được `c7a.2xlarge`: kiểm tra quota hoặc thử `--instance-type` khác có đủ CPU và RAM.
- Config bị từ chối: dùng một file tồn tại bên trong repository; đường dẫn ngoài repository không được đồng bộ.
- Download thất bại: giữ cluster bằng `--keep-cluster-on-failure` nếu cần debug, kiểm tra `sky status`, rồi thử lại `download` trước khi `down`.
- Job thất bại: chạy `scripts/sky_benchmark.sh logs`; sau khi điều tra phải chạy `scripts/sky_benchmark.sh down`.

Không sửa thủ công state để trỏ tới đường dẫn tùy ý. Nếu state thiếu hoặc hỏng, hãy xác định cluster bằng `sky status`, lấy log cần thiết và hủy cluster an toàn.

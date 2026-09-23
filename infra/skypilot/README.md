# Chạy benchmark Phase 1 trên AWS bằng SkyPilot

Hướng dẫn này chạy benchmark trên một EC2 instance do SkyPilot quản lý. Artifact được lưu bền vững trên S3 trước khi job kết thúc, nên có thể tải về sau khi EC2 đã autodown.

## Điều kiện cần

- Python 3.11 trở lên và `uv`.
- Một AWS account có quyền tạo, xem và terminate EC2 instance cùng các tài nguyên mạng liên quan.
- AWS credentials được cấu hình ở máy local bằng cơ chế chuẩn của AWS SDK.
- AWS CLI có trong `PATH`; wrapper dùng STS để suy ra bucket và dùng `aws s3 sync` khi download.
- `rsync` có trong `PATH` để tương thích với state cũ chưa có metadata S3.
- Chạy các lệnh trong repository này; wrapper có thể được gọi từ bất kỳ current directory nào.

Wrapper không đọc hoặc in access key, secret key hay session token.

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

Từ repository root, kiểm tra wrapper, config, AWS CLI, `rsync` và kết nối SkyPilot với AWS:

```bash
scripts/sky_benchmark.sh check
```

Kiểm tra task và lựa chọn tài nguyên bằng dry run; lệnh này không tạo EC2:

```bash
sky launch --dryrun \
  --cluster uav-benchmark \
  --region ap-southeast-1 \
  --instance-type c7a.2xlarge \
  --env BENCHMARK_CONFIG=phase1/configs/benchmark_p1_c25_r1.json \
  --env BENCHMARK_WORKERS=8 \
  --env BENCHMARK_OUTPUT_DIR=phase1/results/sky/20260923T000000Z \
  --env BENCHMARK_S3_BUCKET=sky-uav-benchmark-123456789012-ap-southeast-1 \
  --env BENCHMARK_RUN_ID=20260923T000000Z \
  infra/skypilot/benchmark.yaml
```

Thay account ID mẫu bằng ID 12 chữ số do `aws sts get-caller-identity` trả về trước khi chạy dry run.

Bộ pytest của wrapper cũng hoàn toàn offline:

```bash
cd phase1
uv run pytest tests/test_sky_benchmark_script.py -q
```

Các test này không xác minh AWS account, IAM permission, service quota, loại instance đang sẵn có hoặc việc thực thi thật trên EC2.

## Chạy benchmark

Luồng mặc định dùng AWS On-Demand tại region `ap-southeast-1`, cluster `uav-benchmark`, instance `c7a.2xlarge`, đĩa 30 GiB, 8 worker và tự động down sau 15 phút idle:

```bash
scripts/sky_benchmark.sh run
```

Có thể chọn config, worker, instance, region và cluster:

```bash
scripts/sky_benchmark.sh run \
  --config phase1/configs/benchmark_p1_c25_r1.json \
  --workers 8 \
  --region ap-southeast-1 \
  --instance-type c7a.2xlarge \
  --cluster uav-benchmark
```

`run` thực hiện preflight, launch, theo dõi job, tải artifact từ S3 rồi hủy cluster. Nếu launch, log-follow hoặc download thất bại, wrapper cố lấy log hiện có và hủy cluster để giới hạn chi phí.

Với luồng tách rời, `launch` trả về ngay sau khi gửi job. EC2 có thể autodown sau khi job kết thúc, nhưng bucket S3 vẫn được giữ lại.

## Theo dõi, tải kết quả và hủy cluster thủ công

Các bước tương đương khi muốn điều khiển riêng từng giai đoạn:

```bash
scripts/sky_benchmark.sh launch
scripts/sky_benchmark.sh logs
scripts/sky_benchmark.sh download
scripts/sky_benchmark.sh down
```

`launch` ghi metadata của lượt gần nhất vào `.sky-benchmark/<cluster>.state`. Bucket có tên `sky-uav-benchmark-<account-id>-<region>` và được tái sử dụng; mỗi lượt lưu artifact tại `s3://<bucket>/runs/<run-id>/`.

`download --cluster <name>` đọc state đã validate và tải từ S3 ngay cả sau khi cluster autodown. State hai trường của phiên bản cũ tiếp tục dùng `rsync`; parser không dùng `source` hoặc `eval`.

Nếu một luồng thủ công gặp lỗi, hãy chạy `scripts/sky_benchmark.sh down` trước khi rời máy, trừ khi bạn chủ ý giữ cluster để debug và đang theo dõi chi phí.

## On-Demand và Spot

On-Demand là mặc định. Spot chỉ được bật rõ ràng:

```bash
scripts/sky_benchmark.sh run --spot
```

Luồng này không có bảo đảm recovery. Spot interruption hoặc EC2 mất đột ngột có thể ngăn exit trap chạy, do đó artifact mới nhất có thể chưa được lưu lên S3.

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

Bucket không bị xóa tự động vì có thể chứa nhiều lượt chạy. Kiểm tra storage bằng `sky storage ls`; thao tác xóa bucket hoặc prefix phải được thực hiện thủ công, có chủ đích và được xem là phá hủy dữ liệu.

## Kết quả local

Mỗi lượt dùng run ID UTC dạng `YYYYMMDDTHHMMSSZ`. Artifact được tải về:

```text
phase1/results/sky/<run-id>/raw.csv
phase1/results/sky/<run-id>/aggregate.csv
phase1/results/sky/<run-id>/benchmark.log
```

Wrapper chỉ báo thành công sau khi download hoàn tất. Lệnh `down` không xóa kết quả local.

Prefix S3 có đúng một marker trạng thái. `SUCCESS` nghĩa là benchmark và bước sao chép đều hoàn tất; `FAILED` nghĩa là shell thoát lỗi bình thường và các artifact từng phần hiện có đã được archive.

## Xử lý sự cố

- `SkyPilot chưa được cài đặt`: cài lại bằng `uv tool install "skypilot[aws]"` và kiểm tra `PATH`.
- `AWS CLI chưa được cài đặt`: cài AWS CLI và xác nhận `aws sts get-caller-identity` hoạt động.
- `sky check aws` thất bại: kiểm tra credentials, IAM permissions và region theo chính sách AWS của bạn.
- Không provision được `c7a.2xlarge`: kiểm tra quota hoặc thử `--instance-type` khác có đủ CPU và RAM.
- Config bị từ chối: dùng một file tồn tại bên trong repository; đường dẫn ngoài repository không được đồng bộ.
- Download thất bại: giữ nguyên dữ liệu local cũ, kiểm tra state và quyền truy cập S3, rồi thử lại `download --cluster <name>`.
- Job thất bại: chạy `scripts/sky_benchmark.sh logs`; sau khi điều tra phải chạy `scripts/sky_benchmark.sh down`.

Không sửa thủ công state để trỏ tới đường dẫn tùy ý. Nếu state thiếu hoặc hỏng, hãy xác định cluster bằng `sky status`, lấy log cần thiết và hủy cluster an toàn.

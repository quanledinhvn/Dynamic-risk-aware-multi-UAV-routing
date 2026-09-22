# Giai đoạn 1 — Định tuyến đa UAV tĩnh có xét đến rủi ro

Phương pháp cơ sở ALNS có khả năng tái lập cho bài toán định tuyến đa UAV tĩnh. Dữ liệu VRPTW Solomon được bổ sung các vùng rủi ro hình tròn; chương trình không cần bộ giải tối ưu hóa bên ngoài.

## Phạm vi

- Các UAV đồng nhất xuất phát từ và quay về cùng một kho.
- Ràng buộc cứng: tải trọng, cửa sổ thời gian, hạn về kho, số UAV tối đa và phục vụ mỗi khách hàng đúng một lần.
- Khoảng cách Euclid bằng thời gian di chuyển vì vận tốc cố định là `1`.
- Mặc định: 25 khách hàng đầu tiên của `C101`, `C102`, `C103`, `R101`, `R102`, `R103`, `RC101`, `RC102`, `RC103`.
- Chưa xét: pin, gió, vùng cấm bay, bất định và thay đổi trực tuyến.

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

## Giải một bộ dữ liệu

```bash
uv run python -m uav_routing.cli solve \
  --instance ../dataset/solomon_risk/c101.txt \
  --customers 25 \
  --risks 5 \
  --iterations 10000 \
  --seed 42 \
  --alpha 0.5 \
  --beta 0.5 \
  --output results/c101-seed42.json
```

Kết quả JSON gồm:

- Bộ dữ liệu, seed, số vòng lặp và thời gian chạy.
- Số UAV, khoảng cách, độ trễ rủi ro, giá trị mục tiêu và tính khả thi.
- Lộ trình và thời điểm đến, phục vụ, rời đi tại mỗi điểm.
- Trọng số và số lần sử dụng các toán tử.

Tùy chọn `--output` ghi tệp theo cơ chế nguyên tử.

## Chạy benchmark

Cấu hình mặc định: 9 bộ dữ liệu, 25 khách hàng, 10 seed (`0`–`9`) và 10.000 vòng lặp.

```bash
uv run python -m uav_routing.experiment \
  --config configs/benchmark.json \
  --workers 8 \
  --output-dir results/benchmark
```

Kiểm tra nhanh mà không sửa cấu hình:

```bash
uv run python -m uav_routing.experiment \
  --config configs/benchmark.json \
  --iterations 2 \
  --seeds 0 \
  --workers 2 \
  --output-dir results/smoke
```

- `raw.csv`: một dòng cho mỗi cặp bộ dữ liệu/seed.
- `aggregate.csv`: thống kê theo bộ dữ liệu, số khách hàng, số vòng lặp, `alpha`, `beta`.
- Chỉ số tổng hợp: số lượt chạy, trung bình, độ lệch chuẩn mẫu, tốt nhất và kém nhất; độ lệch chuẩn bằng `0` nếu chỉ có một lượt.
- `--workers N` chạy tối đa `N` cặp bộ dữ liệu/seed đồng thời bằng nhiều process; mặc định là `1`.
- Khi chạy song song, process chính ghi kết quả mỗi job vào JSON nguyên tử trong `.tmp/<run-id>` và chỉ tạo CSV sau khi mọi job thành công.
- Thư mục tạm được xóa sau khi tổng hợp thành công và được giữ lại nếu benchmark thất bại.
- Khi gọi API với `solver` tùy biến và nhiều worker, callable phải hỗ trợ pickle; CLI mặc định luôn dùng solver hợp lệ.
- Benchmark dừng nếu gặp nghiệm không khả thi.

## Khả năng tái lập

- Mỗi lượt chạy dùng một `numpy.random.Generator` khởi tạo từ seed.
- Cùng đầu vào, giới hạn khách hàng, cấu hình và seed sẽ cho cùng lộ trình, giá trị mục tiêu và thống kê toán tử.
- Thời gian chạy có thể khác nhau.

## Kiểm thử

```bash
uv run pytest tests -q
```

Bao phủ bộ phân tích cú pháp, hình học, ràng buộc, hàm mục tiêu, ALNS, khả năng tái lập, CLI và benchmark.

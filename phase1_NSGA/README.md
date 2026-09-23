# NSGA-III Baseline Phase 1

Baseline NSGA-III cho static risk-aware multi-UAV routing trên dữ liệu Solomon mở rộng với section `RISK`.

## Mục tiêu

Project này là nhánh đa mục tiêu độc lập với baseline ALNS trong `phase1/`. Benchmark được chạy theo ba scenario `risk_limit` là `0`, `1` và `5`. Mỗi nghiệm khả thi được đánh giá bằng vector năm objective cần minimize:

1. số UAV sử dụng;
2. tổng quãng đường;
3. risk delay có trọng số priority;
4. tải lớn nhất trên một UAV;
5. tổng lateness.

Time window, depot deadline, capacity, số UAV và phục vụ đúng một lần là ràng buộc cứng. NSGA-III trả về một Pareto front thay vì một nghiệm duy nhất.

## Cài đặt và kiểm thử

```powershell
cd phase1_NSGA
python -m pip install -e .
python -m pytest tests -q
```

## Chạy một instance

```powershell
python -m uav_routing_nsga.cli ..\dataset\solomon_risk\c101.txt --customers 25 --population 28 --generations 100 --seed 42 --output result.json
```

Nếu chạy từ source chưa cài editable package:

```powershell
$env:PYTHONPATH = "src"
python -m uav_routing_nsga.cli ..\dataset\solomon_risk\c101.txt
```

## Kiến trúc

- `parser.py`: đọc Solomon-RISK và xây `Instance`.
- `evaluator.py`: nguồn duy nhất tính schedule, feasibility và objective vector.
- `encoding.py`: permutation chromosome, decoder và khởi tạo population.
- `variation.py`: order crossover và swap mutation.
- `dominance.py`: Pareto dominance và fast non-dominated sorting.
- `normalization.py`: chuẩn hóa objective và associate với reference direction.
- `selection.py`: NSGA-III environmental selection.
- `nsga3.py`: vòng lặp population-based và seed control.
- `cli.py`: chạy một instance và xuất JSON.

## Reproducibility

Cùng instance, cấu hình và seed sẽ tái tạo cùng population, Pareto front và objective values. Runtime không được coi là metric tái lập.

## Giới hạn có chủ đích của Phase 1

Risk hiện được mô hình hóa bằng risk priority tại khách hàng và risk delay, chưa phải risk exposure tích phân trên từng đoạn bay. Dynamic rolling horizon, warm start và time-dependent risk map được dành cho Phase 2.

Chi tiết lý thuyết và quyết định thiết kế nằm trong `docs/nsga3-design.md` và kế hoạch triển khai trong `docs/implementation-plan.md`.

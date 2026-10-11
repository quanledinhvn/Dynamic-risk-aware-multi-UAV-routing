# Sensitivity test

Test sensitivity cho thuật toán Dynamic Risk-Aware Multi-UAV Routing, chạy trên code `master` ở commit `1d15fce`.

Thiết kế test:

- 3 case thuật toán, 11 tham số, 54 điểm đo, 9 instance, 5 seed.
- Tổng cộng 2,430 lần chạy, không có lần nào lỗi.

## Nội dung

| File / thư mục | Nội dung |
|---|---|
| [`report.html`](report.html) | **Báo cáo chính:** dữ liệu (file nào, định dạng, cách sinh sự kiện), thuật toán, tham số và khoảng test, số lần chạy, kết quả, kết luận, cách tái lập |
| [`overview.html`](overview.html) | Tổng quan đề tài: bài toán, thuật toán, dữ liệu, tham số, sơ đồ. Mục 9 tóm tắt kết quả sensitivity |
| [`results/SENSITIVITY_RESULTS.md`](results/SENSITIVITY_RESULTS.md) | Bảng chi tiết mọi mức của mọi tham số, kèm kiểm định Friedman / sign test và hiệu chỉnh Holm |
| [`results/results.csv`](results/results.csv) | 2,430 dòng, mỗi dòng là một lần chạy: số UAV, quãng đường, risk_delay, objective, số khách unserved, runtime, … |
| [`code/plan.py`](code/plan.py) | Định nghĩa 3 case, các điểm đo và mức test |
| [`code/runner.py`](code/runner.py) | Chạy song song, có resume, theo dõi tiến độ và ETA, dừng an toàn |
| [`code/analyze.py`](code/analyze.py) | Sinh `results.csv` và `SENSITIVITY_RESULTS.md` từ kết quả từng job |
| [`CLAUDE.md`](CLAUDE.md) | Nhật ký các phiên làm việc và việc cần làm tiếp |

Kết quả thô của từng job (`results/jobs/`, khoảng 11 MB) và log chạy không được commit (xem `.gitignore`).

## Dữ liệu dùng

| Case | Dữ liệu | Số file |
|---|---|---|
| A (rolling horizon) và C (rolling horizon + contextual) | `dataset/solomon_dynamic/{c,r,rc}10{1,2,3}-n88-d12-s{0..4}.json` | 45 |
| B (contextual ALNS tĩnh) | `dataset/solomon_risk/{c,r,rc}10{1,2,3}.txt`, lấy 100 khách và 5 vùng rủi ro | 9 |

## Chạy lại

Chạy từ thư mục gốc của repo:

```
phase1/.venv/Scripts/python sensitivity_test/code/runner.py run --workers 8 --out sensitivity_test/results_rerun
phase1/.venv/Scripts/python sensitivity_test/code/runner.py status --out sensitivity_test/results_rerun
phase1/.venv/Scripts/python sensitivity_test/code/runner.py stop --out sensitivity_test/results_rerun
phase1/.venv/Scripts/python sensitivity_test/code/analyze.py --out sensitivity_test/results_rerun
```

- `run` tự bỏ qua các job đã có kết quả, nên có thể dừng rồi chạy tiếp bất cứ lúc nào.
- Có thể giới hạn phạm vi chạy bằng `--only A0_base`, `--seeds 0` hoặc `--instances c101`.
- Nếu không truyền `--out`, kết quả được ghi vào `sensitivity_test/results/`.

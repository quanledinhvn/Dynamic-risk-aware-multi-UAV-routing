# ALNS Baseline Tasks — 2026-09-20

Thư mục này chia implementation plan thành các đơn vị có thể thực hiện và review độc lập. Đọc [design spec](../../2026-09-19-alns-baseline-design.md) và [master plan](../../2026-09-20-alns-baseline-implementation-plan.md) trước khi bắt đầu.

## Thứ tự thực hiện

| Task | Nội dung | Milestone | Phụ thuộc |
|---:|---|---|---|
| 01 | [Package skeleton, domain models and validated configuration](task_01.md) | M1 | Không có |
| 02 | [Parse Solomon-RISK instances and derive geometry](task_02.md) | M1 | Task 01 |
| 03 | [Make Evaluator the single feasibility and objective oracle](task_03.md) | M1 | Task 02 |
| 04 | [Build the deterministic greedy initial solution](task_04.md) | M1 | Task 03 |
| 05 | [Implement five destroy operators with a common contract](task_05.md) | M2 | Task 03 |
| 06 | [Build the lexicographic insertion engine](task_06.md) | M2 | Task 03 |
| 07 | [Implement Greedy, Regret-2 and Risk-Priority repair](task_07.md) | M2 | Task 06 |
| 08 | [Implement roulette selection and segmented adaptive weights](task_08.md) | M3 | Task 01 |
| 09 | [Implement acceptance, cooling and the ALNS loop](task_09.md) | M3 | Tasks 04, 05, 07, 08 |
| 10 | [Lock reproducibility and end-to-end search invariants](task_10.md) | M3 | Task 09 |
| 11 | [Add single-instance CLI and complete JSON output](task_11.md) | M4 | Task 10 |
| 12 | [Add benchmark runner, aggregation, README and final verification](task_12.md) | M4 | Task 10 |

## Luồng phụ thuộc

```text
01 ─┬─> 02 -> 03 ─┬─> 04 ───────────┐
    └─> 08 ───────┤                  │
                  ├─> 05 ───────────┤
                  └─> 06 -> 07 ─────┤
                                     v
                                    09 -> 10 ─┬─> 11
                                              └─> 12
```

## Review gates

- Sau Task 03: xác minh công thức và evaluator trước khi viết heuristic.
- Sau Task 07: xác minh neighborhood invariants và atomic repair failure.
- Sau Task 10: xác minh reproducibility, acceptance và reward semantics.
- Sau Task 12: chạy smoke benchmark chín instance và kiểm tra output schema.

## Quy ước trạng thái

Giữ checkbox ngay trong từng file task. Một task chỉ hoàn thành khi năm bước đều được đánh dấu, verification command thoát với mã 0 và commit của task đã được tạo.

## Quy ước TDD

Mỗi task mới phải phân biệt **API scaffold** với **behavior implementation**:

1. Viết test mô tả hành vi mong muốn.
2. Tạo scaffold tối thiểu để toàn bộ import và test collection thành công. Scaffold chỉ được khai báo tên, chữ ký, dataclass field và trả giá trị trung tính hoặc `raise NotImplementedError`; không cài đặt thuật toán đang được kiểm thử.
3. Chạy test và xác nhận trạng thái RED là assertion failure hoặc `NotImplementedError` tại lời gọi đang kiểm thử, không phải `ModuleNotFoundError`, `ImportError`, `NameError` hay lỗi cú pháp.
4. Cài đặt lượng code nhỏ nhất để test chuyển GREEN, sau đó refactor nhưng vẫn giữ toàn bộ suite GREEN.
5. Chạy focused test và toàn bộ suite trước khi commit.

Nếu test vẫn lỗi lúc collection, sửa scaffold hoặc test fixture rồi chạy lại; chưa được bắt đầu behavior implementation cho tới khi test thực sự chạy đến assertion hoặc API stub.

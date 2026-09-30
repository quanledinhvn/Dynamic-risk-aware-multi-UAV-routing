# Rolling Horizon Tasks — 2026-09-30

Thư mục này chia implementation plan Pha 2 thành các đơn vị có thể thực hiện và review độc lập. Đọc [design spec](../../2026-09-30-rolling-horizon-design.md) và [master plan](../../2026-09-30-rolling-horizon-implementation-plan.md) trước khi bắt đầu.

## Thứ tự thực hiện

| Task | Nội dung | Milestone | Phụ thuộc |
|---:|---|---|---|
| 01 | [Dynamic package skeleton, event models and RollingHorizonConfig](task_01.md) | M1 | Không có |
| 02 | [Add SearchConstraints to the Evaluator without changing static results](task_02.md) | M1 | Task 01 |
| 03 | [Make destroy operators respect locked customers](task_03.md) | M1 | Task 02 |
| 04 | [Make insertion and repair respect locked prefixes and free departure](task_04.md) | M1 | Task 02 |
| 05 | [Add warm start, constraints and fixed d_ref to run_alns](task_05.md) | M1 | Tasks 03, 04 |
| 06 | [Define the scenario format, loader and deterministic generator](task_06.md) | M2 | Task 01 |
| 07 | [Apply events to an Instance with frozen priorities](task_07.md) | M2 | Task 06 |
| 08 | [Derive locked prefixes from the executed schedule](task_08.md) | M2 | Task 02 |
| 09 | [Project the previous plan and triage the unassigned pool](task_09.md) | M2 | Tasks 04, 07, 08 |
| 10 | [Implement the rolling-horizon controller and the four policies](task_10.md) | M3 | Tasks 05, 09 |
| 11 | [Add the simulate CLI and JSON output](task_11.md) | M4 | Task 10 |
| 12 | [Add the dynamic benchmark runner, configs, scenarios and README](task_12.md) | M4 | Task 10 |

## Luồng phụ thuộc

```text
01 ─┬─> 02 ─┬─> 03 ──┬─> 05 ─────────────┐
    │       ├─> 04 ──┘                    │
    │       └─> 08 ──┐                    │
    └─> 06 -> 07 ────┼─> 09 ──────────────┤
                     │                     v
                     └────────────────── 10 ─┬─> 11
                                             └─> 12
```

Task 03 và 04 có thể làm song song; Task 06 đến 08 độc lập với Task 03 đến 05.

## Review gates

- Sau Task 05: xác minh ràng buộc chỉ được kiểm tra trong `Evaluator`, destroy và repair; snapshot tĩnh không đổi.
- Sau Task 09: xác minh khóa, áp dụng sự kiện và chiếu nghiệm trên ví dụ nhỏ tính tay.
- Sau Task 10: xác minh reproducibility, kế toán ngân sách và ngữ nghĩa chính sách.
- Sau Task 12: chạy smoke benchmark chín kịch bản, kiểm tra schema CSV, gộp nhánh perf trước khi chạy thực nghiệm dài.

## Quy ước trạng thái

Giữ checkbox ngay trong từng file task. Một task chỉ hoàn thành khi mọi bước đều được đánh dấu, verification command thoát với mã 0 và commit của task đã được tạo.

## Quy ước TDD

Mỗi task mới phải phân biệt **API scaffold** với **behavior implementation**, theo `AGENT_RULE_04_01` đến `AGENT_RULE_04_06`:

1. Viết test mô tả hành vi mong muốn.
2. Tạo scaffold tối thiểu để toàn bộ import và test collection thành công. Scaffold chỉ được khai báo tên, chữ ký, dataclass field và trả giá trị placeholder đúng kiểu hoặc `raise NotImplementedError`; không cài đặt thuật toán đang được kiểm thử.
3. Chạy test và xác nhận trạng thái RED là assertion failure hoặc `NotImplementedError` tại lời gọi đang kiểm thử, không phải `ModuleNotFoundError`, `ImportError`, `NameError` hay lỗi cú pháp.
4. Cài đặt lượng code nhỏ nhất để test chuyển GREEN, sau đó refactor nhưng vẫn giữ toàn bộ suite GREEN.
5. Chạy focused test và toàn bộ suite trước khi commit.

Lệnh chạy test từ `phase1/`:

```bash
uv run pytest tests -q
```

Nếu `uv` không có trong `PATH`, dùng `~/.local/bin/uv`.

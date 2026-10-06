Mình so sánh [contextual](/Users/ledinhquan/Hust/Dynamic%20risk-aware%20multi-UAV%20routing/phase1/results/contextual/aggregate.csv) với [baseline](/Users/ledinhquan/Hust/Dynamic%20risk-aware%20multi-UAV%20routing/phase1/results/benchmark_p1_c100_r5_1000/aggregate.csv). Hai bộ cùng 56 instance, mỗi instance 10 seed, 100 khách hàng, 5 mức rủi ro và 1.000 vòng lặp. Bảng dưới lấy **trung bình các giá trị `*_mean` trên 56 instance**; mọi chỉ số đều càng thấp càng tốt.

| Chỉ số | Contextual | Baseline | Contextual so với baseline |
|---|---:|---:|---:|
| Số UAV | 8,230 | 8,221 | +0,11% |
| Quãng đường | 1.221,44 | 1.219,56 | +0,15% |
| Risk delay | 0,09130 | 0,08580 | +6,41% |
| Objective | 0,41734 | 0,41401 | +0,81% |
| Thời gian chạy | 248,65 s | 227,61 s | +9,24% |

**Kết luận:** Với cấu hình này, contextual chưa cải thiện kết quả tổng thể và chạy chậm hơn khoảng 21 giây mỗi lần. Objective trung bình tốt hơn ở 22 instance, bằng ở 1 và kém hơn ở 33. Mức chênh objective tập trung rõ nhất ở nhóm C: contextual cao hơn baseline 2,07%; nhóm R gần như ngang nhau (+0,04%), còn nhóm RC cao hơn 0,40%.

Có một điểm cần đọc cùng objective: [bộ đánh giá](/Users/ledinhquan/Hust/Dynamic%20risk-aware%20multi-UAV%20routing/phase1/src/uav_routing/evaluator.py:113) ưu tiên **số UAV trước, rồi mới đến objective**. Chẳng hạn C204 dùng trung bình 3,2 UAV với contextual so với 3,6 của baseline, dù objective cao hơn (0,3851 so với 0,3634). Khi đối chiếu từng cặp cùng instance và seed theo đúng thứ tự ưu tiên đó, contextual thắng 266/560 lần, baseline thắng 283/560 lần và hòa 11 lần. Cả 560 lần chạy của mỗi bên đều được ghi là khả thi.

Vì vậy, kết quả hiện tại nghiêng nhẹ về baseline; chưa cho thấy lợi ích nhất quán của LinUCB đủ bù chi phí thời gian chạy.

## Hướng kết hợp contextual và dynamic

Kết quả tĩnh trên không có nghĩa contextual không hữu ích trong bài toán động. Trong rolling horizon, phân phối trạng thái thay đổi sau mỗi `customer_arrival`, `risk_update` và `deadline_update`; đây mới là bối cảnh phù hợp để kiểm tra khả năng thích nghi của bộ chọn toán tử.

Phương pháp kết hợp trong code là `contextual_warm_alns`:

1. Rolling horizon tiết lộ sự kiện, khóa prefix đã thực thi, cập nhật instance, chiếu nghiệm cũ và triage khách hàng chưa thể chèn.
2. Nghiệm khả thi sau triage trở thành warm start của epoch.
3. Contextual ALNS nhận cùng `initial_solution`, `SearchConstraints` và $D_{\mathrm{ref}}$ của epoch.
4. Trong từng iteration, LinUCB chọn một trong 15 cặp destroy–repair; destroy và repair đều phải tôn trọng prefix đã khóa.
5. Nghiệm tốt nhất được chuyển sang epoch kế tiếp.

So sánh chính nên dùng cùng scenario, seed và tổng ngân sách iteration cho bốn policy: `greedy_insert`, `cold_restart`, `warm_alns` và `contextual_warm_alns`. Thứ tự đánh giá nên là $(U,K,F)$, trong đó $U$ là số khách hàng không phục vụ, $K$ là số UAV và $F$ là objective; sau đó mới so runtime. Không nên kết luận chỉ từ $F$ vì objective hiện không phạt trực tiếp khách hàng bị loại khỏi instance của epoch.

Phiên bản hiện tại khởi tạo lại LinUCB ở đầu mỗi epoch. Đây là baseline kết hợp an toàn vì không mang thống kê cũ sang một chế độ rủi ro mới. Bước nghiên cứu tiếp theo nên là ablation giữa:

- reset LinUCB ở mỗi epoch;
- giữ toàn bộ trạng thái LinUCB xuyên epoch;
- dùng hệ số quên để giảm trọng số dữ liệu cũ sau sự kiện lớn.

Nếu carry-over được triển khai, context nên bổ sung đặc trưng động như tỷ lệ khách hàng mới, số deadline vừa đổi, độ biến thiên risk priority, tỷ lệ route đã khóa và tỷ lệ ngân sách còn lại. Khi đó đóng góp không chỉ là “chạy contextual bên trong rolling horizon”, mà là học chọn toán tử dưới distribution shift của bài toán định tuyến động.

Cấu hình smoke để so trực tiếp hai policy ALNS nằm tại `phase1/configs/dynamic/contextual_smoke.json`.

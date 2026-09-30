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
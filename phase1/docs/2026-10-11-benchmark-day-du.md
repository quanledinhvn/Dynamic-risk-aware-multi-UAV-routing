# Benchmark đầy đủ: rolling horizon + ALNS và rolling horizon + contextual bandit

Theo biên bản 06/10/2026: 10 000 vòng lặp, 20 seed, dữ liệu 25 và 100 khách hàng. Phần của Hải: `warm_alns` (rolling horizon + ALNS roulette) và `contextual_warm_alns` (rolling horizon + ALNS chọn toán tử bằng contextual bandit). Chạy trên nhánh `f/hai-benchmark`, tách từ `master` tại `8f52e60` (sau khi gộp phần tích hợp contextual của Quân). Mọi số liệu trong tài liệu này sinh từ `results/full/*/raw.csv` bằng `uav_routing.dynamic.analysis`; bảng gốc ở `results/analysis/full_policies.md`.

## 1. Thiết lập

| Mục | Giá trị |
|---|---|
| Kịch bản | 540 file trong `dataset/solomon_dynamic/`: 9 instance (C101–C103, R101–R103, RC101–RC103) × 2 kích thước × 3 mức động × 10 seed kịch bản |
| 25 khách hàng | 25 tĩnh + {5, 12, 25} động |
| 100 khách hàng | {95+5, 88+12, 75+25}; instance tiết lộ đầy đủ là instance Solomon 100 khách hàng chuẩn |
| Seed chạy | 0–19 cho mỗi kịch bản (20 seed, không cộng dồn) |
| Ngân sách | 2 000 vòng ở epoch 0 + 400 vòng mỗi epoch; 20 epoch cho 10 000, một số instance làm tròn thành 21 epoch cho 10 400. Clairvoyant nhận đúng ngân sách của kịch bản đó |
| Rolling horizon | trigger `periodic`, $\Delta = 0.05\,T$ |
| ALNS | tham số Pha 1 mặc định ($\alpha = \beta = 0.5$, $q \in [2,5]$) |
| Contextual bandit | mặc định của Quân: `context_window 100`, `linucb_exploration 0.5`, `linucb_regularization 1.0`, `include_temperature true`, `short_route_warm_start false`; trạng thái LinUCB khởi tạo lại ở mỗi epoch |
| Khối lượng | mỗi mức: 90 kịch bản × 20 seed × 2 chính sách = 3 600 lượt + 1 800 clairvoyant; tổng 21 600 lượt chính sách |
| Thời gian máy | 44 h 43 trên 16 lõi, 09/10 18:01 → 11/10 14:44; cấu hình `configs/dynamic/full/`, log `results/logs/run_full.log` |

Metric như các tài liệu trước: $F$ (thấp hơn tốt hơn), số UAV $K$, số khách hàng không phục vụ $U$, tỷ lệ lượt phục vụ đủ, và gap tới clairvoyant chỉ tính trên lượt có $U = 0$. Mọi so sánh theo cặp trên cùng kịch bản và seed: thắng/thua theo thứ tự từ điển $(U, K, F)$, Wilcoxon signed-rank hai phía trên $F$.

## 2. Kết quả theo mức

| Mức | Chính sách | $F$ | $K$ | $U$ | Phục vụ đủ % | gap trung vị % | gap trung bình % | Trong 10 % | Runtime s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 25, +5 | warm_alns | 0.6192 | 5.18 | 0.29 | 75.7 | 3.0 | 6.0 | 76 | 18.6 |
| 25, +5 | contextual | 0.6186 | 5.20 | 0.29 | 75.8 | 3.0 | 5.9 | 76 | 21.0 |
| 25, +12 | warm_alns | 0.7820 | 6.08 | 0.94 | 40.8 | 8.7 | 10.9 | 59 | 20.2 |
| 25, +12 | contextual | 0.7830 | 6.08 | 0.94 | 40.7 | 8.7 | 10.9 | 59 | 22.9 |
| 25, +25 | warm_alns | 0.9901 | 7.76 | 1.86 | 35.4 | 10.9 | 12.1 | 43 | 24.4 |
| 25, +25 | contextual | 0.9912 | 7.77 | 1.85 | 35.5 | 11.0 | 12.3 | 43 | 27.0 |
| 95+5 | warm_alns | 0.4803 | 14.11 | 0.21 | 82.8 | 2.9 | 5.5 | 77 | 79.7 |
| 95+5 | contextual | 0.4865 | 14.13 | 0.21 | 82.6 | 4.2 | 7.2 | 73 | 92.3 |
| 88+12 | warm_alns | 0.4902 | 14.35 | 0.55 | 51.2 | 4.1 | 5.3 | 73 | 74.3 |
| 88+12 | contextual | 0.4940 | 14.28 | 0.55 | 51.0 | 5.2 | 6.5 | 70 | 88.0 |
| 75+25 | warm_alns | 0.5763 | 14.69 | 0.73 | 40.5 | 6.0 | 6.7 | 70 | 67.5 |
| 75+25 | contextual | 0.5772 | 14.66 | 0.73 | 40.5 | 6.0 | 7.0 | 69 | 78.5 |

Clairvoyant trung bình: $F$ = 0.6045 / 0.7683 / 0.9528 (25 khách hàng) và 0.4648 / 0.4772 / 0.5540 (100 khách hàng); $K$ = 5.29 / 6.02 / 7.49 và 13.66 / 13.74 / 13.72. Runtime là thời gian một lượt khi 16 lượt chạy song song.

## 3. Contextual bandit so với roulette, theo cặp

Tham chiếu là `contextual_warm_alns`; "thắng" nghĩa là contextual tốt hơn theo $(U, K, F)$; $\Delta F$ = $F_{\text{roulette}} - F_{\text{contextual}}$, dương nghiêng về contextual.

| Mức | Cặp | Contextual thắng | Roulette thắng | Hòa | $\Delta F$ trung bình | $\Delta F$ trung vị | Wilcoxon $p$ |
|---|---:|---:|---:|---:|---:|---:|---:|
| 25, +5 | 1 800 | 192 | 201 | 1 407 | +0.0006 | 0 | 0.031 |
| 25, +12 | 1 800 | 475 | 500 | 825 | −0.0009 | 0 | 0.21 |
| 25, +25 | 1 800 | 733 | 732 | 335 | −0.0012 | 0 | 0.17 |
| 95+5 | 1 800 | 761 | 1 037 | 2 | −0.0061 | −0.0041 | 5e-16 |
| 88+12 | 1 800 | 897 | 903 | 0 | −0.0038 | −0.0026 | 3e-07 |
| 75+25 | 1 800 | 929 | 870 | 1 | −0.0009 | −0.0006 | 0.31 |

Theo lớp instance (gộp ba mức của mỗi kích thước, 1 800 cặp mỗi ô):

| Kích thước | Lớp | Contextual thắng | Roulette thắng | Hòa |
|---|---|---:|---:|---:|
| 25 | C | 455 | 445 | 900 |
| 25 | R | 606 | 622 | 572 |
| 25 | RC | 339 | 366 | 1 095 |
| 100 | C | 907 | 890 | 3 |
| 100 | R | 808 | 992 | 0 |
| 100 | RC | 872 | 928 | 0 |

## 4. Nhận xét

1. **Rolling horizon + ALNS giữ ổn định so với clairvoyant.** Gap trung vị trên lượt phục vụ đủ là 3 % ở mức động thấp và 6–11 % ở mức cao, nhất quán với benchmark 10 seed trước đó. Khoảng cách chính tới clairvoyant vẫn là khách hàng bị bỏ (0.2–1.9 mỗi lượt tùy mức), không phải $F$.
2. **Contextual bandit, như đã gộp vào master, không cải thiện.** Ở 25 khách hàng hai chính sách không phân biệt được: 20–78 % số cặp hòa hoàn toàn, $\Delta F$ trung vị bằng 0, $p$ không đạt 5 % ở hai trong ba mức (giá trị 0.031 ở mức +5 đi kèm chênh lệch 0.0006, không có ý nghĩa thực tế). Ở 100 khách hàng roulette tốt hơn rõ: $F$ thấp hơn 1.3 % (95+5) và 0.8 % (88+12) với $p < 10^{-6}$, gap trung vị 2.9 % so với 4.2 %; mức 75+25 hòa.
3. **Contextual chậm hơn 11–16 %** do chi phí tính context và LinUCB mỗi vòng lặp, trong khi $U$, $K$ và tỷ lệ phục vụ đủ gần như giống hệt. Số khách hàng bị bỏ do bước triage quyết định nên không phụ thuộc bộ chọn toán tử.
4. **Số cặp hòa cao ở 25 khách hàng** (tới 78 % ở mức +5) cho thấy với 400 vòng mỗi epoch trên instance nhỏ, cả hai bộ chọn thường hội tụ về cùng một nghiệm: ngân sách đã bão hòa, bộ chọn toán tử không còn là yếu tố quyết định.

### Vì sao bandit không giúp ở đây

- LinUCB **khởi tạo lại ở mỗi epoch** và chỉ có 400 vòng để học 15 cặp toán tử với 9 đặc trưng; bộ chọn roulette của Pha 1 cũng khởi tạo lại nhưng chỉ cần vài segment để nghiêng trọng số.
- Các đặc trưng context được thiết kế cho một lần chạy tĩnh dài (tiến độ, nhiệt độ, thời gian đình trệ). Trong một epoch ngắn chúng gần như không biến thiên, nên context mang ít thông tin.
- Kết quả này là của cấu hình mặc định đã thống nhất; nó không bác bỏ ý tưởng, chỉ nói rằng cách ghép hiện tại chưa mang lại lợi ích trong rolling horizon.

### Đề xuất cho vòng tiếp theo

1. Giữ trạng thái LinUCB (ma trận $A_a$, $b_a$) qua các epoch thay vì khởi tạo lại; đây là thay đổi nhỏ trong bộ giải contextual và là thí nghiệm có giá trị nhất.
2. Thử bandit chỉ ở epoch 0 (2 000 vòng, nơi nó có thời gian học) và roulette ở các epoch sau.
3. Khi báo cáo, trình bày contextual như một ablation của hệ thống đầy đủ: "bỏ bandit" không làm giảm chất lượng, điều này củng cố kết luận rằng warm start và thời điểm tiết lộ mới là thành phần quyết định.

## 5. Tái lập

```bash
cd phase1
bash results/logs/run_full.sh            # 6 cấu hình trong configs/dynamic/full/, ~45 h trên 16 lõi
uv run python -m uav_routing.dynamic.analysis \
  --results results/full/n25_d5 results/full/n25_d12 results/full/n25_d25 \
            results/full/n100_d5 results/full/n100_d12 results/full/n100_d25 \
  --reference contextual_warm_alns --output results/analysis/full_policies.md
```

Mỗi thư mục `results/full/<mức>/` có `raw.csv` (một dòng cho mỗi kịch bản × seed × chính sách, kèm clairvoyant và gap) và `aggregate.csv`. Cùng kịch bản, cấu hình và seed tái tạo đúng từng dòng.

# Chẩn đoán nút thắt ALNS trước khi tiếp tục tối ưu contextual bandit

## Phạm vi và cách đo

Đọc mã hiện tại, sau đó chạy lại vòng lặp contextual với cấu hình trong
`configs/benchmark_p1_c25_r5.json` trên C101, 100 khách hàng, 5 vùng rủi ro,
100 iteration và seed 0–9. Vòng lặp được instrument tạm thời để đếm candidate,
không sửa toán tử, phép chọn, acceptance hay reward. Seed 0 cho 10 UAV và
objective 0.6618, khớp kết quả đã ghi trong optimization study.

Các số dưới đây là chẩn đoán trên đúng một instance, không phải bằng chứng cho
toàn bộ Solomon-RISK.

| Chỉ số | 10 seed, tổng 1000 iteration |
|---|---:|
| Repair thành công và candidate khả thi | 1000 |
| Candidate giống hệt current solution | 602 |
| Candidate giảm số UAV so với current | 6 |
| Candidate giảm objective khi số UAV bằng current | 196 |
| Candidate được acceptance chấp nhận, kể cả nghiệm giống hệt | 923 |
| Reward bằng 0 | 729 |
| Số UAV tốt nhất trung bình | 11.4 |

Phân rã theo destroy operator cho thấy chính xác nơi action bị thoái hóa:

| Destroy | Số lượt | Candidate giống current | Candidate giảm UAV |
|---|---:|---:|---:|
| `random` | 177 | 151 | 0 |
| `worst` | 208 | 140 | 0 |
| `related` | 196 | 154 | 0 |
| `risk_priority` | 203 | 149 | 0 |
| `route` | 216 | 8 | 6 |

Nghiệm ban đầu C101 có 12 route với kích thước đã sắp xếp:
`2, 4, 8, 8, 9, 9, 9, 9, 10, 10, 11, 11`. Chỉ 15/100 khách hàng có risk
priority dương. Tổng risk priority là 5.882. Tại nghiệm ban đầu, thành phần
distance của objective là 0.5, còn thành phần risk delay là 0.2634.

## Nguyên nhân có bằng chứng trong mã

1. **Neighborhood có nhiều lượt không đổi nghiệm.** `q_min=2`, `q_max=5`;
   bốn destroy operator chỉ xóa tối đa 5 khách hàng. `RouteRemoval` xóa cả
   route nhưng chọn route đồng đều, không ưu tiên route dễ hấp thụ. Cả ba repair
   đều là insertion tất định, thường đưa khách hàng về đúng vị trí cũ. Con số
   602/1000 lượt giống hệt current là tín hiệu trực tiếp. Cả sáu lượt giảm số
   UAV đều từ `RouteRemoval`; bốn destroy còn lại có 594/784 lượt giống current.
   Tăng độ phức tạp của selector trong khi action hầu như không tạo candidate
   mới sẽ có lợi ích thấp.

2. **Reward không phản ánh độ lớn cải thiện theo score từ điển.** `classify_reward`
   trả `reward_best=20` cho mọi best mới, dù chỉ giảm rất nhỏ objective thứ cấp;
   một candidate giảm số UAV nhưng chưa vượt best chỉ nhận
   `reward_improve=10`. Điều này hợp lệ theo rule hiện tại, nhưng lệch mục tiêu
   ưu tiên số UAV. Reward `accepted=2` cũng phụ thuộc nhiệt độ và không đo
   chất lượng candidate. Trên C101, 729/1000 phản hồi bằng 0 nên LinUCB có
   rất ít tín hiệu phân biệt arm.

3. **Đối chứng roulette chưa thực sự thích nghi trong benchmark ngắn.** Với
   `segment_length=iterations=100`, `AdaptivePool.update_segment()` chỉ chạy
   sau iteration cuối. Mọi weight ban đầu bằng 1, nên selection gần như đều
   suốt 100 iteration. So sánh hiện tại chứng minh contextual so với roulette
   đồng đều, chưa chứng minh contextual tốt hơn ALNS adaptive được cập nhật
   trong quá trình tìm kiếm.

4. **Acceptance và context thay đổi ít.** Nhiệt độ giảm từ 0.05 xuống khoảng
   0.0476 trong 100 iteration; 923/1000 candidate được chấp nhận, phần lớn là
   nghiệm giống current. Thành phần temperature trong context gần như hằng và
   đồng biến với progress. `vehicle_gap` bằng 0 phần lớn thời gian do chính
   acceptance từ chối mọi candidate tăng số UAV. Vì thế context 9 chiều chứa
   nhiều tọa độ yếu hoặc dư thừa cho run ngắn.

5. **Objective cần đánh giá theo ý nghĩa nghiệp vụ, chưa có lỗi tính toán rõ.**
   Score $(K,F)$ thực hiện đúng thứ tự từ điển đã mô tả trong README. Tuy nhiên
   chỉ 15 khách hàng C101 có risk priority dương, nên thành phần risk không
   phân biệt nhiều phép chuyển khách hàng ngoài vùng. Hệ số $\alpha=\beta=0.5$
   không có nghĩa hai thành phần đóng góp tương đương ở mọi nghiệm. Cần báo
   cáo riêng $K$, distance và risk delay, đồng thời kiểm tra độ nhạy của
   $\beta$ trước khi đổi mô hình mục tiêu.

## Thứ tự thử nghiệm đề xuất

1. **Sửa neighborhood trước.** Thêm destroy `small_route` chọn một route ngắn
   hoặc route có chi phí cao nhưng có khả năng hấp thụ, rồi repair với điều kiện
   cấm mở lại route đó trong lần thử đầu. Nếu thất bại, dùng fallback repair
   hiện tại. Đo tỷ lệ candidate khác current, tỷ lệ giảm $K$, tỷ lệ repair
   thất bại và runtime. Thử các mức $q$ lớn hơn theo tỷ lệ khách hàng, nhưng
   giữ `RouteRemoval` riêng vì nó không tuân theo $q$.

2. **Làm đối chứng công bằng.** Chạy baseline với `segment_length` nhỏ hơn
   ngân sách, chẳng hạn 10 và 20, cùng seed và instance. Giữ thêm đối chứng
   roulette đều rõ tên. Điều chỉnh ngân sách bằng cả iteration lẫn thời gian,
   vì các action có chi phí rất khác nhau.

3. **Thử reward có thứ tự ưu tiên rõ.** Một ablation riêng có thể dùng reward
   giảm $K$ lớn nhất, sau đó reward liên tục theo $\max(0, F_{current}-F_{cand})$
   khi $K$ bằng nhau, với ngưỡng chuẩn hóa cố định theo instance. Không thưởng
   nghiệm giống current. Ghi riêng reward cho accepted-worse để tránh thưởng
   một bước chỉ vì nhiệt độ cao. So sánh với reward rời rạc gốc trên held-out
   seed; nghiên cứu trước đã thử một reward liên tục nhưng không thắng ổn định.

4. **Giảm độ thưa học của selector.** Bắt đầu từ context ít chiều gồm bias,
   stagnation, $K$, tỷ lệ route ngắn, và giai đoạn search; thêm $q$ hoặc tỷ lệ
   khách hàng bị xóa khi selector thực sự chọn $q$. Thử mô hình chia sẻ tham số
   theo destroy và repair, hoặc selector hai tầng, trước khi warm-start qua
   instance. Cần kiểm tra tương tác cặp, vì chia sẻ reward một cách đơn giản
   có thể làm mất thông tin tương tác.

5. **Đánh giá ngoài C101.** Chọn trước tập train/tune và held-out gồm C, R,
   RC; dùng 20–30 seed mỗi instance, báo paired difference của $K$, sau đó
   so $F$ khi $K$ bằng nhau, cùng khoảng tin cậy và runtime. Không chọn cấu
   hình cuối theo seed 0. Thực nghiệm phải tách tác dụng neighborhood, reward,
   context và selector bằng ablation tuần tự.

## Kết luận tạm thời

Ưu tiên hiện tại là tăng xác suất tạo candidate mới và giảm $K$; sau đó mới
đánh giá reward và mô hình bandit. Việc chỉ tinh chỉnh LinUCB trên action space
hiện tại khó tạo cải thiện lớn trong 100 iteration. Đây là giả thuyết có hỗ trợ
bởi phép đo C101, cần kiểm chứng trên nhiều instance.

## Ablation tiếp theo: nới score trong acceptance và chọn route ngắn

Hai thử nghiệm sau giữ nguyên score từ điển để lưu `best`, cách tính objective,
reward và LinUCB. Chúng chỉ thay đổi từng cơ chế một. Mã chạy lại ở
`experiments/score_route_ablation.py`; dữ liệu thô ở
`results/score_route_ablation/`.

### Score mềm cho acceptance

Thay acceptance từ điển bằng simulated annealing trên
$M_\lambda(S)=\lambda K(S)+F(S)$, với $\lambda\in\{0.1,0.25,0.5\}$.
Nghiệm cuối vẫn là `best` theo $(K,F)$. So trên C101, C102, R101,
seed 0–4, 100 iteration:

| Chính sách | Thắng lex | Thua lex | Hòa lex | Chênh lệch UAV trung bình |
|---|---:|---:|---:|---:|
| $\lambda=0.1$ | 5 | 5 | 5 | -0.067 |
| $\lambda=0.25$ | 4 | 6 | 5 | 0 |
| $\lambda=0.5$ | 4 | 6 | 5 | 0 |

`Thắng` và `thua` dùng score cuối $(K,F)$ theo thứ tự từ điển trên từng cặp
instance–seed. Chênh lệch UAV âm là tốt hơn. Ba mức phạt chưa cho bằng chứng
rằng nới acceptance giúp search. Trên C101, trong chẩn đoán gốc chỉ có 10/1000
candidate tăng số UAV; vì vậy cơ hội để chính sách acceptance mới tác động
vốn đã rất hiếm. Việc đổi cả tiêu chí chọn `best` sang scalar sẽ thay đổi mục
tiêu bài toán và cần định giá nghiệp vụ rõ ràng cho một UAV bổ sung.

### Ưu tiên route ngắn trong `RouteRemoval`

So `uniform` hiện tại với `shortest` (chọn ngẫu nhiên giữa các route ngắn nhất)
và `inverse` (xác suất tỷ lệ nghịch với số khách hàng). Mọi cơ chế khác giữ
nguyên. Trên C101, C102, R101, seed 0–9, 100 iteration:

| Instance | Uniform: UAV TB | Shortest: UAV TB | Inverse: UAV TB |
|---|---:|---:|---:|
| C101 | 11.4 | 10.9 | 11.3 |
| C102 | 10.0 | 10.0 | 10.0 |
| R101 | 21.0 | 21.1 | 21.2 |

Trên 30 cặp, `shortest` thắng `uniform` 19 lần và thua 11 lần theo $(K,F)$;
`inverse` thắng 17 và thua 13. C101 cải thiện rõ hơn, nhưng R101 hơi kém.
Chưa có lý do thay mặc định bằng `shortest` chỉ từ ba instance và 10 seed.
Nên thử thêm route elimination có khả năng tái chèn vào các route khác, và
kiểm tra trên tập C/R/RC đã tách khỏi tập dùng để chọn biến thể.

Chạy lại hai ablation từ thư mục `phase1`:

```bash
uv run python experiments/score_route_ablation.py \
  --seeds 5 --policies lex soft_0.1 soft_0.25 soft_0.5 \
  --output results/score_route_ablation/score_5_seeds.csv

uv run python experiments/score_route_ablation.py \
  --seeds 10 --policies lex shortest inverse \
  --output results/score_route_ablation/route_10_seeds.csv
```

## Có nên dừng trước 100 iteration?

Đã ghi lại thời điểm lập `best` trong 30 run contextual đầy đủ: C101, C102,
R101, mỗi instance 10 seed và 100 iteration. Sau đó mô phỏng quy tắc dừng
khi không có `best` mới trong một số iteration liên tiếp. Vì trace tới điểm
dừng giống hệt run đầy đủ, phép so nghiệm tại điểm dừng là chính xác; tỷ lệ
tiết kiệm **thời gian** chỉ là ước lượng từ số iteration vì chi phí mỗi operator
khác nhau.

| Patience | Số iteration trung bình tới khi dừng | Run dùng thêm UAV so với đủ 100 | Run có score từ điển kém hơn |
|---:|---:|---:|---:|
| 20 | 57.8 | 6/30 | 17/30 |
| 30 | 81.7 | 3/30 | 8/30 |
| 40 | 88.4 | 2/30 | 5/30 |
| 50 | 93.9 | 1/30 | 2/30 |

Best cuối xuất hiện sau iteration 70 ở 23/30 run. Dừng vì trì trệ không đủ
an toàn cho kết quả báo cáo: patience 30 chỉ giảm khoảng 18% số lượt nhưng làm
xấu số UAV ở 3 run. Vì vậy script ablation có `--iterations` để chạy vòng sàng
lọc ngắn, rồi chạy lại các cấu hình được chọn với cùng ngân sách 100 iteration
trên tập đánh giá cuối. `--seeds` và `--policies` tiếp tục giúp giới hạn số
run; CSV ghi cả ngân sách iteration để tránh trộn kết quả.

Ví dụ sàng lọc nhanh từ thư mục `phase1`:

```bash
uv run python experiments/score_route_ablation.py \
  --instances c101 c102 r101 --seeds 3 --iterations 20 \
  --policies lex shortest soft_0.1 \
  --output results/score_route_ablation/screen_20.csv
```

Lượt sàng lọc này gồm 27 run và đã được lưu ở `screen_20.csv`. Trên ba seed
R101, cả ba chính sách đều có 22.33 UAV trung bình ở 20 iteration, nhưng khi
chạy đủ 100 iteration thì `lex` và `soft_0.1` đạt 21.0, còn `shortest` đạt
21.33. Vì vậy ngân sách ngắn chỉ dùng để loại ứng viên rõ ràng kém hoặc ước
lượng chi phí, không dùng để kết luận chính sách tốt nhất.

## Ablation tiếp theo: tập arm, kích thước phá nghiệm và warm start

Để tìm chất lượng tốt hơn trong ít iteration, đã kiểm tra ba hướng trên C101,
C102 và R101. Cùng một seed giữ nguyên cấu hình LinUCB và score cuối $(K,F)$.
Các CSV nằm trong `results/score_route_ablation/`.

**Giảm số arm đơn thuần không hiệu quả.** Sau 50 iteration và 5 seed, tập chỉ
gồm `route` × 3 repair (3 arm) thắng bản 15 arm ở 5/15 cặp, thua 10/15; tập
`route` hoặc `random` × 3 repair (6 arm) thắng 3/15, thua 12/15. Chỉ chọn
route ngắn với 3 arm rất nhanh nhưng R101 giữ nguyên 23 UAV ở cả 5 seed,
trong khi bản 15 arm đạt 21 UAV trung bình. Bandit cần đủ loại neighborhood để
tiếp tục cải thiện distance và risk sau khi thử giảm số UAV.

**Tăng $q$ làm mỗi lượt đắt hơn, chưa giúp giảm UAV.** Trên C101 và R101,
seed 0–2, 50 iteration, thay $q\in[2,5]$ bằng $[6,10]$ hoặc $[8,12]$ không
cải thiện số UAV trung bình; runtime tăng khoảng 2–4 lần tùy instance.
Đây là thử nghiệm nhỏ, nhưng không ủng hộ việc tăng $q$ đồng loạt.

**Warm start có điều kiện giúp tìm ít UAV sớm hơn.** Trước LinUCB, xét tối đa
8 route có không quá 5 khách hàng, thử ba repair, nhận route đầu tiên có thể
được hấp thụ hoàn toàn; lặp tối đa 3 lần. Không thay $D_{\mathrm{ref}}$, score,
reward hoặc số iteration LinUCB. Toàn bộ chi phí này nằm trong runtime.

| Instance | Iteration | Bản gốc: UAV TB / giây TB | Warm start: UAV TB / giây TB |
|---|---:|---:|---:|
| C101 | 20 | 11.8 / 0.37 | 11.0 / 0.43 |
| C102 | 20 | 10.0 / 0.47 | 10.0 / 0.47 |
| R101 | 20 | 22.6 / 0.29 | 20.9 / 0.65 |
| C101 | 100 | 11.4 / 1.88 | 11.0 / 1.90 |
| C102 | 100 | 10.0 / 2.16 | 10.0 / 2.16 |
| R101 | 100 | 21.0 / 1.30 | 20.4 / 1.63 |

Mỗi dòng dùng 10 seed. Sau 100 iteration, warm start thắng bản gốc theo
$(K,F)$ ở 15/30 cặp, thua 5/30 và hòa 10/30. Riêng C101 seed 0, bản gốc đạt
10 UAV còn warm start đạt 11, nên chưa được bật mặc định. C102 không có route
ngắn và giữ nguyên trajectory. Kết quả chứng minh lợi ích của tiền xử lý
route, không chứng minh LinUCB chọn arm tốt hơn. Khi so với baseline, cần áp
dụng cùng warm start cho baseline hoặc báo ablation tách biệt.

Đã thêm `short_route_warm_start` vào cấu hình contextual, mặc định `false`.
Lệnh `solve --algorithm contextual` có cờ `--short-route-warm-start`; cấu hình
benchmark JSON có thể đặt `"short_route_warm_start": true` trong
`contextual_bandit`. CSV benchmark tách nhóm theo cờ này.

Kiểm tra thêm trên ba instance chưa dùng để chọn biến thể, 5 seed mỗi instance:

| Instance | Iteration | Bản gốc: UAV TB / giây TB | Warm start: UAV TB / giây TB |
|---|---:|---:|---:|
| C103 | 20 | 10.0 / 0.50 | 10.0 / 0.50 |
| R102 | 20 | 20.0 / 0.39 | 20.0 / 0.58 |
| RC101 | 20 | 19.6 / 0.27 | 18.4 / 0.48 |
| C103 | 100 | 10.0 / 2.40 | 10.0 / 2.42 |
| R102 | 100 | 18.6 / 1.78 | 18.6 / 1.96 |
| RC101 | 100 | 17.8 / 1.36 | 17.4 / 1.54 |

Ở 100 iteration, warm start thắng 2 và thua 3 trên 15 cặp held-out theo
$(K,F)$; 10 cặp còn lại hòa. Lợi ích rõ nhất là số UAV trong ngân sách 20
iteration trên RC101; R102 bị tăng runtime mà không cải thiện score. Do đó
không có cơ sở bật mặc định hay tuyên bố chất lượng cuối tốt hơn trên mọi
instance. Không có cận tối ưu cho nghiệm tìm được; đây là best-known theo
ngân sách thử nghiệm.

Để chạy lại phép so chính từ thư mục `phase1`:

```bash
uv run python experiments/score_route_ablation.py \
  --instances c101 c102 r101 --seeds 10 --iterations 20 \
  --policies lex warm_route_small \
  --output results/score_route_ablation/warm_small_20.csv
```

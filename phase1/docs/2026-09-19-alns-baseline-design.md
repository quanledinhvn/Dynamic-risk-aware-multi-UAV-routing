# Thiết kế ALNS baseline cho Pha 1

## 1. Mục tiêu và phạm vi

Pha 1 hiện thực một baseline Adaptive Large Neighborhood Search (ALNS) cho bài toán static risk-aware multi-UAV routing. Baseline sử dụng dữ liệu Solomon VRPTW đã được bổ sung các vùng risk hình tròn. Vùng risk biểu diễn khu vực có nhiệm vụ khẩn cấp cần được phục vụ sớm, không phải vùng cấm bay hoặc vùng gây nguy hiểm cho UAV.

Phạm vi benchmark ban đầu gồm chín instance:

- `C101`, `C102`, `C103`;
- `R101`, `R102`, `R103`;
- `RC101`, `RC102`, `RC103`.

Mỗi instance chỉ sử dụng depot và 25 khách hàng đầu tiên. Solver phải nhận được số khách hàng qua cấu hình để phạm vi có thể mở rộng mà không đổi mã nguồn.

Toàn bộ mã nguồn, kiểm thử, cấu hình, tài liệu và kết quả của Pha 1 nằm trong thư mục `phase1/`. Solver được viết bằng Python 3, không dùng OR-Tools, Gurobi hoặc một solver tối ưu bên ngoài. NumPy được dùng cho ma trận khoảng cách và bộ sinh số ngẫu nhiên; pytest được dùng để kiểm thử.

## 2. Giả định mô hình

- Mọi UAV đồng nhất, xuất phát từ depot và trở về depot.
- Số UAV tối đa và capacity được đọc từ instance Solomon.
- Mỗi khách hàng được phục vụ đúng một lần.
- Mỗi khách hàng có tọa độ, demand, ready time, due date và service time.
- Khoảng cách giữa hai điểm là khoảng cách Euclidean.
- Tốc độ UAV bằng 1, do đó thời gian di chuyển bằng khoảng cách.
- Capacity, time window và due date của depot là các ràng buộc cứng.
- Pin, gió, vùng cấm bay và thay đổi động chưa thuộc phạm vi Pha 1.
- ALNS chỉ chấp nhận candidate hoàn chỉnh và khả thi. Partial solution ngay sau destroy được phép thiếu khách hàng nhưng không được coi là candidate.

## 3. Biểu diễn dữ liệu và nghiệm

### 3.1. Dữ liệu đầu vào

Một `Instance` chứa:

- depot;
- danh sách khách hàng đã giới hạn theo cấu hình;
- danh sách vùng risk;
- số UAV tối đa;
- capacity;
- ma trận khoảng cách đối xứng;
- risk priority của từng khách hàng.

Một vùng risk `z` có tâm `(x_z, y_z)` và bán kính `r_z`.

### 3.2. Lời giải

Một `Solution` là danh sách các tuyến không rỗng. Tuyến của UAV `k` được biểu diễn bởi thứ tự khách hàng:

```text
0 -> v1 -> v2 -> ... -> vm -> 0
```

Depot không cần lưu lặp lại trong danh sách khách hàng của tuyến; evaluator bổ sung hai chặng depot khi tính lịch và quãng đường.

Một nghiệm hoàn chỉnh phải chứa mỗi khách hàng đúng một lần. Số UAV được sử dụng là số tuyến không rỗng:

\[
K(S)=|\{R_k: |R_k|>0\}|.
\]

## 4. Lịch tuyến và ràng buộc

Với khách hàng `i` đứng sau điểm `j`, thời điểm đến, bắt đầu phục vụ và rời đi lần lượt là:

\[
a_i=\operatorname{departure}_j+d_{ji},
\]

\[
s_i=\max(a_i,e_i),
\]

\[
\operatorname{departure}_i=s_i+\operatorname{service}_i.
\]

Trong đó `e_i` là ready time. Việc đến trước ready time tạo thời gian chờ và không tạo vi phạm.

Một tuyến khả thi khi đồng thời thỏa:

1. Tổng demand không vượt capacity.
2. Với mọi khách hàng, `s_i <= l_i`, trong đó `l_i` là due date.
3. Thời điểm trở về depot không vượt due date của depot.

Một nghiệm khả thi khi mọi tuyến khả thi, không vượt số UAV tối đa và mỗi khách hàng xuất hiện đúng một lần.

`evaluator.py` là nguồn duy nhất tính lịch, tính khả thi và các thành phần mục tiêu. Operator không tự diễn giải lại time window.

## 5. Risk priority

Với khách hàng `i` và vùng risk `z`, khoảng cách từ khách hàng đến tâm vùng là:

\[
d_{iz}=\sqrt{(x_i-x_z)^2+(y_i-y_z)^2}.
\]

Ảnh hưởng của vùng `z` lên khách hàng `i` là:

\[
p_{iz}=\max\left(0,1-\frac{d_{iz}}{r_z}\right).
\]

Risk priority của khách hàng lấy ảnh hưởng lớn nhất nếu các vùng chồng nhau:

\[
p_i=\max_{z\in Z}p_{iz}.
\]

Do đó `p_i` nằm trong `[0,1]`: khách hàng gần tâm có priority cao; khách hàng ở biên hoặc ngoài mọi vùng có priority bằng 0.

## 6. Risk delay và hàm mục tiêu

### 6.1. Độ trễ tương đối

Với một nghiệm khả thi, vị trí phục vụ tương đối của khách hàng trong time window là:

\[
q_i=\frac{s_i-e_i}{\max(1,l_i-e_i)}.
\]

`q_i = 0` nghĩa là phục vụ ngay khi time window mở; `q_i = 1` nghĩa là phục vụ tại due date. Ràng buộc time window bảo đảm `q_i` nằm trong `[0,1]`.

Risk delay của nghiệm là trung bình có trọng số priority:

\[
R(S)=
\frac{
\sum_{i\in N}p_iq_i
}{
\sum_{i\in N}p_i
}.
\]

Nếu tổng priority bằng 0, quy ước `R(S) = 0`. Với nghiệm khả thi, `R(S)` nằm trong `[0,1]` và giá trị nhỏ hơn biểu diễn việc phục vụ các nhiệm vụ nguy cấp sớm hơn.

### 6.2. Quãng đường tham chiếu

Nghiệm greedy ban đầu được ký hiệu là `S_0`. Quãng đường tham chiếu được tính một lần:

\[
D_{\mathrm{ref}}=D(S_0),
\]

và không thay đổi trong quá trình ALNS. Nó chỉ dùng để đưa thành phần quãng đường về thang đo gần với risk delay; nó không phải nghiệm tối ưu đã biết.

### 6.3. Objective distance-risk

Với `alpha >= 0`, `beta >= 0` và `alpha + beta = 1`:

\[
F(S)=
\alpha\frac{D(S)}{D_{\mathrm{ref}}}
+\beta R(S).
\]

Cấu hình mặc định dùng `alpha = beta = 0.5`. Thí nghiệm sensitivity có thể thay đổi `beta` và đặt `alpha = 1 - beta`.

### 6.4. Mục tiêu từ điển

Solver ưu tiên giảm số UAV trước, sau đó mới giảm objective distance-risk:

\[
\operatorname{Score}(S)=\left(K(S),F(S)\right).
\]

Nghiệm `S_1` tốt hơn `S_2` khi `K(S_1) < K(S_2)`, hoặc khi hai nghiệm dùng cùng số UAV và `F(S_1) < F(S_2)`.

Các kết quả phải báo cáo riêng số UAV, tổng quãng đường, risk delay và objective, không chỉ báo một scalar tổng hợp.

## 7. Nghiệm ban đầu

Nghiệm ban đầu phải khả thi và xác định:

1. Sắp khách hàng theo `(due_date tăng, risk_priority giảm, customer_id tăng)`.
2. Với từng khách hàng, thử mọi vị trí trên các tuyến hiện có.
3. Giữ các vị trí chèn khả thi và chọn vị trí tăng quãng đường ít nhất; dùng chỉ số tuyến và vị trí chèn để phá hòa.
4. Nếu không có vị trí khả thi, mở một tuyến mới nếu chưa vượt số UAV tối đa.
5. Nếu không thể chèn một khách hàng, dừng với lỗi không xây được nghiệm ban đầu khả thi.
6. Tính `D_ref` sau khi hoàn tất `S_0`.

## 8. Destroy operators

Số khách hàng cần tháo `q` được lấy ngẫu nhiên trong đoạn cấu hình; mặc định với 25 khách hàng là `[2,5]`.

### 8.1. RandomRemoval

Chọn ngẫu nhiên `q` khách hàng đang được phục vụ và tháo khỏi các tuyến.

### 8.2. WorstRemoval

Ước lượng đóng góp biên của từng khách hàng bằng thay đổi objective trên tuyến khi tháo khách hàng đó. Ưu tiên tháo khách hàng có đóng góp chi phí lớn, với nhiễu ngẫu nhiên có kiểm soát để tránh luôn lặp lại cùng một lựa chọn.

### 8.3. RelatedRemoval

Chọn ngẫu nhiên một seed customer, sau đó ưu tiên tháo các khách hàng liên quan theo tổ hợp đã chuẩn hóa của:

- khoảng cách không gian;
- độ gần time window;
- chênh lệch demand;
- chênh lệch risk priority.

Các trọng số relatedness nằm trong cấu hình.

### 8.4. RouteRemoval

Chọn một tuyến và tháo toàn bộ khách hàng của tuyến. Operator này tạo cơ hội chèn các khách hàng vào những tuyến còn lại để giảm số UAV. Nếu tuyến có nhiều hơn `q_max` khách hàng, operator vẫn tháo toàn tuyến vì đơn vị phá của nó là một route.

### 8.5. RiskPriorityRemoval

Ưu tiên tháo các khách hàng có risk priority cao để repair có thể đưa chúng tới vị trí phục vụ sớm hơn. Việc chọn trong nhóm priority cao có thành phần ngẫu nhiên để duy trì đa dạng tìm kiếm.

## 9. Repair operators

Repair chỉ hoàn thành thành công khi chèn lại toàn bộ khách hàng và tạo candidate khả thi. Nếu không có vị trí khả thi cho một khách hàng, candidate bị hủy và nghiệm hiện tại được giữ nguyên.

Mỗi phép thử chèn phải đánh giá lại lịch của toàn bộ phần tuyến từ vị trí chèn trở về sau, vì thời điểm phục vụ của các khách hàng phía sau có thể thay đổi.

Vị trí chèn được so sánh theo chi phí từ điển `(delta_K, delta_F)`. Chèn vào một tuyến hiện có có `delta_K = 0`; mở tuyến mới có `delta_K = 1`. Vì vậy repair chỉ mở tuyến mới khi không còn cách chèn khả thi vào các tuyến hiện có cho khách hàng cần xử lý, và không bao giờ vượt số UAV tối đa. Trong các vị trí có cùng `delta_K`, vị trí có `delta_F` nhỏ hơn được ưu tiên.

### 9.1. GreedyRepair

Trong tất cả cặp khách hàng-vị trí khả thi, chọn cặp có `(delta_K, delta_F)` nhỏ nhất. Lặp lại cho tới khi tập chưa gán rỗng.

### 9.2. Regret2Repair

Với mỗi khách hàng chưa gán, chỉ xét các vị trí có `delta_K` nhỏ nhất rồi tìm hai vị trí có `delta_F` tốt nhất. Regret là chênh lệch `delta_F` giữa vị trí tốt thứ hai và tốt nhất. Chèn trước khách hàng có regret lớn nhất vào vị trí tốt nhất. Nếu chỉ có một vị trí khả thi ở mức `delta_K` tốt nhất, regret của khách hàng được coi là vô hạn để nó được xử lý ngay.

### 9.3. RiskPriorityRepair

Sắp khách hàng chưa gán theo `(risk_priority giảm, due_date tăng, customer_id tăng)`. Với từng khách hàng theo thứ tự này, chọn vị trí khả thi có `(delta_K, delta_F)` nhỏ nhất.

GreedyRepair và Regret2Repair cũng đánh giá vị trí bằng objective có chứa risk delay. RiskPriorityRepair khác ở chỗ nó dành quyền chọn vị trí cho khách hàng priority cao trước.

## 10. Vòng lặp ALNS

ALNS duy trì nghiệm hiện tại `S`, nghiệm tốt nhất `S_best`, trọng số, tổng điểm và số lần dùng của từng operator.

Mỗi vòng lặp:

1. Chọn một destroy và một repair theo roulette-wheel dựa trên trọng số.
2. Áp dụng destroy lên bản sao của nghiệm hiện tại.
3. Áp dụng repair để tạo candidate hoàn chỉnh.
4. Hủy candidate nếu repair thất bại hoặc evaluator xác định candidate không khả thi.
5. Áp dụng tiêu chuẩn chấp nhận.
6. Cập nhật `S_best` theo thứ tự từ điển `(K,F)`.
7. Ghi thưởng cho hai operator đã dùng.
8. Sau mỗi segment, cập nhật trọng số operator.
9. Giảm nhiệt độ.

Điều kiện dừng của Pha 1 là số vòng lặp cố định. Mọi lần chạy nhận một seed và toàn bộ lựa chọn ngẫu nhiên đi qua một NumPy `Generator` duy nhất.

## 11. Tiêu chuẩn chấp nhận

So sánh candidate `S'` với nghiệm hiện tại `S`:

- Nếu `K(S') < K(S)`, luôn chấp nhận.
- Nếu `K(S') > K(S)`, luôn từ chối.
- Nếu số UAV bằng nhau và `F(S') <= F(S)`, chấp nhận.
- Nếu số UAV bằng nhau và `F(S') > F(S)`, chấp nhận với xác suất:

\[
\Pr(\text{accept})=
\exp\left(-\frac{F(S')-F(S)}{T}\right).
\]

Nhiệt độ giảm theo geometric cooling. Nhiệt độ đầu, cooling rate và nhiệt độ tối thiểu nằm trong cấu hình.

Việc không chấp nhận nghiệm dùng nhiều UAV hơn bảo toàn ưu tiên chính của objective từ điển. RouteRemoval và repair tạo cơ hội giảm số UAV trực tiếp mà không cần đi qua một candidate hoàn chỉnh có nhiều UAV hơn.

## 12. Cơ chế adaptive

Mỗi destroy và repair operator có trọng số ban đầu bằng nhau. Sau một lần sử dụng, operator nhận:

- `20` điểm nếu tạo best-so-far mới;
- `10` điểm nếu cải thiện nghiệm hiện tại nhưng không tạo best-so-far;
- `2` điểm nếu candidate xấu hơn nhưng được Simulated Annealing chấp nhận;
- `0` điểm nếu candidate bị từ chối hoặc repair thất bại.

Sau mỗi segment, với operator đã được dùng ít nhất một lần:

\[
w_o\leftarrow
(1-\rho)w_o+
\rho\frac{\operatorname{score}_o}{\operatorname{count}_o}.
\]

Operator không được dùng trong segment giữ nguyên trọng số. Điểm và số lần dùng được đặt lại sau khi cập nhật. Trọng số được chặn bởi một giá trị dương tối thiểu trong cấu hình để mọi operator vẫn có khả năng được chọn.

## 13. Kiến trúc mã nguồn

```text
phase1/
├── pyproject.toml
├── README.md
├── configs/
├── docs/
├── results/
├── scripts/
├── src/uav_routing/
│   ├── __init__.py
│   ├── models.py
│   ├── parser.py
│   ├── geometry.py
│   ├── evaluator.py
│   ├── initial.py
│   ├── destroy.py
│   ├── repair.py
│   ├── adaptive.py
│   ├── alns.py
│   ├── cli.py
│   └── experiment.py
└── tests/
    ├── test_parser.py
    ├── test_geometry.py
    ├── test_evaluator.py
    ├── test_initial.py
    ├── test_destroy.py
    ├── test_repair.py
    ├── test_adaptive.py
    └── test_alns.py
```

Trách nhiệm chính:

- `models.py`: các cấu trúc dữ liệu miền bài toán và kết quả đánh giá.
- `parser.py`: đọc định dạng Solomon có phần mở rộng `RISK`.
- `geometry.py`: ma trận khoảng cách và risk priority.
- `evaluator.py`: lịch tuyến, feasibility, `D`, `R`, `F` và score.
- `initial.py`: xây nghiệm greedy và xác định `D_ref`.
- `destroy.py`, `repair.py`: các operator độc lập với vòng điều phối.
- `adaptive.py`: roulette selection, thống kê thưởng và cập nhật trọng số.
- `alns.py`: vòng lặp tìm kiếm, acceptance và cooling.
- `cli.py`: chạy một instance.
- `experiment.py`: chạy benchmark nhiều instance/seed và tổng hợp kết quả.

## 14. Giao diện chạy và đầu ra

Ví dụ chạy một instance:

```bash
cd phase1
python -m uav_routing.cli solve \
  --instance ../dataset/solomon_risk/c101.txt \
  --customers 25 \
  --iterations 10000 \
  --seed 42 \
  --alpha 0.5 \
  --beta 0.5
```

Đầu ra console và JSON của một lần chạy gồm:

- instance, số khách hàng, seed và số vòng lặp;
- số UAV, tổng quãng đường, risk delay và objective;
- runtime và trạng thái khả thi;
- số lần dùng và trọng số cuối của từng operator;
- các tuyến và lịch phục vụ từng khách hàng.

Benchmark ban đầu chạy chín instance đã nêu. Cấu hình phát triển dùng 10 seed; cấu hình kết quả chính có thể tăng lên 20-30 seed. CSV từng lần chạy lưu các metric thô. CSV tổng hợp lưu mean, standard deviation, best và worst theo instance và cấu hình.

## 15. Xử lý lỗi

Solver dừng với thông báo rõ ràng khi:

- file đầu vào sai định dạng;
- không có depot hoặc không đủ số khách hàng yêu cầu;
- capacity, số UAV hoặc risk radius không hợp lệ;
- `alpha` hoặc `beta` âm, hoặc tổng của chúng khác 1 ngoài sai số số thực;
- tham số ALNS không hợp lệ;
- không xây được nghiệm ban đầu khả thi;
- nghiệm tốt nhất cuối cùng không vượt qua kiểm tra độc lập về feasibility và tính đầy đủ.

Repair thất bại trong một vòng lặp chỉ làm candidate bị hủy; nó không làm dừng toàn bộ lần chạy.

## 16. Kiểm thử và tiêu chí hoàn thành

### 16.1. Unit tests

- Parser đọc đúng depot, vehicle limit, capacity, 25 khách hàng và các vùng risk.
- Distance đúng với các tọa độ có kết quả biết trước.
- Risk priority đúng tại tâm, trong vùng, trên biên và ngoài vùng.
- Lịch tuyến xử lý đúng thời gian đến, chờ, phục vụ và trở về depot.
- Evaluator phát hiện vi phạm capacity, time window, depot deadline, khách hàng thiếu hoặc trùng.
- `R(S)` nằm trong `[0,1]` cho mọi nghiệm khả thi thử nghiệm.
- Objective và so sánh score từ điển cho kết quả đúng.
- Nghiệm greedy là xác định và khả thi.
- Destroy trả đúng tập khách hàng bị tháo mà không tạo bản sao trùng.
- Repair thành công khôi phục đúng toàn bộ tập khách hàng.
- Adaptive selection và cập nhật trọng số đúng công thức.
- Simulated Annealing xử lý đúng các nhánh tốt hơn, xấu hơn và khác số UAV.

### 16.2. Integration tests

- Cùng instance, cấu hình và seed tạo cùng kết quả.
- ALNS trên instance nhỏ trả về nghiệm hoàn chỉnh, khả thi.
- Smoke test với 25 khách hàng và số vòng lặp thấp chạy được từ CLI.
- Benchmark runner tạo CSV đúng schema cho chín instance.

### 16.3. Tiêu chí hoàn thành

Pha 1 baseline được coi là hoàn thành khi:

1. Toàn bộ unit và integration tests vượt qua.
2. Chín instance mục tiêu chạy được với 25 khách hàng và seed cố định.
3. Mỗi nghiệm cuối vượt qua kiểm tra feasibility độc lập.
4. Kết quả chứa đủ số UAV, distance, risk delay, objective, runtime và route schedule.
5. README mô tả được mô hình, objective, cách chạy và cách tái lập thí nghiệm.
6. Tài liệu giải thích rõ các công thức risk priority, `R(S)`, `D_ref`, `F(S)` và score từ điển.

## 17. Ngoài phạm vi

Các nội dung sau không thuộc baseline Pha 1:

- sự kiện động và rolling horizon;
- pin và năng lượng;
- risk thay đổi theo thời gian;
- vùng cấm bay hoặc path planning tránh vật cản;
- nghiệm trung gian không khả thi và adaptive constraint penalties;
- NSGA-III hoặc tập nghiệm Pareto;
- learning-assisted operator selection.

Các mục này có thể trở thành hướng mở rộng Pha 2 mà không thay đổi định dạng dữ liệu miền hoặc giao diện evaluator cốt lõi.

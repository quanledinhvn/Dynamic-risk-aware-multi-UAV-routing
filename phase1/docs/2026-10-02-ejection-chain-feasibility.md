# Thử nghiệm tính khả thi của ejection chain

Prototype khả thi về tính đúng nhưng **chưa hiệu quả trong ngân sách 2 giây**.
Trên 60 cặp C104/R104/RC104, ejection thắng/thua/hòa bản guided là 3/41/16;
bản có risk là 5/39/16. Giữ cơ chế này ở mức thử nghiệm, không bật mặc định.
Kết quả không chứng minh mọi biến thể ejection chain đều kém; nó bác bỏ việc
đưa cấu hình prototype hiện tại vào solver dựa trên pilot nhỏ.

## Phạm vi và cơ chế

Thử nghiệm thay contextual bandit bằng repair loại route có backtracking và
ejection trong ALNS roulette thích nghi. Mã thử nghiệm nằm trong
`src/uav_routing/ejection.py`; solver mặc định không thay đổi. Đây là bài toán
tĩnh hiện có với tải, time windows và risk delay, chưa phải mô phỏng UAV đang
bay, pin hoặc risk map thay đổi.

Sau khi xóa một route dễ hấp thụ, repair chèn các khách vào route còn lại.
Khách có demand lớn hơn được xét trước, rồi đến deadline sớm hơn. Mỗi nút tìm
kiếm giữ tối đa 4 lựa chọn chèn, thử bằng DFS có backtracking. Nếu các nhánh
chèn trực tiếp thất bại, thử thay một khách trên route bằng khách đang chờ và
đưa khách bị đẩy ra vào đầu danh sách chờ. Một lần repair dùng tối đa 2 phép
ejection tổng cộng; không đẩy lại khách đã chèn trên cùng nhánh.

Giới hạn 2000 lần đánh giá route chưa có trong cache cho mỗi repair, cộng với
deadline chung của run, giúp chặn chi phí tìm kiếm. Số 2000 không bao gồm final
audit hoặc đánh giá của fallback repair. Các route đang chứa khách luôn phải
khả thi; nghiệm trung gian có thể thiếu khách. Chỉ nghiệm đầy đủ vượt final
audit mới được trả về. Thất bại trả `RepairResult(False, None)` và vòng lặp
thử repair gốc; không mở route mới bên trong ejection repair.

Hai cách xếp hạng nhánh:

- Bản thường dùng thay đổi chi phí distance đã chuẩn hóa.
- Bản risk dùng thay đổi distance cộng risk delay của toàn route bị sửa,
  bao gồm các khách phía sau; khi bằng chi phí, ưu tiên độ dư hạn phục vụ
  chuẩn hóa nhỏ nhất trên route lớn hơn. Đây là tie-break theo slack,
  chưa phải một mô hình đánh giá khả năng hấp thụ nhiều khách đồng thời.

Tên policy `beam` trong CSV chỉ bản DFS giới hạn số nhánh, không phải beam
search duyệt đồng thời toàn bộ một tầng. Nó có cùng cách xếp hạng distance
với `ejection`, nhưng giới hạn số ejection bằng 0.

## Thiết kế đánh giá

Mọi run dùng 100 khách, 5 vùng rủi ro, score từ điển $(K,F)$, cùng khởi tạo,
chuẩn hóa và acceptance gốc. Roulette cập nhật mỗi 20 iteration. Khi arm
`route` được chọn, các biến thể mới thử repair chuyên biệt trước, rồi fallback
về repair được roulette chọn nếu thất bại. Vì thế đây là thay đổi pipeline
repair có điều kiện, không phải chỉ thêm một arm vào tích Descartes toán tử.

| Policy | Cơ chế |
|---|---|
| `original` | ALNS gốc |
| `guided` | ALNS với chọn route dễ hấp thụ |
| `beam` | Guided cộng chèn có backtracking, không ejection |
| `ejection` | Guided cộng backtracking và tối đa 2 ejection |
| `risk_ejection` | Ejection với xếp hạng distance và risk, tie-break theo slack |

Pilot dùng C101/R101/RC101, seed 0–4, cả 5 policy, 2 giây mỗi run. Một phần
đầu pilot trùng thời gian chạy test suite nên chỉ dùng để sàng lọc, không coi
là phép đo timing sạch. Không điều chỉnh tham số ejection từ kết quả pilot.

Lượt kiểm tra dùng C104/R104/RC104, seed 0–19, 4 policy từ guided trở đi,
2 giây mỗi run, chạy tuần tự. Ba instance này không có trong pilot này.
Thứ tự policy được xoay theo seed. Thời gian khởi tạo, destroy, repair, chọn
operator và đánh giá đều nằm trong ngân sách. Candidate hoàn tất quá deadline
bị bỏ; runtime thực tế có thể vượt nhẹ do một lời gọi đang thực thi và final
audit. Bản runner của lượt kiểm tra còn kiểm tra deadline sau đánh giá và
acceptance, khôi phục incumbent trước bước đó nếu hết giờ; pilot chỉ kiểm tra
trước đánh giá cuối bước. Vì vậy không gộp hai lượt thành một đánh giá chính.

Ngân sách theo thời gian phụ thuộc tải máy; seed giống nhau không bảo đảm
số iteration giống nhau giữa các lần chạy lại. Các chính sách cũng có quỹ đạo
ngẫu nhiên khác nhau sau khi tạo candidate khác nhau.

## Kết quả

Pilot 15 cặp có tín hiệu thuận lợi nhưng yếu:

| Policy | UAV trung bình | Thắng thua hòa so guided |
|---|---:|---:|
| Original | 16.600 | 5 / 10 / 0 |
| Guided | 16.067 | — |
| Beam | 16.000 | 6 / 4 / 5 |
| Ejection | 15.867 | 7 / 5 / 3 |
| Risk ejection | 15.867 | 7 / 5 / 3 |

Lượt kiểm tra 60 cặp cho kết quả ngược lại:

| Policy | UAV trung bình | Thắng thua hòa so guided | Iteration trung bình | Giây trung bình |
|---|---:|---:|---:|---:|
| guided | 11.833 | — | 60.13 | 2.026 |
| beam | 11.850 | 7 / 21 / 32 | 58.40 | 2.025 |
| ejection | 11.850 | 3 / 41 / 16 | 52.75 | 2.025 |
| risk_ejection | 11.833 | 5 / 39 / 16 | 52.95 | 2.021 |

Trung bình UAV theo từng instance, mỗi ô có 20 seed:

| Instance | Guided | Beam | Ejection | Risk ejection |
|---|---:|---:|---:|---:|
| C104 | 10.00 | 10.00 | 10.00 | 10.00 |
| R104 | 11.80 | 11.80 | 11.75 | 11.75 |
| RC104 | 13.70 | 13.75 | 13.80 | 13.75 |

Ejection thua cả đối chứng backtracking không ejection: thắng/thua/hòa
2/36/22. Risk ejection so với ejection thường là 8/5/47, chưa có lợi thế rõ.
Không gộp objective giữa các nghiệm khác số UAV: ở 55 cặp cùng $K$, ejection
có $F$ cao hơn guided trung bình 0.01135; với risk ejection, 58 cặp cùng $K$
có chênh lệch 0.00930. $F$ thấp hơn là tốt hơn.

Tất cả 315 nghiệm cuối của pilot và lượt kiểm tra đều khả thi. Runtime lớn
nhất ở lượt kiểm tra là 2.137 giây; candidate muộn không được cộng vào best.
CSV và JSON tổng hợp nằm trong `results/ejection_ablation/`.

## Vì sao chưa hiệu quả

Ejection có 633 lần thử repair chuyên biệt, chỉ 8 lần tạo được nghiệm đầy đủ;
4 trong số đó thực sự dùng ejection. Risk ejection có 629 lần thử, 7 lần
thành công, trong đó 3 lần dùng ejection. Đây là số lần xây dựng candidate,
không phải số seed thắng hay chứng minh mọi lần ejection đều cần thiết.

Iteration trung bình giảm từ 60.13 của guided xuống 52.75 của ejection và
52.95 của risk ejection, tương đương mất khoảng 12% số lượt. Trong khi đó,
số UAV trung bình không tốt hơn. Đây là bằng chứng về tradeoff chi phí và
lợi ích của prototype, không phải chứng minh nhân quả duy nhất: quỹ đạo
search và các candidate cũng thay đổi.

Ở C104, mọi policy đạt cận tải 10 UAV. Các lần thử loại route ở đây đều thất
bại, trong khi vẫn chiếm thời gian. Có thể thêm điều kiện bỏ qua theo cận
tải và chọn lần thử bằng ngân sách riêng, nhưng các thay đổi đó **chưa được
thử** trong dữ liệu này.

## Quyết định sau thử nghiệm

Không thay ALNS mặc định bằng ejection repair này. Giữ mã và kết quả làm
ablation âm: chuyển từ bandit sang neighborhood mạnh hơn không tự động đem
lại cải thiện; xác suất thành công phải đủ cao so với chi phí.

Nếu tiếp tục, ưu tiên một thí nghiệm nhỏ về local search trực tiếp ở $K$
cố định, với relocate, swap hoặc trao đổi đuôi route và đánh giá gia tăng.
Lý do là prototype hiện đã giữ được $K$ gần đối chứng nhưng thua chủ yếu về
$F$. Đây là hướng thử tiếp, chưa phải kết quả hay cam kết thắng benchmark.

## Kiểm tra tính đúng

Skeleton được tạo trước test. Ba assertion về repair thành công thất bại ở
bản skeleton, sau đó vượt qua khi cài đặt. Các ca kiểm tra bao gồm xung đột
sức chứa cần đẩy khách giữa route, giới hạn ejection, chèn trực tiếp, input
không hợp lệ, giới hạn số đánh giá, deadline, time windows và ưu tiên phục vụ
khách có risk sớm hơn. Mọi nghiệm benchmark được audit bằng evaluator chung.
Toàn bộ test suite đạt 437 test; Ruff kiểm tra bốn file Python mới đều đạt.

## Tái lập

Từ thư mục `phase1`:

```bash
./.venv/bin/python experiments/ejection_ablation.py \
  --seeds 5 --seconds 2 \
  --output results/ejection_ablation/pilot.csv

./.venv/bin/python experiments/ejection_ablation.py \
  --instances c104 r104 rc104 --seeds 20 --seconds 2 \
  --policies guided beam ejection risk_ejection \
  --output results/ejection_ablation/validation_20_seeds.csv

./.venv/bin/python experiments/summarize_ejection.py \
  results/ejection_ablation/validation_20_seeds.csv \
  --output results/ejection_ablation/validation_summary.json

./.venv/bin/python -m pytest tests -q
```

## Giới hạn của prototype

Tìm kiếm bị cắt theo số nhánh, số ejection và số đánh giá nên có thể thất bại
dù tồn tại phép loại route. Khi hết ngân sách lúc liệt kê lựa chọn, prototype
bỏ lần thử thay vì khai thác các lựa chọn đã liệt kê dở. Quy tắc bảo vệ khách
đã chèn cũng thu hẹp neighborhood. Đây chưa phải ejection pool đầy đủ của
các thuật toán route minimization mạnh.

Cận dưới tải là $K \geq \lceil \sum_i q_i/Q \rceil$. C104 có tổng tải 1810,
sức chứa 200, nên ít nhất cần 10 route. Nếu đạt 10, không thể giảm thêm $K$;
prototype hiện chưa dùng cận này để bỏ qua lần thử loại route vô ích.

Chỉ có ba instance kiểm tra, nên 60 cặp seed không đại diện cho 60 instance
độc lập. Kiểm định dấu là mô tả thăm dò, chưa hiệu chỉnh nhiều phép so sánh.
Cần ngân sách dài hơn và nhiều instance trước khi kết luận khả năng tổng
quát hóa. Chưa cài pha local search riêng hoặc tuyên bố tính mới khoa học.

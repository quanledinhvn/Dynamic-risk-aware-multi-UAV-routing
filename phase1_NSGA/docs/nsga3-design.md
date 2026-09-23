# NSGA-III Design Specification

## 1. Phạm vi

Phase 1 hiện thực baseline NSGA-III cho static risk-aware multi-UAV routing. Mục tiêu là tạo một Pareto approximation set có thể tái lập, kiểm thử và so sánh với ALNS scalarized.

## 2. Biểu diễn nghiệm

Một `Solution` là tuple các route, mỗi route chỉ chứa ID khách hàng. Chromosome là permutation của toàn bộ khách hàng. Decoder lần lượt chèn khách hàng vào vị trí khả thi làm tăng distance ít nhất; nếu không thể chèn vào route hiện có thì mở route mới trong giới hạn UAV.

Vì decoder kiểm tra bằng `Evaluator`, offspring không được tự ý diễn giải time window hoặc capacity.

## 3. Objective vector

Tất cả objective đều minimize:

$$
f(x) = (K(x), D(x), R(x), L_{max}(x), T_{late}(x))
$$

Trong đó:

- $K$: số UAV;
- $D$: tổng distance;
- $R$: risk delay weighted by priority;
- $L_{max}$: tải lớn nhất;
- $T_{late}$: tổng lateness.

Trong Phase 1, lateness là hard constraint nên nghiệm khả thi có giá trị bằng 0. Objective này vẫn được giữ trong vector để API có thể mở rộng sang penalty hoặc dynamic scenarios.

## 4. Dominance

Với hai nghiệm khả thi $a,b$, $a$ trội $b$ khi không objective nào xấu hơn và ít nhất một objective tốt hơn. Không dùng weighted sum và không áp dụng lexicographic acceptance.

## 5. NSGA-III environmental selection

Mỗi thế hệ:

1. gộp parent và offspring;
2. tạo non-dominated fronts;
3. lấy trọn các front cho đến khi front kế tiếp bị cắt;
4. chuẩn hóa objective của pool đang xét;
5. chiếu từng vector lên các simplex-lattice reference directions;
6. đếm niche đã có trong phần được chọn;
7. bổ sung từ niche ít nghiệm nhất, ưu tiên khoảng cách vuông góc nhỏ nhất khi niche chưa có nghiệm.

Cơ chế này thay crowding distance của NSGA-II bằng phân bố theo hướng tham chiếu.

## 6. Reference directions

Dùng Das-Dennis với $M=5$ objective và số divisions $H$. Số hướng là:

$$
N_{dir} = {H+M-1 \choose M-1}
$$

Cấu hình mặc định $H=4$ tạo 70 hướng. Population size nên được chọn tương thích với số hướng nếu muốn phủ Pareto front tốt.

## 7. Feasibility

Evaluator loại nghiệm khi có một trong các lỗi: duplicate/missing/unknown customer, quá số UAV, capacity, customer due date hoặc depot due date. Partial route chỉ là trạng thái nội bộ decoder, không được đưa vào population.

## 8. Tái lập và đánh giá

Mọi randomness đi qua một NumPy Generator duy nhất. Báo cáo cần lưu seed, objective vector, routes, số nghiệm Pareto, tỷ lệ feasible, runtime và config. Khi so sánh nhiều seed nên báo cáo hypervolume, spacing, IGD và độ phân tán.

## 9. Dynamic extension

Phase 2 có thể giữ population cũ, loại nhiệm vụ đã hoàn thành, cập nhật risk map và chạy lại trong rolling horizon. Warm start cần trộn một phần nghiệm mới để tránh population bị khóa trong cấu trúc cũ.

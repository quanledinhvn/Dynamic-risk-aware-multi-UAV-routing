# Thiết kế Contextual Bandit cho ALNS

## 1. Mục tiêu và câu hỏi nghiên cứu

Mở rộng ALNS baseline bằng một cơ chế Contextual Bandit để chọn cặp
destroy--repair theo trạng thái tìm kiếm hiện tại. Baseline roulette hiện có
phải được giữ nguyên như một lựa chọn cấu hình để làm đối chứng.

Câu hỏi nghiên cứu chính là:

> Với cùng ngân sách iteration, việc chọn cặp destroy--repair bằng Contextual
> Bandit có cải thiện chất lượng nghiệm của ALNS mà không tạo overhead runtime
> quá lớn so với roulette adaptive truyền thống trong bài toán risk-aware
> multi-UAV routing hay không?

Phiên bản đầu chỉ triển khai Disjoint LinUCB cho bài toán tĩnh của Pha 1. Việc
chọn kích thước phá nghiệm $q$, discounted learning cho dữ liệu động, continuous
reward và huấn luyện chung qua nhiều instance không thuộc phạm vi triển khai
đầu tiên.

## 2. Nguyên tắc thiết kế

- Mỗi arm là một cặp `(destroy_name, repair_name)` hợp lệ.
- Với năm destroy và ba repair hiện có, selector mặc định có 15 arms.
- Context chỉ chứa thông tin có sẵn trước khi chọn arm.
- Reward chỉ được tính sau khi candidate đã được repair, đánh giá và quyết định
  acceptance.
- Roulette và LinUCB dùng chung operator, evaluator, acceptance policy, cooling
  schedule, reward classification và stopping condition.
- Không thêm dependency machine-learning; LinUCB chỉ dùng NumPy.
- Mọi lựa chọn ngẫu nhiên, kể cả phá hòa giữa các arm có cùng điểm, dùng
  `numpy.random.Generator` đã được truyền vào ALNS.
- Cùng instance, cấu hình và seed phải tái lập route, metric và thống kê
  selector; runtime không cần giống nhau.
- Thuật ngữ `vehicle` tiếp tục được dùng trong code lõi VRPTW; `UAV` được dùng
  trong tài liệu nghiệp vụ.

## 3. Action space

Một action là:

$$
a=(d_i,r_j),
$$

trong đó $d_i$ là destroy operator và $r_j$ là repair operator. Danh sách arm
được tạo theo thứ tự Cartesian product ổn định của danh sách destroy rồi danh
sách repair. Tên arm trong output có dạng `destroy_name+repair_name`.

Chọn nguyên cặp thay vì hai bandit độc lập để mô hình học trực tiếp tương tác
giữa destroy và repair, đồng thời tránh gán cùng một reward cho hai quyết định
độc lập như baseline hiện tại.

Kích thước phá nghiệm $q$ vẫn được lấy đều từ đoạn cấu hình
`[q_min, q_max]`. Giữ quyết định này ngoài action space giúp giới hạn số arm và
cô lập ảnh hưởng của cơ chế chọn operator trong ablation đầu tiên.

## 4. Context vector

Context có đúng chín chiều và được tạo trước khi chọn arm:

$$
x_t=[
1,
p_t,
\tau_t,
s_t,
a_t,
i_t,
g^K_t,
g^F_t,
R(S_t)
].
$$

Các thành phần là:

1. `bias`: hằng số $1$.
2. `progress`: với iteration đánh số từ $0$, dùng
   $p_t=t/\max(1,T-1)$.
3. `temperature`: nhiệt độ logarithmic chuẩn hóa về $[0,1]$:

   $$
   \tau_t=
   \frac{\log(T_t/T_{\min})}
        {\log(T_0/T_{\min})}.
   $$

   Kết quả được clip về $[0,1]$. Nếu $T_0=T_{\min}$, quy ước
   $\tau_t=1$.
4. `stagnation`: số iteration kể từ best-so-far gần nhất chia cho
   `context_window`, sau đó clip về $[0,1]$.
5. `acceptance_rate`: tỷ lệ candidate được chấp nhận trong tối đa
   `context_window` iteration gần nhất; bằng $0$ khi chưa có lịch sử.
6. `improvement_rate`: tỷ lệ candidate tốt hơn current được dùng ở đầu
   iteration tương ứng, trong cùng cửa sổ; bằng $0$ khi chưa có lịch sử.
7. `vehicle_gap`: khoảng cách số vehicle giữa current và best:

   $$
   g^K_t=
   \frac{\max(0,K(S_t)-K(S_{best}))}
        {\max(1,K_{max})}.
   $$

8. `objective_gap`: nếu current và best có cùng số vehicle:

   $$
   g^F_t=
   \min\left(
   1,
   \frac{\max(0,F(S_t)-F(S_{best}))}
        {\max(|F(S_{best})|,10^{-12})}
   \right).
   $$

   Nếu số vehicle khác nhau, quy ước $g^F_t=0$ để không trộn hai tầng của
   objective từ điển.
9. `risk_delay`: $R(S_t)$ của current solution, đã nằm trong $[0,1]$ đối với
   nghiệm khả thi.

Mọi phần tử context phải hữu hạn. Context extractor từ chối vector sai kích
thước hoặc chứa `NaN`/vô cực thay vì truyền dữ liệu lỗi vào selector.

Các đặc trưng cố định như số customer và số risk zone không được đưa vào phiên
bản đầu vì bandit được khởi tạo mới cho mỗi lần chạy; chúng không thay đổi giữa
các iteration của cùng một run.

## 5. Search history

`SearchHistory` là state mutable riêng, không đặt trong các domain dataclass bất
biến. Nó lưu:

- số iteration kể từ best-so-far gần nhất;
- cửa sổ boolean candidate được accepted;
- cửa sổ boolean candidate cải thiện current trước action;
- tổng số iteration đã ghi nhận.

Sau mỗi iteration:

- nếu candidate tạo best-so-far mới, stagnation đặt về $0$;
- nếu không, stagnation tăng một;
- repair thất bại hoặc candidate không khả thi ghi `False` cho accepted và
  improved;
- accepted-worse ghi `True` cho accepted và `False` cho improved;
- cửa sổ không vượt `context_window`.

Context của iteration $t$ chỉ dùng history kết thúc ở iteration $t-1$.

## 6. Disjoint LinUCB

Mỗi arm $a$ có ma trận $A_a$ và vector $b_a$ riêng. Khởi tạo:

$$
A_a=\lambda I,
\qquad
b_a=0,
$$

trong đó `linucb_regularization` là $\lambda>0$.

Tại một context $x_t$, selector tính:

$$
\hat\theta_a=A_a^{-1}b_a,
$$

$$
u_{t,a}=
x_t^T\hat\theta_a+
\alpha_{ucb}\sqrt{x_t^TA_a^{-1}x_t}.
$$

Arm có $u_{t,a}$ lớn nhất được chọn. `numpy.linalg.solve` được dùng thay cho
nghịch đảo ma trận trực tiếp. Các arm có điểm bằng nhau trong dung sai số học
được phá hòa bằng RNG của solver.

Sau khi nhận reward $r_t$:

$$
A_a\leftarrow A_a+x_tx_t^T,
$$

$$
b_a\leftarrow b_a+r_tx_t.
$$

Chỉ arm đã chọn được cập nhật. `linucb_exploration` phải không âm và
`linucb_regularization` phải dương.

## 7. Reward

Outcome classification của baseline được giữ nguyên:

- `reward_best` nếu tạo best-so-far mới;
- `reward_improve` nếu tốt hơn current nhưng không tốt hơn best;
- `reward_accepted` nếu candidate xấu hơn được chấp nhận;
- `0` nếu equal, rejected, repair thất bại hoặc candidate không khả thi.

Roulette tiếp tục nhận raw reward để bảo toàn hành vi baseline. LinUCB nhận
reward chuẩn hóa:

$$
r_t=
\frac{r^{raw}_t}
     {\max(\text{reward_best},
           \text{reward_improve},
           \text{reward_accepted})}.
$$

Với cấu hình mặc định, các mức là $1$, $0.5$, $0.1$ và $0$. Khi dùng LinUCB,
ít nhất một mức reward phải dương; mọi mức phải không âm. Việc giữ reward cũ
giúp ablation đầu tiên chỉ thay selection policy.

## 8. Selector abstraction và tương thích baseline

Tạo module `selection.py` với một interface chung cho hai policy:

```python
OperatorPair = tuple[str, str]

class OperatorSelector(Protocol):
    def select(
        self,
        context: np.ndarray,
        rng: np.random.Generator,
    ) -> OperatorPair: ...

    def record(
        self,
        arm: OperatorPair,
        context: np.ndarray,
        raw_reward: float,
    ) -> None: ...

    def end_iteration(self, completed_iterations: int) -> None: ...

    def snapshot(self) -> tuple[PairSelectionStats, ...]: ...
```

`RoulettePairSelector` bọc hai `AdaptivePool` hiện có. Nó chọn destroy và repair
độc lập như trước, ghi raw reward vào cả hai pool và cập nhật segment tại
`end_iteration`. Tham số `completed_iterations` bắt đầu từ $1$; selector cập
nhật segment khi giá trị này chia hết cho `segment_length`. Vì vậy cấu hình
`selector="roulette"` phải bảo toàn kết quả baseline hiện có với cùng seed.

`LinUCBPairSelector` dùng Cartesian product của hai operator list, bỏ qua cập
nhật segment và chuẩn hóa reward trước khi cập nhật mô hình.

Mỗi selector đồng thời tích lũy `PairSelectionStats` gồm:

- `destroy_name`;
- `repair_name`;
- `total_uses`;
- `total_raw_reward`;
- `average_raw_reward`.

`SearchResult.operator_stats` được giữ nguyên để không phá output baseline;
với LinUCB nó là tuple rỗng. `SearchResult` bổ sung `selector_name` và
`pair_selection_stats`. Roulette trả cả operator stats cũ và pair stats mới.

## 9. Luồng một iteration

Mỗi iteration thực hiện theo thứ tự:

1. Tạo context từ state và history trước iteration.
2. Lấy $q$ ngẫu nhiên như baseline.
3. Selector chọn một cặp destroy--repair.
4. Chạy destroy và repair.
5. Đánh giá candidate, acceptance và reward như baseline.
6. Cập nhật current và best nếu phù hợp.
7. Ghi arm, context và reward vào selector.
8. Cập nhật search history từ outcome.
9. Gọi `end_iteration` với số iteration đã hoàn tất để roulette có thể cập
   nhật segment.
10. Giảm nhiệt độ.

Thứ tự lấy $q$ trước khi selector chọn operator là bắt buộc để roulette tiêu
thụ RNG theo đúng thứ tự của baseline hiện tại.

Kết quả nội bộ của bước 5 phải được biểu diễn bằng một record thay vì chỉ trả
`float`, để reward, accepted, improved và new-best được dùng nhất quán bởi
selector và history.

## 10. Cấu hình

`ALNSConfig` bổ sung:

```text
selector = "roulette"
context_window = 100
linucb_exploration = 0.5
linucb_regularization = 1.0
```

Validation:

- `selector` chỉ nhận `roulette` hoặc `linucb`;
- `context_window` là số nguyên dương, không nhận `bool`;
- `linucb_exploration` hữu hạn và không âm;
- `linucb_regularization` hữu hạn và dương;
- khi `selector="linucb"`, reward lớn nhất phải dương.

CLI `solve` bổ sung `--selector` với hai lựa chọn trên. Các tham số LinUCB còn
lại được đọc từ config/API trong phiên bản đầu; không mở rộng toàn bộ thành CLI
flag để tránh tăng bề mặt giao diện không cần thiết.

## 11. Output và benchmark

JSON của một lần solve bổ sung:

- `selector`;
- `pair_selection_stats`.

Trường `operators` cũ vẫn tồn tại. Với LinUCB nó là danh sách rỗng; với roulette
nó giữ nguyên schema hiện tại.

`raw.csv` và `aggregate.csv` bổ sung `selector`. Selector là một phần của khóa
group aggregate để kết quả roulette và LinUCB không bị gộp. Pair statistics chỉ
được lưu trong JSON solve, không nhúng vào CSV benchmark.

## 12. Kiểm thử và tiêu chí nghiệm thu

Kiểm thử được phát triển theo TDD và tuân theo quy tắc skeleton của dự án.

### Unit tests

- Context có đúng thứ tự chín feature, finite và đúng các trường hợp biên.
- History không vượt window và cập nhật đúng failed, rejected, improved,
  accepted-worse và new-best.
- LinUCB khởi tạo đúng regularization, chọn theo exploitation/uncertainty, chỉ
  cập nhật arm được chọn và phá hòa tái lập bằng RNG.
- Roulette adapter bảo toàn lựa chọn, reward và segment update của baseline.
- Config từ chối selector và hyperparameter không hợp lệ.

### Integration tests

- `selector="roulette"` bảo toàn deterministic baseline hiện tại.
- `selector="linucb"` chạy end-to-end, trả nghiệm hoàn chỉnh và khả thi.
- Hai lần chạy LinUCB cùng instance, config và seed cho cùng route, evaluation
  và selection statistics.
- Tổng `total_uses` của pair statistics bằng số iteration.
- CLI và benchmark xuất đúng selector, không gộp hai policy khi aggregate.

### Definition of done

- Toàn bộ test hiện có tiếp tục pass.
- Không có dependency mới ngoài NumPy.
- Roulette vẫn là selector mặc định.
- LinUCB có thể bật qua config hoặc `--selector linucb`.
- Cả hai selector dùng cùng operator, evaluator, reward classification,
  acceptance và stopping condition.
- README mô tả context, action, reward, lệnh chạy và giới hạn của phiên bản
  tĩnh.

## 13. Ngoài phạm vi

- Context chứa event động, pin, nhiệm vụ mới hoặc risk-map delta.
- Discounted hoặc sliding-window LinUCB.
- Chọn $q$, cooling rate hoặc acceptance policy bằng bandit.
- Continuous/delayed reward và deep reinforcement learning.
- Huấn luyện chung hoặc chuyển mô hình giữa các instance.
- Thay đổi objective, destroy operator hoặc repair operator hiện có.

# Rolling Horizon

Dưới đây là giả mã **rolling horizon đúng theo phần cài đặt hiện tại của dự án**, gồm chọn thời điểm ra quyết định, khóa phần tuyến đã thực thi, áp dụng sự kiện, chiếu kế hoạch cũ, xử lý nhiệm vụ không thể phục vụ, tái tối ưu và ghi nhận kết quả.

## Giả mã Rolling Horizon

```text
ALGORITHM RUN_ROLLING_HORIZON(scenario, alns_config, rolling_config)

INPUT:
    scenario                 kịch bản động
    alns_config              cấu hình ALNS
    rolling_config           cấu hình rolling horizon

    H                        thời điểm kết thúc mô phỏng
    E                        danh sách sự kiện, sắp theo thời gian
    policy                   greedy_insert, cold_restart hoặc warm_alns
    trigger                  periodic, event hoặc hybrid
    Δt                       độ dài epoch hiệu dụng
    I0                       số vòng ALNS tại epoch 0
    Ie                       số vòng ALNS tại mỗi epoch sau
    seed                     seed gốc của mô phỏng

OUTPUT:
    simulation_result        lời giải thực thi và lịch sử các epoch


1.  Validate(alns_config, rolling_config)
2.  instance ← BaseInstance(scenario)
3.  constraints ← EmptyConstraints()
4.  frozen_priority ← {}
5.  rejected ← ()
6.  lost ← []
7.  epochs ← []
8.  pending ← E
9.  t ← 0


10. --------------------------------------------------
11. // EPOCH 0: GIẢI BÀI TOÁN TĨNH BAN ĐẦU
12. --------------------------------------------------

13. seed0 ← EpochSeed(seed, 0)

14. IF I0 > 0:
15.     result ← ALNS(instance, iterations = I0, seed = seed0)
16. ELSE:
17.     (initial, d_ref) ← BuildInitialSolution(instance)
18.     result ← EvaluateOnly(instance, initial, constraints, d_ref)

19. d_ref ← result.d_ref
20. solution ← result.best_solution
21. RecordEpoch(index = 0, time = 0, revealed = (), result)


22. --------------------------------------------------
23. // CÁC EPOCH TÁI TỐI ƯU
24. --------------------------------------------------

25. WHILE t < H:

26.     next_event ← thời gian event chưa xử lý gần nhất, hoặc H nếu không còn
27.     periodic ← min(t + Δt, H)

28.     IF trigger = periodic:
29.         next_time ← periodic
30.     ELSE IF trigger = event:
31.         next_time ← min(next_event, H)
32.     ELSE:  // hybrid
33.         next_time ← min(periodic, next_event)

34.     revealed ← {e ∈ pending | e.time ≤ next_time}
35.     pending ← {e ∈ pending | e.time > next_time}
36.     t ← next_time


37.     --------------------------------------------------
38.     // BƯỚC 1: KHÓA PHẦN TUYẾN ĐÃ CAM KẾT
39.     --------------------------------------------------

40.     (solution, constraints) ← LockSolution(solution, instance, t, constraints)

41.     FOR mỗi customer i vừa được khóa:
42.         IF i chưa có trong frozen_priority:
43.             frozen_priority[i] ← CurrentRiskPriority(i)


44.     --------------------------------------------------
45.     // BƯỚC 2: ÁP DỤNG CÁC SỰ KIỆN VỪA LỘ DIỆN
46.     --------------------------------------------------

47.     applicable ← ()

48.     FOR mỗi event e ∈ revealed:
49.         IF e là DeadlineUpdate của customer đã khóa hoặc đã lost:
50.             bỏ qua e
51.         ELSE:
52.             thêm e vào applicable

53.     instance ← ApplyEvents(instance, applicable, frozen_priority)

        // CustomerArrival: thêm customer mới
        // RiskUpdate: thêm hoặc thay risk zone, rồi tính lại risk priority
        // DeadlineUpdate: chỉ chấp nhận deadline mới chặt hơn nhưng vẫn hợp lệ
        // Priority của customer đã khóa luôn giữ nguyên


54.     --------------------------------------------------
55.     // BƯỚC 3: LOẠI CÁC CUSTOMER ĐÃ MẤT CƠ HỘI PHỤC VỤ
56.     --------------------------------------------------

57.     newly_lost ← ()

58.     FOR mỗi customer i ∈ rejected:
59.         latest_launch[i] ← due_date[i] - distance(depot, i)

60.         IF t > latest_launch[i]:
61.             thêm i vào newly_lost

62.     lost ← lost ∪ newly_lost
63.     lost_priority ← lost_priority + tổng priority của newly_lost
64.     instance ← DropCustomers(instance, newly_lost, frozen_priority)


65.     --------------------------------------------------
66.     // BƯỚC 4: CHIẾU KẾ HOẠCH CŨ SANG INSTANCE MỚI
67.     --------------------------------------------------

68.     projected ← solution sau khi bỏ customer không còn trong instance

69.     FOR mỗi route r trong projected:
70.         WHILE phần tự do của r làm route không khả thi:
71.             p ← vị trí tự do đầu tiên vi phạm deadline
72.             nếu không tìm thấy vị trí đó, p ← vị trí cuối của route
73.             tháo customer tại p khỏi r

74.     pool ← mọi customer trong instance chưa có trong projected


75.     --------------------------------------------------
76.     // BƯỚC 5: TRIAGE ĐỂ TẠO LỜI GIẢI BAN ĐẦU KHẢ THI
77.     --------------------------------------------------

78.     S_initial ← projected
79.     rejected ← ()

80.     Sắp pool theo RiskPriorityRepair

81.     FOR mỗi customer i ∈ pool theo thứ tự trên:
82.         choice ← BestFeasibleInsertion(S_initial, i, constraints)

83.         IF choice tồn tại:
84.             S_initial ← choice.solution
85.         ELSE:
86.             thêm i vào rejected

87.     IF rejected ≠ ():
88.         epoch_instance ← DropCustomers(instance, rejected, frozen_priority)
89.     ELSE:
90.         epoch_instance ← instance

        // Customer bị rejected chỉ bị bỏ khỏi bài toán của epoch hiện tại.
        // Nó vẫn được giữ trong instance để thử chèn lại ở epoch tiếp theo,
        // trừ khi đã chuyển thành lost ở bước 3.


91.     --------------------------------------------------
92.     // BƯỚC 6: GIẢI EPOCH THEO POLICY
93.     --------------------------------------------------

94.     epoch_index ← số record hiện có
95.     epoch_seed ← EpochSeed(seed, epoch_index)

96.     result ← EpochSolver(
97.         epoch_instance,
98.         S_initial,
99.         constraints,
100.        d_ref,
101.        iterations = Ie,
102.        seed = epoch_seed
103.    )

104.    solution ← result.best_solution


105.    --------------------------------------------------
106.    // BƯỚC 7: GHI NHẬN EPOCH
107.    --------------------------------------------------

108.    RecordEpoch(
109.        index = epoch_index,
110.        time = t,
111.        revealed = revealed,
112.        locked_customers = CountLocked(constraints),
113.        rejected = rejected,
114.        solution = solution,
115.        evaluation = result.evaluation,
116.        iterations = result.iterations,
117.        runtime = elapsed_time
118.    )


119. --------------------------------------------------
120. // KẾT THÚC MÔ PHỎNG
121. --------------------------------------------------

122. final_instance ← instance sau khi bỏ các customer còn rejected
123. final_evaluation ← Evaluate(solution, final_instance, constraints, d_ref)
124. unserved ← Sort(Unique(rejected ∪ lost))
125. unserved_priority ← priority(rejected) + lost_priority

126. RETURN SimulationResult(
127.     realized = solution,
128.     evaluation = final_evaluation,
129.     unserved = unserved,
130.     epochs = epochs,
131.     total_iterations = tổng iterations của mọi epoch,
132.     runtime = tổng thời gian mô phỏng
133. )
```

## Độ dài epoch và thời điểm ra quyết định

Độ dài epoch hiệu dụng được xác định bởi:

$$
\Delta t=
\begin{cases}
fH, & \text{nếu cấu hình } \texttt{epoch\_fraction}=f,\\
\texttt{epoch\_length}, & \text{nếu không.}
\end{cases}
$$

Trong đó:

- $H$: toàn bộ simulation horizon;
- $f \in (0,1]$: tỷ lệ độ dài epoch so với horizon;
- nếu có `epoch_fraction`, giá trị `epoch_length` không được sử dụng.

Tại thời điểm $t$, đặt:

$$
t_{\text{periodic}}=\min(t+\Delta t,H)
$$

và $t_{\text{event}}$ là thời gian của event chưa xử lý gần nhất, hoặc $H$ nếu không còn event. Ba trigger chọn epoch tiếp theo như sau:

| Trigger | Thời điểm tiếp theo |
|---|---|
| `periodic` | $t_{\text{periodic}}$ |
| `event` | $\min(t_{\text{event}},H)$ |
| `hybrid` | $\min(t_{\text{periodic}},t_{\text{event}})$ |

Với `periodic`, mọi event xảy ra giữa hai epoch được gom lại và chỉ áp dụng ở epoch kế tiếp. Với `event`, controller đi qua từng mốc có event. Cả ba chế độ đều tạo một epoch cuối tại $H$.

Ví dụ, với $H=100$, $\Delta t=30$ và các event tại 5, 10, 30:

```text
periodic: 0, 30, 60, 90, 100
event:    0, 5, 10, 30, 100
hybrid:   0, 5, 10, 30, 60, 90, 100
```

## Cơ chế khóa route prefix

Mỗi route được tách thành:

$$
R_k=R_k^{\text{locked}}\oplus R_k^{\text{free}}
$$

Trong đó:

- $R_k^{\text{locked}}$: prefix đã cam kết, destroy và repair không được thay đổi;
- $R_k^{\text{free}}$: phần còn lại có thể tái tối ưu;
- `free_departure = t`: route chưa khởi hành sớm nhất chỉ có thể rời depot tại thời điểm epoch hiện tại.

Với customer đầu tiên $i$ của một route chưa khởi hành, thời điểm rời depot muộn nhất mà vẫn đến đúng `ready_time` là:

$$
d_i^{\text{latest}}=\max(d_k,r_i-c_{0i})
$$

Trong đó:

- $d_k$: mốc khởi hành áp dụng cho route;
- $r_i$: `ready_time` của customer đầu tiên;
- $c_{0i}$: thời gian bay từ depot đến customer $i$.

Customer đầu tiên chỉ bị khóa khi:

$$
d_i^{\text{latest}}<t
$$

Các customer tiếp theo được thêm vào prefix nếu UAV đã rời customer đứng trước chúng, tức `departure < t`. So sánh là **nhỏ hơn nghiêm ngặt**; tại đúng thời điểm departure, customer tiếp theo chưa bị khóa.

Prefix đã khóa ở epoch trước không bao giờ bị rút ngắn. Sau khi khóa, các route có prefix được đưa lên trước các route hoàn toàn tự do để `locked_prefixes` và chỉ số route luôn khớp nhau.

## Thứ tự xử lý trong một epoch

Thứ tự trong code là:

```text
lock
→ apply events
→ drop lost customers
→ project old plan
→ triage
→ solve
→ record
```

`lock` chạy trước `apply events`. Vì vậy phần tuyến đã được thực thi đến thời điểm $t$ được xác định từ kế hoạch và dữ liệu đã biết ở epoch trước; sự kiện vừa lộ diện không thể sửa ngược lịch sử.

## Ba loại sự kiện động

### Customer arrival

Customer mới được thêm vào `instance`. Ma trận khoảng cách và risk priority được xây dựng lại. Khi project kế hoạch cũ, customer mới chưa nằm trong route nào nên được đưa vào `pool` để triage.

### Risk update

Risk zone cùng `id` sẽ bị thay thế; `id` mới sẽ được thêm vào. Sau đó risk priority của toàn bộ customer chưa khóa được tính lại.

Priority của customer đã khóa được lưu trong `frozen_priority`, nên risk update về sau không làm thay đổi chi phí lịch sử của phần tuyến đã thực thi.

### Deadline update

Deadline mới phải:

- nhỏ hơn deadline hiện tại;
- không nhỏ hơn `ready_time`;
- thuộc về customer đã tồn tại;
- không áp dụng cho customer đã khóa hoặc đã `lost`.

Deadline update của customer đã khóa hoặc đã `lost` được controller bỏ qua thay vì phát sinh lỗi.

## Projection và triage

`project` tận dụng kế hoạch cũ theo nguyên tắc warm start:

1. giữ nguyên mọi locked prefix;
2. bỏ customer không còn trong instance;
3. kiểm tra lại từng route theo dữ liệu mới;
4. nếu route không khả thi, tháo customer tự do đầu tiên vi phạm deadline;
5. nếu không có customer nào vi phạm deadline trực tiếp, tháo customer tự do cuối route;
6. lặp đến khi route khả thi hoặc không còn customer tự do;
7. gom mọi customer chưa được phục vụ vào `pool`.

`triage` duyệt `pool` theo thứ tự của `RiskPriorityRepair`, ưu tiên risk priority cao hơn rồi xét deadline và `id` để phá hòa. Mỗi customer được chèn vào vị trí khả thi tốt nhất. Customer không có phép chèn khả thi được đưa vào `rejected`.

## Phân biệt rejected và lost

Hai trạng thái này không giống nhau:

- `rejected`: chưa chèn được trong epoch hiện tại nhưng sẽ được thử lại;
- `lost`: đã quá muộn để ngay cả chuyến bay trực tiếp từ depot cũng kịp deadline, nên bị loại vĩnh viễn.

Với customer $i$, thời điểm xuất phát muộn nhất theo kiểm tra hiện tại là:

$$
\ell_i=b_i-c_{0i}
$$

Trong đó $b_i$ là `due_date`. Customer chỉ chuyển từ `rejected` sang `lost` khi:

$$
t>\ell_i
$$

Điều kiện cũng dùng dấu lớn hơn nghiêm ngặt. Kiểm tra này chưa tính service time, capacity hay việc phải ghé customer khác; đây là một cận đơn giản để xác định nhiệm vụ chắc chắn không còn cơ hội phục vụ.

## Các policy giải một epoch

```text
POLICIES = {
    greedy_insert,
    cold_restart,
    warm_alns
}
```

### `greedy_insert`

Không chạy thêm vòng tìm kiếm. Kế hoạch sau `project + triage` được đánh giá và trả về trực tiếp. Tên policy nói đến bước chèn tham lam đã diễn ra trong `triage`.

### `warm_alns`

Dùng kế hoạch sau `project + triage` làm `initial_solution`, giữ nguyên locked prefix và chạy ALNS trong `iterations_per_epoch` vòng. Nếu ngân sách bằng 0, policy chỉ đánh giá lời giải ban đầu.

### `cold_restart`

Giữ locked prefix nhưng xây lại toàn bộ phần tự do từ đầu. Customer tự do được xét theo thứ tự:

```text
(due_date tăng dần, risk_priority giảm dần, customer_id tăng dần)
```

Nếu không thể xây lại đầy đủ, policy quay về kế hoạch `initial` do triage tạo. Sau đó nó chạy cùng quy trình ALNS như `warm_alns`.

## Seed và tính tái lập

Mỗi epoch nhận một seed riêng được sinh từ cặp:

```text
(base_seed, epoch_index)
```

thông qua `numpy.random.SeedSequence`. Vì vậy:

- cùng seed và cùng cấu hình cho kết quả có thể tái lập;
- các epoch khác nhau không dùng trùng chuỗi ngẫu nhiên;
- epoch 0 cũng dùng seed đã dẫn xuất, không dùng trực tiếp seed trong `ALNSConfig`.

## Đại lượng được giữ cố định qua các epoch

`d_ref` được xác định ở epoch 0 rồi tái sử dụng ở mọi epoch sau. Điều này giữ cùng thang chuẩn hóa khoảng cách khi so sánh objective qua thời gian, ngay cả khi customer hoặc risk zone thay đổi.

Các locked prefix và priority đã đóng băng cũng được truyền xuyên suốt mô phỏng. Ngược lại, lời giải tự do, tập `rejected`, instance của epoch và seed được cập nhật ở mỗi lần ra quyết định.

## Kết quả mô phỏng

Mỗi `EpochRecord` lưu:

- chỉ số và thời điểm epoch;
- các event được reveal;
- số customer đã khóa;
- các customer bị reject ở epoch đó;
- lời giải và kết quả đánh giá;
- số vòng lặp solver;
- runtime của epoch.

`SimulationResult` lưu lời giải thực thi cuối cùng, đánh giá cuối, hợp của `rejected` và `lost`, tổng priority không được phục vụ, toàn bộ lịch sử epoch, tổng số vòng lặp và runtime toàn mô phỏng.

## Ánh xạ sang mã nguồn

| Thành phần | File |
|---|---|
| Controller và vòng lặp epoch | `phase1/src/uav_routing/dynamic/horizon.py` |
| Cấu hình policy, trigger và epoch | `phase1/src/uav_routing/dynamic/config.py` |
| Khóa route prefix | `phase1/src/uav_routing/dynamic/locking.py` |
| Áp dụng event và xây lại instance | `phase1/src/uav_routing/dynamic/events.py` |
| Projection, triage và lost customer | `phase1/src/uav_routing/dynamic/projection.py` |
| Solver của từng policy | `phase1/src/uav_routing/dynamic/policies.py` |
| Record của scenario, event và kết quả | `phase1/src/uav_routing/dynamic/models.py` |
| Ràng buộc locked prefix | `phase1/src/uav_routing/models.py` |

## Lưu ý về cấu hình hiện tại

`RollingHorizonConfig` có trường `carry_weights`, nhưng controller và các epoch solver hiện chưa đọc trường này. Vì thế đặt `carry_weights=True` **chưa truyền trọng số operator ALNS từ epoch trước sang epoch sau**; mỗi lần gọi `run_alns` vẫn khởi tạo một lượt tìm kiếm mới từ cấu hình ALNS và lời giải đầu vào.

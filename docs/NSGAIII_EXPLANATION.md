# Lý thuyết NSGA-III cho bài toán Dynamic Risk-Aware Multi-UAV Routing

Tài liệu này trình bày các khái niệm lý thuyết nền tảng của bài toán định tuyến nhiều UAV có xét đến rủi ro động, thời hạn phục vụ và giới hạn tải. Nội dung tập trung vào mô hình hóa bài toán, tối ưu đa mục tiêu và nguyên lý của NSGA-III, không phụ thuộc vào một chương trình hay bộ dữ liệu cụ thể.

---

## 1. Mô hình bài toán

Xét một hệ thống gồm:

- một depot hoặc các điểm xuất phát;
- tập nhiệm vụ cần phục vụ;
- nhiều UAV;
- vị trí, nhu cầu tải, thời gian phục vụ và thời gian cho phép của mỗi nhiệm vụ;
- các vùng hoặc bản đồ rủi ro trong không gian bay.

Một lời giải phải xác định:

1. nhiệm vụ nào được giao cho UAV nào;
2. thứ tự phục vụ các nhiệm vụ của từng UAV;
3. thời điểm thực hiện mỗi nhiệm vụ.

Một route của UAV có thể được biểu diễn dưới dạng:

$$
R_k = [d, i_1, i_2, \ldots, i_m, d]
$$

trong đó `d` là depot, còn $i_1, \ldots, i_m$ là các nhiệm vụ được giao cho UAV $k$.

Mỗi nhiệm vụ phải được phục vụ đúng một lần, trừ trường hợp mô hình cho phép bỏ nhiệm vụ với một chi phí phạt rõ ràng.

### 1.1. Ràng buộc phân công

Gọi $x_{ik}$ bằng 1 nếu nhiệm vụ $i$ được giao cho UAV $k$, và bằng 0 trong trường hợp ngược lại. Khi mỗi nhiệm vụ chỉ được giao cho một UAV:

$$
\sum_{k=1}^{K} x_{ik} = 1
$$

### 1.2. Ràng buộc tải

Nếu $q_i$ là nhu cầu tải của nhiệm vụ $i$ và $Q_k$ là sức chứa của UAV $k$, ta có:

$$
\sum_{i \in R_k} q_i \le Q_k
$$

Ràng buộc này có thể được xử lý theo hai cách: loại bỏ nghiệm vi phạm hoặc cho phép vi phạm nhưng cộng thêm một hàm phạt lớn.

### 1.3. Ràng buộc thời gian

Mỗi nhiệm vụ có thể có thời điểm sẵn sàng $a_i$ và deadline $b_i$. Thời điểm bắt đầu phục vụ phải thỏa mãn:

$$
a_i \le start_i \le b_i
$$

Nếu UAV đến sớm, nó phải chờ. Nếu đến muộn, mô hình có thể loại bỏ route, ghi nhận một vi phạm hoặc tính độ trễ:

$$
late_i = \max(0, start_i - b_i)
$$

### 1.4. Tính khả thi của route

Một route khả thi thường phải đồng thời thỏa mãn phân công, tải, thời gian bay, năng lượng và các giới hạn an toàn. Trong thực tế, không phải lúc nào cũng nên dùng một định nghĩa khả thi cứng; việc dùng penalty cho phép thuật toán tiếp tục khám phá những vùng nghiệm gần khả thi.

---

## 2. Vì sao đây là bài toán tối ưu tổ hợp?

Không gian nghiệm bao gồm cả việc phân chia nhiệm vụ cho các UAV và việc sắp xếp thứ tự trong từng route. Với $n$ nhiệm vụ, riêng số thứ tự đã có thể tăng theo cấp số giai thừa:

$$
n!
$$

Khi có nhiều UAV, số cách phân chia nhiệm vụ làm không gian tìm kiếm lớn hơn nữa. Vì vậy, việc duyệt toàn bộ nghiệm thường không phù hợp với các bài toán kích thước lớn.

Các thuật toán tiến hóa và metaheuristic giải quyết vấn đề bằng cách duy trì một quần thể nghiệm ứng viên, đánh giá chất lượng của chúng, sau đó tạo ra các nghiệm mới từ những nghiệm có triển vọng.

---

## 3. Tối ưu đa mục tiêu

Định tuyến UAV thường có nhiều mục tiêu xung đột:

- giảm quãng đường hoặc thời gian bay;
- giảm mức phơi nhiễm rủi ro;
- cân bằng tải giữa các UAV;
- giảm độ trễ deadline;
- giảm năng lượng tiêu thụ.

Một cách đơn giản là gộp các mục tiêu thành một hàm có trọng số:

$$
F = \sum_{m=1}^{M} w_m f_m
$$

Tuy nhiên, cách này yêu cầu chọn trước các trọng số $w_m$. Một thay đổi nhỏ trong trọng số có thể làm thay đổi nghiệm được chọn, và một bộ trọng số duy nhất không thể hiện đầy đủ các phương án đánh đổi.

Tối ưu đa mục tiêu giữ các mục tiêu riêng biệt và tìm một tập nghiệm đại diện cho nhiều lựa chọn khác nhau.

---

## 4. Quan hệ trội và tập Pareto

Giả sử tất cả objective đều cần minimize. Nghiệm $A$ trội nghiệm $B$ nếu:

1. $A$ không tệ hơn $B$ ở mọi objective;
2. $A$ tốt hơn $B$ ở ít nhất một objective.

$$
A \prec B \iff
\left(\forall m, f_m(A) \le f_m(B)\right)
\land
\left(\exists m, f_m(A) < f_m(B)\right)
$$

Nghiệm không bị bất kỳ nghiệm nào khác trội được gọi là nghiệm không trội. Tập các nghiệm không trội được gọi là **Pareto front**.

Ví dụ, một route có thể ngắn hơn nhưng đi qua vùng rủi ro lớn hơn. Route đó không nhất thiết bị loại, vì nó thể hiện một đánh đổi khác với route an toàn hơn nhưng dài hơn.

---

## 5. Mô hình hóa rủi ro

Rủi ro có thể được mô hình hóa bằng nhiều cách, chẳng hạn:

- các vùng nguy hiểm hình học;
- bản đồ cường độ rủi ro liên tục;
- xác suất sự cố;
- điều kiện thời tiết hoặc gió;
- nguy cơ mất liên lạc;
- hàm rủi ro phụ thuộc vào thời gian và độ cao.

Với một đoạn bay $s$, mức phơi nhiễm rủi ro tổng quát có thể viết là:

$$
Risk(s) = \int_s \rho(x,y,t,h)\, ds
$$

trong đó $\rho$ là cường độ rủi ro tại vị trí $(x,y)$, thời điểm $t$ và độ cao $h$.

Nếu dùng vùng tròn có tâm $(x_r,y_r)$ và bán kính $r$, đoạn bay đi vào vùng đó có thể được tính theo chiều dài phần giao nhau. Một mô hình đơn giản là:

$$
Exposure(s,r) = l_r \cdot w_r
$$

trong đó $l_r$ là chiều dài đoạn nằm trong vùng rủi ro và $w_r$ là trọng số thể hiện mức độ nghiêm trọng của vùng.

Tổng risk của một đội UAV là:

$$
F_{risk} = \sum_{k=1}^{K} Risk(R_k)
$$

---

## 6. Các objective thường dùng

### 6.1. Quãng đường hoặc thời gian bay

$$
F_{travel} = \sum_{k=1}^{K} distance(R_k)
$$

Objective này có thể được thay bằng tổng thời gian, thời gian hoàn thành cuối cùng hoặc một đại lượng kết hợp giữa quãng đường và tốc độ bay.

### 6.2. Rủi ro

$$
F_{risk} = \sum_{k=1}^{K} Risk(R_k)
$$

Objective này khuyến khích UAV tránh các vùng nguy hiểm, nhưng việc giảm rủi ro thường làm route dài hơn.

### 6.3. Cân bằng tải

Gọi $load_k$ là tổng tải trên UAV $k$. Một mục tiêu phổ biến là:

$$
F_{load} = \max_{k=1,\ldots,K} load_k
$$

Có thể dùng thêm độ lệch chuẩn của tải để đo mức cân bằng giữa các UAV.

### 6.4. Độ trễ deadline

$$
F_{late} = \sum_i \max(0, start_i-b_i)
$$

Với nhiệm vụ có mức ưu tiên $p_i$, độ trễ có thể được tính trọng số:

$$
F_{priority} = \sum_i p_i \max(0, start_i-b_i)
$$

### 6.5. Năng lượng

Một mô hình đơn giản của năng lượng là:

$$
energy_k = c_d \cdot distance(R_k) + c_s \cdot service(R_k)
$$

Ràng buộc năng lượng có dạng:

$$
energy_k \le B_k
$$

hoặc năng lượng được đưa thành một objective riêng.

---

## 7. Biểu diễn nghiệm

Một nghiệm có thể được biểu diễn trực tiếp bằng danh sách route, hoặc gián tiếp bằng một chromosome.

Với biểu diễn permutation, chromosome chứa mỗi nhiệm vụ đúng một lần:

```text
[i_7, i_2, i_9, i_1, i_5, ...]
```

Một bộ giải mã sẽ chuyển chromosome thành các route của UAV. Cách biểu diễn này giúp crossover và mutation duy trì điều kiện không lặp, không mất nhiệm vụ.

Ngoài permutation, có thể dùng:

- vector gán nhiệm vụ cho UAV kết hợp với thứ tự;
- biểu diễn nhiều route trực tiếp;
- mã hóa có separator giữa các UAV;
- biểu diễn theo vị trí kế tiếp hoặc ma trận cung.

Không có biểu diễn duy nhất tốt cho mọi bài toán. Biểu diễn nên phù hợp với toán tử di truyền và cơ chế sửa nghiệm của bài toán cụ thể.

### 7.1. Decoder và repair

Decoder chuyển một chromosome thành route có ý nghĩa. Trong quá trình đó, nó có thể:

- phân chia nhiệm vụ cho các UAV;
- kiểm tra sức chứa;
- đánh giá thời gian đến và thời gian chờ;
- tránh hoặc giảm đoạn bay qua vùng rủi ro;
- sửa các route vi phạm;
- đưa nhiệm vụ vào vị trí làm tăng chi phí ít nhất.

Repair heuristic giúp thuật toán tiến hóa sử dụng kiến thức miền, nhưng cần tránh việc repair quá mạnh khiến quần thể mất đa dạng.

---

## 8. NSGA-III

NSGA-III là thuật toán tiến hóa đa mục tiêu dựa trên non-dominated sorting và các **reference directions**. Nó đặc biệt phù hợp khi số objective từ ba trở lên.

NSGA-II thường duy trì đa dạng bằng crowding distance. NSGA-III thay cơ chế này bằng các hướng tham chiếu trong không gian objective, nhờ đó kiểm soát tốt hơn sự phân bố của nghiệm trên Pareto front.

### 8.1. Khởi tạo quần thể

Tạo một quần thể gồm nhiều nghiệm ứng viên. Các nghiệm có thể được tạo ngẫu nhiên, bằng heuristic, hoặc kết hợp cả hai.

Mỗi nghiệm được giải mã và đánh giá bởi vector objective:

$$
F(x) = [f_1(x), f_2(x), \ldots, f_M(x)]
$$

### 8.2. Tạo thế hệ mới

Từ quần thể hiện tại, chọn các parent và tạo offspring bằng:

- crossover để kết hợp các phần tốt của parent;
- mutation để tạo biến đổi mới;
- repair để khôi phục các ràng buộc quan trọng.

Với permutation, order crossover, swap mutation và insertion mutation là các lựa chọn thường gặp.

### 8.3. Non-dominated sorting

Gộp parent và offspring thành một quần thể hợp nhất, sau đó chia thành các front:

- front thứ nhất gồm các nghiệm không bị trội;
- front tiếp theo gồm các nghiệm chỉ bị trội bởi front trước;
- quá trình tiếp tục cho đến khi phân loại hết quần thể.

Các front tốt hơn được ưu tiên trước.

### 8.4. Chuẩn hóa objective

Các objective có thể có thang đo rất khác nhau. Gọi ideal point là:

$$
z^*_m = \min_i f_m(x_i)
$$

Một dạng chuẩn hóa là:

$$
\bar f_m(x_i) =
\frac{f_m(x_i)-z^*_m}{s_m}
$$

trong đó $s_m$ là độ rộng hoặc một hệ số scale của objective $m$. Chuẩn hóa giúp việc so sánh với các hướng tham chiếu không bị chi phối bởi đơn vị đo.

### 8.5. Reference directions

Với $M$ objective, một hướng tham chiếu là vector không âm:

$$
d = (d_1,d_2,\ldots,d_M),
\qquad \sum_{m=1}^{M} d_m = 1
$$

Các hướng này phủ không gian objective từ những hướng ưu tiên một objective đến các hướng thể hiện sự đánh đổi cân bằng hơn.

### 8.6. Gán nghiệm vào hướng tham chiếu

Với vector objective chuẩn hóa $y$ và hướng $d$, khoảng cách vuông góc có thể được tính thông qua hình chiếu:

$$
proj_d(y) = \frac{y \cdot d}{\|d\|^2}d
$$

$$
distance(y,d) = \|y-proj_d(y)\|
$$

Mỗi nghiệm được gán cho hướng gần nhất. Khi cần chọn một phần của front cuối, thuật toán ưu tiên các hướng đang ít nghiệm để giữ độ phủ đa dạng.

### 8.7. Quy trình tổng quát

```text
Tạo quần thể ban đầu và đánh giá các nghiệm
Tạo các hướng tham chiếu

Lặp cho đến điều kiện dừng:
    Tạo offspring bằng chọn lọc, crossover và mutation
    Đánh giá offspring
    Gộp parent và offspring
    Phân loại bằng non-dominated sorting
    Chuẩn hóa objective
    Chọn quần thể mới bằng reference directions

Trả về các nghiệm không bị trội
```

---

## 9. Định tuyến động

Trong môi trường động, thông tin đầu vào có thể thay đổi khi UAV đang thực hiện nhiệm vụ:

- vùng rủi ro thay đổi;
- nhiệm vụ mới xuất hiện hoặc bị hủy;
- deadline được cập nhật;
- vị trí UAV thay đổi;
- năng lượng còn lại giảm;
- điều kiện thời tiết hoặc liên lạc thay đổi.

Vì vậy, một route được tính tại thời điểm ban đầu có thể không còn phù hợp về sau.

### 9.1. Rolling horizon

Rolling horizon chia quá trình điều phối thành các thời điểm quyết định. Tại mỗi thời điểm:

1. cập nhật trạng thái thực tế của hệ thống;
2. giữ lại các nhiệm vụ đã hoàn thành;
3. tối ưu phần route chưa thực hiện;
4. chỉ thực thi một đoạn ngắn của lời giải;
5. lặp lại khi có thông tin mới hoặc đến thời điểm quyết định tiếp theo.

Ưu điểm của cách này là route có thể phản ứng với các thay đổi mà không cần cam kết cố định cho toàn bộ thời gian hoạt động.

### 9.2. Warm start

Quần thể ở thời điểm trước có thể được dùng làm điểm khởi đầu cho lần tối ưu tiếp theo. Các nghiệm cũ được cập nhật theo vị trí hiện tại và trạng thái mới, sau đó trộn với một số nghiệm mới để duy trì khả năng khám phá.

Warm start thường giúp giảm thời gian hội tụ, nhưng cần tránh giữ quá nhiều cấu trúc cũ khi môi trường đã thay đổi mạnh.

### 9.3. Rủi ro phụ thuộc thời gian

Với hàm rủi ro $\rho(x,y,t)$, chi phí của một route phụ thuộc vào thời điểm UAV đi qua từng đoạn:

$$
F_{risk}(R_k) = \int_{R_k} \rho(x,y,t)\, ds
$$

Điều này làm cho thứ tự nhiệm vụ ảnh hưởng không chỉ đến quãng đường và deadline mà còn đến rủi ro gặp phải trên đường bay.

---

## 10. Các hướng mở rộng

NSGA-III có thể được mở rộng để xử lý:

- nhiều loại UAV với tốc độ và sức chứa khác nhau;
- nhiều depot hoặc điểm sạc;
- bay nhiều chuyến và quay về nạp tải;
- giới hạn năng lượng theo từng UAV;
- ưu tiên nhiệm vụ khẩn cấp;
- risk map liên tục thay đổi;
- ràng buộc vùng cấm bay;
- mất liên lạc hoặc không chắc chắn trong dữ liệu;
- phối hợp giữa UAV và phương tiện mặt đất.

Khi số objective tăng, lợi ích của reference directions trở nên rõ hơn, nhưng việc chuẩn hóa, chọn số hướng và duy trì đa dạng cũng trở nên khó hơn.

---

## 11. Đánh giá thuật toán về mặt nghiên cứu

Đánh giá một thuật toán đa mục tiêu không nên chỉ dựa trên một nghiệm tốt nhất. Các khía cạnh cần xem xét gồm:

- chất lượng của Pareto front;
- độ phủ và độ đa dạng của nghiệm;
- khả năng giữ tính khả thi;
- mức rủi ro, thời gian, tải và năng lượng;
- thời gian tính toán;
- độ ổn định qua nhiều lần chạy;
- khả năng thích ứng sau biến động động.

Một số chỉ số thường dùng là hypervolume, spacing, inverted generational distance và tỷ lệ nghiệm khả thi. Khi so sánh, cần sử dụng cùng điều kiện tính toán và báo cáo cả giá trị trung bình lẫn độ phân tán.

---

## 12. Tóm tắt

Bài toán Dynamic Risk-Aware Multi-UAV Routing là một bài toán tối ưu tổ hợp, đa mục tiêu và biến thiên theo thời gian. NSGA-III tạo ra nhiều nghiệm ứng viên, đánh giá đồng thời các mục tiêu như thời gian, rủi ro, tải, deadline và năng lượng, sau đó dùng non-dominated sorting cùng reference directions để giữ lại các nghiệm vừa tốt vừa đa dạng. Trong môi trường động, rolling horizon và warm start cho phép cập nhật kế hoạch khi trạng thái UAV, nhiệm vụ hoặc bản đồ rủi ro thay đổi.

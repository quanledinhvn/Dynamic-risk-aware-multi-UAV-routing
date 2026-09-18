# ALNS từ con số 0: giải thích từng bước cho bài toán định tuyến nhiều UAV

> Tài liệu này dành cho người chưa biết ALNS và chưa cần có kiến thức trước về tối ưu tổ hợp. Mục tiêu là hiểu được: bài toán cần giải là gì, tại sao cần ALNS, một vòng ALNS làm gì, các công thức có ý nghĩa gì, và cách áp dụng ALNS vào đề tài **Dynamic risk-aware multi-UAV routing**.

## 0. Tên đúng là ALNS hay ANLS?

Tên thường dùng trong tài liệu khoa học là **ALNS**, viết tắt của:

- **Adaptive**: thích nghi, tức là thuật toán học xem cách tìm kiếm nào đang hiệu quả;
- **Large Neighborhood**: lân cận lớn, tức là mỗi lần có thể thay đổi một phần đáng kể của lời giải;
- **Search**: tìm kiếm.

Tên tiếng Việt có thể hiểu là **tìm kiếm lân cận lớn thích nghi**.

“ANLS” thường chỉ là cách viết nhầm thứ tự hai chữ `L` và `N`. Trong toàn bộ tài liệu này ta dùng tên **ALNS**.

---

## 1. Đặt vấn đề bằng một tình huống cụ thể

Giả sử có một trung tâm cứu hộ sở hữu 3 UAV. Trên bản đồ có 20 địa điểm cần quan sát hoặc giao vật tư.

Mỗi địa điểm có thể có:

- một vị trí khác nhau;
- một hạn chót khác nhau;
- một mức độ nguy hiểm khác nhau;
- một thời gian phục vụ khác nhau;
- một lượng hàng cần giao khác nhau.

Mỗi UAV lại có:

- dung lượng pin hữu hạn;
- tải trọng hữu hạn;
- vị trí hiện tại;
- tốc độ bay;
- trạng thái sẵn sàng khác nhau.

Ta phải trả lời ba câu hỏi:

1. Nhiệm vụ nào được giao cho UAV nào?
2. Mỗi UAV thăm các nhiệm vụ theo thứ tự nào?
3. Khi bản đồ rủi ro, pin hoặc nhiệm vụ thay đổi, ta sửa kế hoạch ra sao?

Một kế hoạch tốt không chỉ ngắn. Nó còn phải:

- không làm UAV hết pin giữa đường;
- không vượt quá tải trọng;
- đến địa điểm trước hạn chót;
- tránh hoặc hạn chế đi qua vùng nguy hiểm;
- ưu tiên nhiệm vụ khẩn cấp;
- có thể được cập nhật nhanh khi môi trường thay đổi.

Đây là một bài toán **tối ưu tổ hợp**: số cách phân công và sắp thứ tự tăng cực nhanh khi số nhiệm vụ tăng.

### 1.1. Vì sao không thử hết mọi phương án?

Chỉ xét một UAV và `n` nhiệm vụ, số thứ tự thăm có thể có là:

$$
n!
$$

Trong đó:

- $n$ là số nhiệm vụ;
- dấu `!` là phép giai thừa;
- $n! = 1 \times 2 \times 3 \times \dots \times n$.

**Diễn giải bằng lời:** nếu có $n$ nhiệm vụ thì chỉ riêng việc đổi thứ tự thăm đã tạo ra $n!$ phương án.

Ví dụ:

- 5 nhiệm vụ có $5! = 120$ thứ tự;
- 10 nhiệm vụ có $10! = 3\,628\,800$ thứ tự;
- 20 nhiệm vụ có khoảng $2{,}43 \times 10^{18}$ thứ tự.

Khi có nhiều UAV, ta còn phải chọn nhiệm vụ cho từng UAV. Vì vậy số phương án còn lớn hơn nhiều. Duyệt toàn bộ thường không phù hợp với một hệ thống cần phản ứng nhanh.

---

## 2. Trước khi nói về ALNS: “lời giải” là gì?

Giả sử:

- depot là căn cứ, ký hiệu là `0`;
- có 6 nhiệm vụ, ký hiệu từ `1` đến `6`;
- có 2 UAV, ký hiệu là UAV A và UAV B.

Một lời giải có thể là:

```text
UAV A: 0 → 1 → 4 → 2 → 0
UAV B: 0 → 5 → 3 → 6 → 0
```

Ý nghĩa:

- UAV A rời căn cứ, làm nhiệm vụ 1, 4, 2 rồi trở về;
- UAV B rời căn cứ, làm nhiệm vụ 5, 3, 6 rồi trở về;
- mỗi nhiệm vụ xuất hiện đúng một lần.

Ta ký hiệu toàn bộ lời giải là $S$. Chữ $S$ đến từ từ tiếng Anh *solution*, nghĩa là lời giải.

Một **lời giải khả thi** là lời giải thỏa tất cả ràng buộc bắt buộc, ví dụ:

- mỗi nhiệm vụ được phục vụ đúng một lần;
- mỗi tuyến bắt đầu và kết thúc đúng nơi quy định;
- UAV không vượt tải trọng;
- UAV đủ pin;
- UAV không đi vào vùng cấm bay;
- các hạn thời gian bắt buộc được tôn trọng.

Một **lời giải không khả thi** là lời giải vi phạm ít nhất một ràng buộc bắt buộc.

---

## 3. Làm sao biết lời giải nào tốt hơn?

Ta cần một **hàm mục tiêu**. Hàm này biến một lời giải thành một con số để so sánh.

Ví dụ đơn giản nhất là tổng quãng đường:

$$
D(S) = \sum_{k \in K}\sum_{(i,j) \in R_k} d_{ij}
$$

Trong đó:

- $S$ là lời giải đang được đánh giá;
- $D(S)$ là tổng quãng đường của lời giải $S$;
- $K$ là tập các UAV;
- $k$ là chỉ số của một UAV trong tập $K$;
- $R_k$ là tập các chặng bay trong tuyến của UAV $k$;
- $(i,j)$ là chặng bay trực tiếp từ điểm $i$ đến điểm $j$;
- $d_{ij}$ là khoảng cách từ điểm $i$ đến điểm $j$;
- ký hiệu $\sum$ có nghĩa là cộng tất cả các phần tử thỏa điều kiện bên dưới nó.

**Diễn giải bằng lời:** với từng UAV, cộng độ dài của tất cả chặng mà UAV đó bay; sau đó cộng kết quả của tất cả UAV.

Nếu chỉ tối thiểu hóa quãng đường, thuật toán có thể chọn một tuyến ngắn nhưng nguy hiểm hoặc trễ hạn. Vì vậy đề tài này cần một hàm mục tiêu giàu thông tin hơn.

### 3.1. Một hàm mục tiêu tổng hợp cho đề tài

Ta có thể dùng:

$$
F(S)=\alpha D(S)+\beta E(S)+\gamma L(S)+\delta U(S)+M V(S)
$$

Trong đó:

- $F(S)$ là tổng chi phí của lời giải $S$; giá trị càng nhỏ càng tốt;
- $D(S)$ là tổng quãng đường;
- $E(S)$ là mức phơi nhiễm rủi ro trên đường bay;
- $L(S)$ là tổng mức trễ hạn;
- $U(S)$ là chi phí của các nhiệm vụ chưa được phục vụ;
- $V(S)$ là tổng mức vi phạm các ràng buộc cứng;
- $\alpha$ là trọng số của quãng đường;
- $\beta$ là trọng số của rủi ro;
- $\gamma$ là trọng số của trễ hạn;
- $\delta$ là trọng số của nhiệm vụ chưa phục vụ;
- $M$ là một hệ số phạt lớn đối với vi phạm ràng buộc.

**Diễn giải bằng lời:** tổng chi phí bằng chi phí quãng đường, cộng chi phí rủi ro, cộng chi phí trễ, cộng chi phí bỏ sót nhiệm vụ, cộng một khoản phạt lớn nếu lời giải vi phạm ràng buộc.

Các trọng số $\alpha,\beta,\gamma,\delta$ giúp đưa các đại lượng khác đơn vị về cùng một thang đo và thể hiện mức ưu tiên. Chẳng hạn, nếu an toàn quan trọng hơn một chút quãng đường thì có thể tăng $\beta$.

> Lưu ý: cộng trọng số tạo ra một mục tiêu duy nhất. Nếu nghiên cứu muốn giữ nhiều mục tiêu riêng biệt và tìm tập nghiệm Pareto, cần cơ chế đa mục tiêu khác. Tài liệu này trước hết giải thích ALNS một mục tiêu để dễ hiểu.

### 3.2. Mức trễ hạn được tính như thế nào?

Với nhiệm vụ $i$, mức trễ có thể được tính bằng:

$$
\ell_i = \max(0, a_i-b_i)
$$

Trong đó:

- $i$ là một nhiệm vụ;
- $a_i$ là thời điểm UAV đến nhiệm vụ $i$;
- $b_i$ là hạn muộn nhất mong muốn của nhiệm vụ $i$;
- $\ell_i$ là lượng thời gian bị trễ tại nhiệm vụ $i$;
- $\max(x,y)$ lấy giá trị lớn hơn giữa $x$ và $y$.

**Diễn giải bằng lời:** nếu UAV đến trước hoặc đúng hạn thì độ trễ bằng 0; nếu UAV đến sau hạn thì độ trễ bằng thời điểm đến trừ hạn chót.

Tổng độ trễ là:

$$
L(S)=\sum_{i \in N}\ell_i
$$

Trong đó:

- $N$ là tập tất cả nhiệm vụ;
- $L(S)$ là tổng độ trễ của lời giải $S$.

**Diễn giải bằng lời:** cộng độ trễ của tất cả nhiệm vụ để có tổng độ trễ của kế hoạch.

### 3.3. Rủi ro trên đường bay được tính như thế nào?

Một mô hình đơn giản cho rủi ro của chặng từ $i$ đến $j$ là:

$$
e_{ij}=d_{ij}\,r_{ij}
$$

Trong đó:

- $e_{ij}$ là mức phơi nhiễm rủi ro trên chặng từ $i$ đến $j$;
- $d_{ij}$ là độ dài chặng bay;
- $r_{ij}$ là mức rủi ro trung bình trên chặng, ví dụ một số từ 0 đến 1.

**Diễn giải bằng lời:** bay càng xa hoặc đi qua khu vực càng nguy hiểm thì mức phơi nhiễm rủi ro càng lớn.

Tổng rủi ro của lời giải là:

$$
E(S)=\sum_{k \in K}\sum_{(i,j)\in R_k}e_{ij}
$$

**Diễn giải bằng lời:** cộng rủi ro của mọi chặng trên mọi tuyến UAV.

Đây chỉ là mô hình khởi đầu. Sau này $e_{ij}$ có thể phụ thuộc vào thời điểm UAV bay qua chặng đó, bởi rủi ro có thể thay đổi theo thời gian.

---

## 4. Từ tìm kiếm cục bộ đến LNS

### 4.1. Tìm kiếm cục bộ là gì?

Ta bắt đầu từ một lời giải, sửa nó một chút, rồi giữ thay đổi nếu kết quả tốt hơn.

Ví dụ, từ tuyến:

```text
0 → 1 → 4 → 2 → 0
```

ta đổi chỗ nhiệm vụ 4 và 2:

```text
0 → 1 → 2 → 4 → 0
```

Những lời giải có thể đạt được bằng một phép thay đổi đã chọn được gọi là **lân cận** của lời giải hiện tại.

Một số phép thay đổi nhỏ phổ biến:

- **swap**: đổi chỗ hai nhiệm vụ;
- **relocate**: lấy một nhiệm vụ và chèn vào vị trí khác;
- **2-opt**: cắt hai cạnh rồi nối lại để đảo một đoạn tuyến.

### 4.2. Cực trị cục bộ là gì?

Hãy tưởng tượng ta đang đứng trong một thung lũng. Mọi bước nhỏ xung quanh đều đi lên, nên ta tưởng mình đã ở nơi thấp nhất. Nhưng phía sau một ngọn đồi có thể còn một thung lũng thấp hơn.

Trong tối ưu:

- lời giải hiện tại tốt hơn tất cả hàng xóm gần của nó;
- nhưng nó chưa chắc là lời giải tốt nhất toàn cục;
- tìm kiếm chỉ dùng thay đổi nhỏ dễ bị mắc kẹt tại đây.

### 4.3. LNS giải quyết vấn đề này ra sao?

**LNS** là *Large Neighborhood Search*, nghĩa là tìm kiếm lân cận lớn.

Thay vì chỉ đổi một hoặc hai nhiệm vụ, LNS:

1. tháo nhiều nhiệm vụ khỏi lời giải;
2. chèn chúng trở lại theo một cách khác.

Hai bước đó có tên:

- **destroy**: phá một phần lời giải;
- **repair**: sửa hoặc xây lại phần vừa phá.

Ví dụ:

```text
Ban đầu:
UAV A: 0 → 1 → 4 → 2 → 0
UAV B: 0 → 5 → 3 → 6 → 0

Destroy tháo {4, 3, 6}:
UAV A: 0 → 1 → 2 → 0
UAV B: 0 → 5 → 0
Chưa gán: {4, 3, 6}

Repair chèn lại:
UAV A: 0 → 3 → 1 → 2 → 0
UAV B: 0 → 5 → 4 → 6 → 0
```

Vì nhiều nhiệm vụ được tháo cùng lúc, thuật toán có thể tạo ra cấu trúc tuyến rất khác và thoát khỏi cực trị cục bộ.

---

## 5. Từ LNS đến ALNS: chữ “Adaptive” thêm điều gì?

Không có một cách destroy hoặc repair nào tốt trong mọi tình huống.

Ví dụ:

- loại ngẫu nhiên giúp tạo đa dạng;
- loại các nhiệm vụ tệ nhất tập trung vào phần đang gây chi phí lớn;
- loại các nhiệm vụ liên quan giúp sắp xếp lại cả một cụm;
- chèn tham lam nhanh nhưng đôi lúc quyết định quá sớm;
- chèn regret thường xử lý tốt những nhiệm vụ khó chèn.

ALNS giữ **nhiều toán tử destroy** và **nhiều toán tử repair**. Trong quá trình chạy, ALNS:

1. chọn một toán tử destroy;
2. chọn một toán tử repair;
3. quan sát kết quả của cặp toán tử;
4. thưởng cho toán tử tạo kết quả tốt;
5. tăng cơ hội chọn lại toán tử có hiệu quả cao.

Một **toán tử** ở đây chỉ là một quy tắc biến đổi lời giải.

Đó là ý nghĩa của “Adaptive”: thuật toán tự điều chỉnh xác suất lựa chọn các toán tử dựa trên hiệu quả đã quan sát.

---

## 6. Bức tranh tổng thể của ALNS

ALNS thường duy trì ba lời giải:

- $S$: lời giải hiện tại;
- $S'$: lời giải ứng viên vừa được tạo;
- $S^*$: lời giải tốt nhất từng tìm thấy, còn gọi là *best-so-far*.

Một vòng lặp gồm:

```text
S hiện tại
   │
   ├─ chọn toán tử destroy
   ↓
Lời giải một phần + tập nhiệm vụ chưa gán
   │
   ├─ chọn toán tử repair
   ↓
S' ứng viên
   │
   ├─ đánh giá chi phí và tính khả thi
   ├─ quyết định có nhận S' làm S mới không
   ├─ cập nhật S* nếu tìm được lời giải tốt nhất mới
   └─ thưởng và cập nhật trọng số toán tử
```

Toàn bộ quá trình lặp lại cho đến khi hết thời gian, đủ số vòng lặp, hoặc không còn cải thiện đáng kể.

---

## 7. Bước 1 — Tạo lời giải ban đầu

ALNS cần một điểm xuất phát $S_0$. Ký hiệu $S_0$ nghĩa là lời giải ở thời điểm khởi đầu.

Một cách dễ cài đặt là **chèn tham lam**:

1. bắt đầu với tuyến rỗng của mỗi UAV;
2. lấy một nhiệm vụ chưa được gán;
3. thử chèn nó vào mọi vị trí của mọi tuyến;
4. bỏ các vị trí gây vi phạm ràng buộc;
5. chọn vị trí làm tăng chi phí ít nhất;
6. lặp lại đến khi hết nhiệm vụ hoặc không còn vị trí khả thi.

Nếu chèn nhiệm vụ $u$ vào giữa hai điểm liên tiếp $i$ và $j$, phần tăng quãng đường là:

$$
\Delta D(i,u,j)=d_{iu}+d_{uj}-d_{ij}
$$

Trong đó:

- $u$ là nhiệm vụ cần chèn;
- $i$ là điểm đứng ngay trước vị trí chèn;
- $j$ là điểm đứng ngay sau vị trí chèn;
- $d_{iu}$ là khoảng cách từ $i$ đến $u$;
- $d_{uj}$ là khoảng cách từ $u$ đến $j$;
- $d_{ij}$ là khoảng cách cũ từ $i$ đến $j$;
- $\Delta D(i,u,j)$ là lượng quãng đường tăng thêm.

**Diễn giải bằng lời:** ta bỏ chặng cũ $i \rightarrow j$, thêm hai chặng $i \rightarrow u$ và $u \rightarrow j$; độ tăng bằng tổng hai chặng mới trừ chặng cũ.

Trong bài toán đầy đủ, không nên chỉ xét khoảng cách. Ta xét độ tăng của cả hàm mục tiêu:

$$
\Delta F = F(S_{\text{after}})-F(S_{\text{before}})
$$

Trong đó:

- $S_{\text{before}}$ là lời giải trước khi chèn;
- $S_{\text{after}}$ là lời giải sau khi chèn;
- $\Delta F$ là lượng thay đổi chi phí do phép chèn.

**Diễn giải bằng lời:** lấy chi phí sau khi chèn trừ chi phí trước khi chèn. Nếu $\Delta F$ nhỏ thì vị trí chèn ít làm lời giải xấu đi hơn.

Lời giải ban đầu chưa cần rất tốt. Nó chỉ cần được tạo nhanh và, nếu thiết kế ALNS theo hướng luôn khả thi, phải thỏa các ràng buộc cứng.

---

## 8. Bước 2 — Chọn số nhiệm vụ cần tháo

Gọi $q$ là số nhiệm vụ sẽ bị tháo trong một vòng destroy.

Có thể chọn cố định, ví dụ $q=5$, hoặc chọn theo tỷ lệ:

$$
q=\max(1,\lfloor \eta n \rfloor)
$$

Trong đó:

- $n$ là tổng số nhiệm vụ đang có trong lời giải;
- $\eta$ là tỷ lệ phá, ví dụ $\eta=0{,}2$ nghĩa là 20%;
- $\lfloor x \rfloor$ là phần nguyên không vượt quá $x$;
- $\max(1,x)$ bảo đảm ít nhất một nhiệm vụ bị tháo;
- $q$ là số nhiệm vụ thực sự bị tháo.

**Diễn giải bằng lời:** lấy một tỷ lệ $\eta$ của tổng số nhiệm vụ, làm tròn xuống, nhưng không cho kết quả nhỏ hơn 1.

Nếu $q$ quá nhỏ, ALNS gần giống tìm kiếm cục bộ và khó thoát bẫy. Nếu $q$ quá lớn, phần lớn cấu trúc tốt bị xóa và bước repair trở nên chậm. Vì vậy có thể chọn ngẫu nhiên $q$ trong một khoảng để tạo đa dạng.

---

## 9. Bước 3 — Destroy: tháo nhiệm vụ như thế nào?

Destroy không xóa nhiệm vụ khỏi bài toán. Nó chỉ tạm thời đưa một số nhiệm vụ vào tập **chưa gán** để repair chèn lại.

Gọi tập nhiệm vụ bị tháo là $U$. Chữ $U$ có thể hiểu là *unassigned*, tức chưa được gán.

### 9.1. Random removal — loại ngẫu nhiên

Chọn ngẫu nhiên $q$ nhiệm vụ trong lời giải.

Ưu điểm:

- rất dễ cài đặt;
- chạy nhanh;
- tạo đa dạng;
- không phụ thuộc nhiều vào mô hình chi phí.

Nhược điểm: có thể tháo những nhiệm vụ đang nằm ở vị trí tốt và bỏ qua phần thật sự có vấn đề.

### 9.2. Worst removal — loại nhiệm vụ “tệ nhất”

Ta ước lượng mức đóng góp chi phí của nhiệm vụ $u$ bằng cách xem chi phí giảm bao nhiêu nếu tạm bỏ $u$:

$$
s_u = F(S)-F(S\setminus\{u\})
$$

Trong đó:

- $u$ là nhiệm vụ đang xét;
- $S\setminus\{u\}$ là lời giải $S$ sau khi tạm bỏ nhiệm vụ $u$;
- $s_u$ là mức tiết kiệm chi phí khi bỏ $u$.

**Diễn giải bằng lời:** nếu bỏ nhiệm vụ $u$ làm chi phí giảm rất nhiều thì vị trí hiện tại của $u$ có thể đang tệ; ta ưu tiên tháo nó để tìm vị trí khác.

Không nên lúc nào cũng chọn đúng $q$ nhiệm vụ có $s_u$ lớn nhất, vì như vậy thuật toán quá tất định. Có thể thêm ngẫu nhiên để vẫn khám phá các phương án khác.

### 9.3. Related removal — loại các nhiệm vụ liên quan

Đầu tiên chọn một nhiệm vụ hạt giống $i$. Sau đó ưu tiên tháo các nhiệm vụ $j$ có mức liên quan cao với $i$.

Ta có thể định nghĩa **độ không giống nhau**:

$$
R(i,j)=\lambda_d\,\widehat d_{ij}
+\lambda_t\,|\widehat a_i-\widehat a_j|
+\lambda_r\,|\widehat r_i-\widehat r_j|
+\lambda_k\,\mathbf{1}[k(i)\ne k(j)]
$$

Trong đó:

- $R(i,j)$ là độ không giống nhau giữa nhiệm vụ $i$ và $j$; càng nhỏ nghĩa là càng liên quan;
- $\widehat d_{ij}$ là khoảng cách đã chuẩn hóa giữa $i$ và $j$;
- $\widehat a_i$ và $\widehat a_j$ là thời điểm phục vụ đã chuẩn hóa của hai nhiệm vụ;
- $\widehat r_i$ và $\widehat r_j$ là mức rủi ro đã chuẩn hóa;
- dấu mũ `^` ở đây cho biết đại lượng đã được đưa về cùng thang đo, thường từ 0 đến 1;
- $k(i)$ là UAV đang phục vụ nhiệm vụ $i$;
- $\mathbf{1}[k(i)\ne k(j)]$ bằng 1 nếu hai nhiệm vụ thuộc hai UAV khác nhau, ngược lại bằng 0;
- $\lambda_d,\lambda_t,\lambda_r,\lambda_k$ là các trọng số thể hiện mức quan trọng của khoảng cách, thời gian, rủi ro và tuyến UAV;
- $|x|$ là trị tuyệt đối của $x$.

**Diễn giải bằng lời:** hai nhiệm vụ được coi là liên quan nếu chúng ở gần nhau, có thời gian phục vụ gần nhau, có mức rủi ro gần nhau hoặc đang nằm trên các tuyến có quan hệ cần xem xét. Ta tháo cả cụm để repair có cơ hội phân vùng lại.

### 9.4. Route removal — loại cả tuyến hoặc một đoạn tuyến

Chọn một UAV và tháo toàn bộ hoặc một đoạn liên tiếp trên tuyến của nó.

Toán tử này phù hợp khi:

- phân công giữa các UAV đang mất cân bằng;
- một UAV gần hết pin;
- một tuyến đi qua vùng vừa trở nên nguy hiểm;
- cần xây lại phần lớn kế hoạch của một UAV.

### 9.5. Risk-priority removal — loại theo rủi ro

Đây là toán tử chuyên biệt phù hợp với đề tài. Ta có thể chấm điểm một nhiệm vụ đang được phục vụ chưa tốt:

$$
h_i = r_i\left(\omega_t\widehat a_i+\omega_e\widehat e_i+\omega_l\widehat \ell_i\right)
$$

Trong đó:

- $h_i$ là điểm cần xem xét lại của nhiệm vụ $i$;
- $r_i$ là mức ưu tiên hoặc mức nghiêm trọng của nhiệm vụ $i$;
- $\widehat a_i$ là thời điểm đến đã chuẩn hóa;
- $\widehat e_i$ là rủi ro đường bay để tới nhiệm vụ đã chuẩn hóa;
- $\widehat \ell_i$ là độ trễ đã chuẩn hóa;
- $\omega_t,\omega_e,\omega_l$ là các trọng số tương ứng cho thời gian đến, phơi nhiễm và độ trễ.

**Diễn giải bằng lời:** một nhiệm vụ càng nghiêm trọng mà lại được phục vụ càng muộn, qua đường càng nguy hiểm hoặc trễ càng nhiều thì điểm $h_i$ càng lớn; nó càng nên được tháo ra để sắp lại.

Đây chỉ là một thiết kế gợi ý. Khi làm nghiên cứu, cần nêu rõ lý do chọn công thức và thực nghiệm ablation để kiểm tra từng thành phần có thật sự hữu ích hay không.

---

## 10. Bước 4 — Repair: chèn nhiệm vụ trở lại

Sau destroy, ta có:

- các tuyến chưa hoàn chỉnh;
- tập nhiệm vụ chưa gán $U$.

Repair phải chèn các nhiệm vụ trong $U$ trở lại tuyến, đồng thời kiểm tra ràng buộc.

### 10.1. Greedy insertion — chèn tham lam

Với mọi nhiệm vụ chưa gán:

1. thử mọi vị trí trên mọi tuyến;
2. tính độ tăng chi phí $\Delta F$;
3. bỏ vị trí không khả thi;
4. chọn phép chèn có $\Delta F$ nhỏ nhất;
5. lặp lại.

Nếu $P(u)$ là tập các vị trí khả thi để chèn nhiệm vụ $u$, chi phí chèn tốt nhất là:

$$
c_1(u)=\min_{p\in P(u)}\Delta F(u,p)
$$

Trong đó:

- $u$ là nhiệm vụ chưa gán;
- $p$ là một vị trí chèn;
- $P(u)$ là tập tất cả vị trí chèn khả thi của $u$;
- $\Delta F(u,p)$ là lượng chi phí tăng khi chèn $u$ tại $p$;
- $c_1(u)$ là chi phí của vị trí chèn tốt nhất cho $u$;
- $\min$ nghĩa là chọn giá trị nhỏ nhất.

**Diễn giải bằng lời:** thử mọi chỗ hợp lệ và ghi lại chỗ làm tăng chi phí ít nhất.

Greedy nhanh và dễ hiểu, nhưng có thể dành mất một vị trí quý giá của nhiệm vụ khác.

### 10.2. Regret-2 insertion — chèn theo “độ hối tiếc”

Giả sử một nhiệm vụ có:

- vị trí tốt nhất làm tăng chi phí 2;
- vị trí tốt thứ hai làm tăng chi phí 20.

Nếu không chèn ngay vào vị trí tốt nhất, sau đó ta có thể phải trả thêm 18. Nhiệm vụ này cần được ưu tiên.

Với nhiệm vụ $u$, gọi:

- $c_1(u)$ là chi phí chèn tốt nhất;
- $c_2(u)$ là chi phí chèn tốt thứ hai.

Độ regret-2 là:

$$
\operatorname{regret}_2(u)=c_2(u)-c_1(u)
$$

**Diễn giải bằng lời:** độ hối tiếc bằng chi phí của lựa chọn tốt thứ hai trừ chi phí của lựa chọn tốt nhất. Khoảng cách càng lớn thì việc bỏ lỡ vị trí tốt nhất càng nguy hiểm.

Thuật toán chọn nhiệm vụ có $\operatorname{regret}_2(u)$ lớn nhất và chèn nó vào vị trí tốt nhất.

Tổng quát hơn, regret-$m$ có thể viết:

$$
\operatorname{regret}_m(u)=\sum_{h=2}^{m}\left(c_h(u)-c_1(u)\right)
$$

Trong đó:

- $m$ là số lựa chọn tốt được đem ra so sánh;
- $c_h(u)$ là chi phí chèn tốt thứ $h$ của nhiệm vụ $u$;
- $h$ là thứ hạng của vị trí chèn;
- $\operatorname{regret}_m(u)$ là tổng thiệt hại tiềm năng nếu mất lựa chọn tốt nhất.

**Diễn giải bằng lời:** so sánh vị trí tốt nhất với nhiều vị trí kế tiếp; nhiệm vụ nào ít lựa chọn thay thế tốt sẽ được ưu tiên.

### 10.3. Risk-priority insertion — chèn nhiệm vụ khẩn cấp trước

Có thể sắp các nhiệm vụ chưa gán theo điểm ưu tiên:

$$
p_i=\theta_r\widehat r_i+\theta_d(1-\widehat s_i)+\theta_u\widehat u_i
$$

Trong đó:

- $p_i$ là điểm ưu tiên của nhiệm vụ $i$;
- $\widehat r_i$ là mức rủi ro hoặc mức nghiêm trọng đã chuẩn hóa;
- $\widehat s_i$ là thời gian dư trước deadline đã chuẩn hóa;
- $1-\widehat s_i$ lớn khi nhiệm vụ còn ít thời gian;
- $\widehat u_i$ là mức bất định hoặc độ khẩn cấp bổ sung đã chuẩn hóa;
- $\theta_r,\theta_d,\theta_u$ là các trọng số.

**Diễn giải bằng lời:** nhiệm vụ nghiêm trọng hơn, gần hết thời gian hơn hoặc bất định hơn nhận điểm ưu tiên cao hơn và được thử chèn sớm hơn.

Sau khi xác định thứ tự ưu tiên, vẫn phải chọn vị trí chèn dựa trên chi phí và tính khả thi. “Ưu tiên” không có nghĩa là bỏ qua pin hoặc vùng cấm bay.

### 10.4. Feasibility repair — sửa vi phạm

Nếu ALNS cho phép tạm thời tạo lời giải không khả thi, một toán tử repair có thể:

- chuyển nhiệm vụ sang UAV còn pin;
- đổi thứ tự để giảm trễ;
- tách một tuyến quá tải;
- bỏ tạm nhiệm vụ có độ ưu tiên thấp và phạt trong hàm mục tiêu;
- chèn điểm sạc nếu mô hình có trạm sạc.

Có hai triết lý thiết kế:

1. **Luôn khả thi:** mọi phép repair chỉ tạo lời giải thỏa ràng buộc cứng. Dễ phân tích nhưng không gian tìm kiếm hẹp hơn.
2. **Cho phép không khả thi có kiểm soát:** thuật toán đi qua lời giải vi phạm nhẹ và dùng penalty để quay lại miền khả thi. Khám phá rộng hơn nhưng khó điều chỉnh hơn.

Với phiên bản đầu tiên của đồ án, cách “luôn khả thi” thường dễ cài đặt và kiểm thử hơn.

---

## 11. Kiểm tra các ràng buộc quan trọng

### 11.1. Ràng buộc mỗi nhiệm vụ phục vụ một lần

Nếu $x_{ik}=1$ nghĩa là nhiệm vụ $i$ được giao cho UAV $k$, và $x_{ik}=0$ nếu không, ta có:

$$
\sum_{k\in K}x_{ik}=1,\qquad \forall i\in N
$$

Trong đó:

- $N$ là tập nhiệm vụ;
- $K$ là tập UAV;
- $x_{ik}$ là biến nhị phân nhận giá trị 0 hoặc 1;
- $\forall i\in N$ nghĩa là điều kiện đúng với mọi nhiệm vụ $i$ trong $N$.

**Diễn giải bằng lời:** với mỗi nhiệm vụ, tổng số lần nó được gán cho tất cả UAV phải đúng bằng 1.

Trong cài đặt bằng danh sách tuyến, có thể kiểm tra điều này bằng cách đếm số lần xuất hiện của từng mã nhiệm vụ.

### 11.2. Ràng buộc tải trọng

$$
\sum_{i\in R_k} q_i \le Q_k,\qquad \forall k\in K
$$

Trong đó:

- $R_k$ ở công thức này được hiểu là tập nhiệm vụ trên tuyến của UAV $k$;
- $q_i$ là nhu cầu hoặc khối lượng hàng của nhiệm vụ $i$;
- $Q_k$ là tải trọng tối đa của UAV $k$;
- $\le$ nghĩa là nhỏ hơn hoặc bằng.

**Diễn giải bằng lời:** tổng khối lượng hàng giao bởi một UAV không được vượt quá tải trọng của UAV đó.

Nếu UAV giao dần hàng dọc đường, nên kiểm tra tải ở từng chặng thay vì chỉ kiểm tra tổng.

### 11.3. Ràng buộc thời gian

Nếu UAV đi từ $i$ đến $j$ thì thời điểm tới $j$ có thể tính bằng:

$$
a_j=\max(e_j,a_i+s_i+t_{ij})
$$

Trong đó:

- $a_i$ là thời điểm UAV đến điểm $i$;
- $s_i$ là thời gian phục vụ tại điểm $i$;
- $t_{ij}$ là thời gian bay từ $i$ đến $j$;
- $e_j$ là thời điểm sớm nhất được phép bắt đầu phục vụ tại $j$;
- $a_j$ là thời điểm bắt đầu phục vụ tại $j$.

**Diễn giải bằng lời:** UAV đến $j$ sau khi hoàn thành phục vụ ở $i$ và bay tới $j$; nếu đến quá sớm so với cửa sổ thời gian thì phải chờ đến $e_j$.

Nếu deadline cứng của $j$ là $b_j$, điều kiện khả thi là:

$$
a_j\le b_j
$$

Trong đó $b_j$ là thời điểm muộn nhất được phép phục vụ nhiệm vụ $j$.

**Diễn giải bằng lời:** thời điểm phục vụ nhiệm vụ $j$ không được muộn hơn hạn cuối của nó.

### 11.4. Ràng buộc pin

Một mô hình đơn giản:

$$
\sum_{(i,j)\in R_k} c^{\text{energy}}_{ij}\le B_k,\qquad \forall k\in K
$$

Trong đó:

- $c^{\text{energy}}_{ij}$ là năng lượng cần để UAV bay từ $i$ đến $j$;
- chỉ số trên `energy` cho biết đây là chi phí năng lượng, không phải lũy thừa;
- $B_k$ là năng lượng pin khả dụng của UAV $k$;
- $R_k$ là tập các chặng trên tuyến UAV $k$.

**Diễn giải bằng lời:** tổng năng lượng cần cho toàn bộ tuyến không được lớn hơn năng lượng pin UAV có thể sử dụng.

Mô hình thực tế hơn có thể cho năng lượng phụ thuộc vào quãng đường, tải, gió và tốc độ:

$$
c^{\text{energy}}_{ij}=g(d_{ij},w_{ij},m_k,v_k)
$$

Trong đó:

- $g$ là hàm ước lượng năng lượng;
- $d_{ij}$ là khoảng cách;
- $w_{ij}$ là điều kiện gió trên chặng;
- $m_k$ là khối lượng UAV cùng tải hiện tại;
- $v_k$ là tốc độ của UAV.

**Diễn giải bằng lời:** năng lượng của một chặng được tính bởi một hàm phụ thuộc vào độ xa, gió, khối lượng và tốc độ.

---

## 12. Bước 5 — Đánh giá lời giải ứng viên

Sau destroy và repair, ta có lời giải ứng viên $S'$. Ta tính:

$$
\Delta = F(S')-F(S)
$$

Trong đó:

- $F(S')$ là chi phí của lời giải ứng viên;
- $F(S)$ là chi phí của lời giải hiện tại;
- $\Delta$ là mức thay đổi chi phí.

**Diễn giải bằng lời:** lấy chi phí ứng viên trừ chi phí hiện tại.

Vì bài toán đang tối thiểu hóa:

- $\Delta<0$: ứng viên tốt hơn;
- $\Delta=0$: hai lời giải có cùng chi phí;
- $\Delta>0$: ứng viên tệ hơn.

Ta luôn cập nhật lời giải tốt nhất nếu:

$$
F(S')<F(S^*)
$$

Trong đó $S^*$ là lời giải tốt nhất đã gặp từ đầu quá trình tìm kiếm.

**Diễn giải bằng lời:** nếu ứng viên tốt hơn kỷ lục hiện tại thì lưu nó làm kỷ lục mới.

---

## 13. Bước 6 — Vì sao đôi khi phải nhận lời giải tệ hơn?

Nếu chỉ nhận ứng viên tốt hơn, thuật toán lại dễ mắc kẹt ở cực trị cục bộ. ALNS thường dùng tiêu chuẩn chấp nhận của **Simulated Annealing**, viết tắt là SA.

Quy tắc:

- nếu $\Delta\le 0$, luôn chấp nhận;
- nếu $\Delta>0$, chấp nhận với xác suất:

$$
P_{\text{accept}}=\exp\left(-\frac{\Delta}{T}\right)
$$

Trong đó:

- $P_{\text{accept}}$ là xác suất chấp nhận ứng viên tệ hơn;
- $\exp(x)$ là hàm mũ $e^x$, với $e\approx2{,}718$;
- $\Delta$ là lượng chi phí xấu đi;
- $T$ là nhiệt độ hiện tại và luôn dương.

**Diễn giải bằng lời:** ứng viên càng tệ thì càng khó được nhận; nhiệt độ càng cao thì thuật toán càng sẵn sàng thử một bước lùi để khám phá vùng mới.

Ví dụ, nếu $\Delta=4$ và $T=10$:

$$
P_{\text{accept}}=\exp(-4/10)\approx0{,}67
$$

**Diễn giải bằng lời:** ứng viên tệ hơn 4 đơn vị có khoảng 67% cơ hội được nhận khi nhiệt độ bằng 10.

Để thực hiện quyết định, sinh số ngẫu nhiên $z$ phân bố đều trong đoạn $[0,1]$:

$$
\text{chấp nhận nếu }z<P_{\text{accept}}
$$

Trong đó $z$ là một số ngẫu nhiên mà mọi giá trị từ 0 đến 1 có cơ hội xuất hiện như nhau.

**Diễn giải bằng lời:** nếu số ngẫu nhiên nhỏ hơn xác suất cho phép thì nhận ứng viên.

Quan trọng: nhận $S'$ làm lời giải hiện tại không có nghĩa là quên lời giải tốt nhất. $S^*$ vẫn được lưu riêng.

### 13.1. Làm nguội nhiệt độ

Sau mỗi vòng hoặc mỗi nhóm vòng lặp:

$$
T\leftarrow cT
$$

Trong đó:

- mũi tên $\leftarrow$ nghĩa là gán giá trị mới;
- $T$ là nhiệt độ;
- $c$ là hệ số làm nguội, thường nhỏ hơn 1 và gần 1, ví dụ 0,995.

**Diễn giải bằng lời:** nhiệt độ mới bằng nhiệt độ cũ nhân hệ số làm nguội. Vì $c<1$, nhiệt độ giảm dần.

Đầu quá trình, $T$ cao để khám phá. Cuối quá trình, $T$ thấp để thuật toán khắt khe hơn và tập trung tinh chỉnh.

---

## 14. Bước 7 — Chọn toán tử theo trọng số

Giả sử có các destroy operator $d_1,d_2,\dots,d_m$. Mỗi toán tử $d_i$ có trọng số $w_i>0$.

Xác suất chọn toán tử $d_i$ là:

$$
P(d_i)=\frac{w_i}{\sum_{j=1}^{m}w_j}
$$

Trong đó:

- $m$ là số destroy operator;
- $d_i$ là destroy operator thứ $i$;
- $w_i$ là trọng số hiện tại của $d_i$;
- $P(d_i)$ là xác suất chọn $d_i$;
- $j$ là chỉ số dùng để cộng trọng số của tất cả operator.

**Diễn giải bằng lời:** lấy trọng số của một toán tử chia cho tổng trọng số của tất cả toán tử. Trọng số càng lớn thì xác suất được chọn càng cao.

Repair operator được chọn theo cách tương tự.

Đây thường được gọi là **roulette-wheel selection**: mỗi toán tử chiếm một phần của vòng quay tỷ lệ với trọng số của nó.

Không nên luôn chọn toán tử có trọng số cao nhất. Xác suất giúp các toán tử khác vẫn có cơ hội được thử, nhờ đó tránh học quá sớm từ ít dữ liệu.

---

## 15. Bước 8 — Thưởng và cập nhật trọng số toán tử

Sau mỗi vòng lặp, cặp destroy–repair nhận điểm tùy kết quả. Ví dụ:

- $\sigma_1$: điểm khi tạo lời giải tốt nhất mới;
- $\sigma_2$: điểm khi cải thiện lời giải hiện tại;
- $\sigma_3$: điểm khi ứng viên không tốt hơn nhưng vẫn được chấp nhận;
- 0 điểm khi bị từ chối.

Nên chọn $\sigma_1>\sigma_2>\sigma_3\ge0$.

Sau một **segment**, tức một nhóm gồm nhiều vòng lặp, trọng số được cập nhật:

$$
w_i\leftarrow(1-\rho)w_i+\rho\frac{\pi_i}{n_i}
$$

Trong đó:

- $w_i$ là trọng số của toán tử $i$;
- $\rho$ là tốc độ phản ứng, nằm trong khoảng từ 0 đến 1;
- $\pi_i$ là tổng điểm toán tử $i$ nhận trong segment;
- $n_i$ là số lần toán tử $i$ được sử dụng trong segment;
- $\pi_i/n_i$ là điểm trung bình mỗi lần sử dụng.

**Diễn giải bằng lời:** trọng số mới là sự pha trộn giữa trọng số cũ và hiệu quả trung bình vừa quan sát. $\rho$ càng lớn thì thuật toán càng phản ứng nhanh với kết quả mới.

Nếu $n_i=0$, không được chia cho 0. Ta có thể giữ nguyên $w_i$ hoặc chỉ cập nhật những toán tử đã được dùng.

### 15.1. Ví dụ cập nhật trọng số

Giả sử:

- trọng số cũ $w_i=4$;
- tốc độ phản ứng $\rho=0{,}2$;
- tổng điểm $\pi_i=30$;
- số lần dùng $n_i=5$.

Khi đó:

$$
w_i\leftarrow(1-0{,}2)\times4+0{,}2\times\frac{30}{5}=4{,}4
$$

**Diễn giải bằng lời:** hiệu quả gần đây của toán tử là 6 điểm mỗi lần, cao hơn trọng số cũ 4, nên trọng số tăng từ 4 lên 4,4.

---

## 16. Một vòng ALNS hoàn chỉnh bằng số

Giả sử lời giải hiện tại là:

```text
UAV A: 0 → 1 → 4 → 2 → 0
UAV B: 0 → 5 → 3 → 6 → 0
F(S) = 128,0
```

Lời giải tốt nhất đang lưu cũng là $S$, nên $F(S^*)=128{,}0$.

### Bước 1: chọn toán tử

Roulette wheel chọn:

- destroy: Related removal;
- repair: Regret-2 insertion.

### Bước 2: destroy

Related removal chọn nhiệm vụ 6 làm hạt giống và nhận thấy nhiệm vụ 3 có liên quan. Nó tháo hai nhiệm vụ:

```text
UAV A: 0 → 1 → 4 → 2 → 0
UAV B: 0 → 5 → 0
U = {3, 6}
```

### Bước 3: repair

Giả sử các chi phí chèn tốt nhất và tốt thứ hai là:

| Nhiệm vụ | $c_1$ | $c_2$ | Regret-2 |
|---|---:|---:|---:|
| 3 | 4 | 7 | $7-4=3$ |
| 6 | 3 | 15 | $15-3=12$ |

Nhiệm vụ 6 có regret lớn hơn, nên được chèn trước vào vị trí tốt nhất. Sau đó chèn nhiệm vụ 3.

Ứng viên thu được:

```text
UAV A: 0 → 1 → 3 → 4 → 2 → 0
UAV B: 0 → 5 → 6 → 0
F(S') = 119,5
```

### Bước 4: đánh giá

$$
\Delta=F(S')-F(S)=119{,}5-128{,}0=-8{,}5
$$

**Diễn giải bằng lời:** ứng viên giảm chi phí 8,5 đơn vị, nên tốt hơn lời giải hiện tại.

### Bước 5: chấp nhận và cập nhật best

Vì $\Delta<0$, ta luôn chấp nhận:

```text
S ← S'
```

Vì $119{,}5<128{,}0$, ta cũng cập nhật:

```text
S* ← S'
```

### Bước 6: thưởng toán tử

Vì cặp operator tạo ra best-so-far, cả Related removal và Regret-2 nhận mức thưởng cao nhất $\sigma_1$.

### Bước 7: làm nguội

Nếu $T=20$ và $c=0{,}95$:

$$
T\leftarrow0{,}95\times20=19
$$

**Diễn giải bằng lời:** nhiệt độ giảm từ 20 xuống 19, rồi thuật toán bắt đầu vòng tiếp theo.

---

## 17. Pseudocode ALNS có chú thích

```text
Input:
    instance       dữ liệu bài toán
    time_limit     thời gian chạy tối đa

S ← BuildInitialSolution(instance)
S_best ← Copy(S)

khởi tạo cùng trọng số cho mọi destroy operator
khởi tạo cùng trọng số cho mọi repair operator
khởi tạo nhiệt độ T

while chưa hết time_limit:
    d ← chọn một destroy operator theo trọng số
    r ← chọn một repair operator theo trọng số
    q ← chọn số nhiệm vụ cần tháo

    (S_partial, U) ← d(S, q)
    S_candidate ← r(S_partial, U)

    tính F(S_candidate)

    if S_candidate khả thi và Accept(S_candidate, S, T):
        S ← S_candidate

        if F(S) < F(S_best):
            S_best ← Copy(S)
            thưởng mức cao nhất cho d và r
        else if S cải thiện lời giải hiện tại trước đó:
            thưởng mức trung bình cho d và r
        else:
            thưởng mức nhỏ cho d và r
    else:
        không thưởng hoặc thưởng 0

    định kỳ cập nhật trọng số destroy và repair
    T ← cooling_rate × T

return S_best
```

Hai chi tiết dễ cài đặt sai:

1. Phải **sao chép** lời giải khi tạo ứng viên; nếu sửa trực tiếp $S$, ta có thể không khôi phục được lời giải khi ứng viên bị từ chối.
2. Phải lưu $S^*$ riêng; việc chấp nhận một lời giải tệ hơn chỉ thay đổi $S$, không được làm mất best-so-far.

---

## 18. Áp dụng ALNS vào môi trường động bằng rolling horizon

ALNS ở trên giải một ảnh chụp tĩnh của bài toán. Đề tài lại có chữ **Dynamic**, nghĩa là dữ liệu có thể thay đổi khi UAV đang hoạt động.

Các sự kiện động có thể gồm:

- xuất hiện nhiệm vụ mới;
- nhiệm vụ bị hủy;
- deadline thay đổi;
- risk map thay đổi;
- gió thay đổi;
- pin thực tế giảm nhanh hơn dự kiến;
- UAV hỏng hoặc mất liên lạc.

### 18.1. Rolling horizon là gì?

Rolling horizon có thể hiểu là **lập kế hoạch trên một cửa sổ thời gian trượt**:

1. lập kế hoạch cho tương lai gần;
2. thực hiện một phần kế hoạch;
3. nhận dữ liệu mới;
4. cố định phần đã thực hiện;
5. tái tối ưu phần còn lại;
6. tiếp tục lặp.

Ta chia tuyến của UAV $k$ thành:

$$
R_k=R_k^{\text{fixed}}\oplus R_k^{\text{future}}
$$

Trong đó:

- $R_k$ là toàn bộ tuyến của UAV $k$;
- $R_k^{\text{fixed}}$ là phần đã bay hoặc sắp thực hiện ngay, không được phép thay đổi;
- $R_k^{\text{future}}$ là phần tương lai còn có thể tối ưu;
- ký hiệu $\oplus$ ở đây nghĩa là nối hai chuỗi tuyến theo thứ tự.

**Diễn giải bằng lời:** toàn bộ tuyến bằng phần đã khóa nối với phần tương lai còn được sửa.

Destroy operator chỉ được tháo nhiệm vụ trong $R_k^{\text{future}}$, không được “sửa lịch sử”.

### 18.2. Khi nào kích hoạt tái tối ưu?

Có ba cách thường dùng:

- **theo chu kỳ:** cứ mỗi 30 giây hoặc 1 phút chạy lại;
- **theo sự kiện:** chạy khi có nhiệm vụ mới, UAV lỗi hoặc risk map đổi mạnh;
- **kết hợp:** chạy định kỳ và chạy ngay khi có sự kiện quan trọng.

Trong hệ thống online, điều kiện dừng ALNS thường là một ngân sách thời gian ngắn, ví dụ 0,5 giây hoặc 2 giây, thay vì hàng chục nghìn vòng lặp cố định.

### 18.3. Warm start

Khi môi trường thay đổi, không nhất thiết xây lời giải từ đầu. Ta dùng kế hoạch cũ còn hợp lệ làm lời giải ban đầu mới. Cách này gọi là **warm start**.

Quy trình:

1. giữ phần tuyến đã khóa;
2. xóa nhiệm vụ bị hủy;
3. đưa nhiệm vụ mới vào tập chưa gán;
4. cập nhật thời gian, năng lượng và chi phí rủi ro;
5. repair để có lời giải khả thi;
6. chạy ALNS trong ngân sách thời gian cho phép.

Warm start thường nhanh và làm kế hoạch ít thay đổi đột ngột hơn.

### 18.4. Phạt việc thay đổi kế hoạch quá nhiều

Nếu mỗi lần cập nhật đều đảo toàn bộ tuyến, người vận hành và hệ thống điều khiển khó theo dõi. Có thể thêm chi phí bất ổn:

$$
C_{\text{change}}(S,S_{\text{old}})=
\sum_{i\in N_{\text{active}}}
\mathbf{1}[\operatorname{pred}_S(i)\ne\operatorname{pred}_{S_{\text{old}}}(i)]
$$

Trong đó:

- $S_{\text{old}}$ là kế hoạch trước sự kiện;
- $S$ là kế hoạch mới;
- $N_{\text{active}}$ là tập nhiệm vụ chưa hoàn thành;
- $\operatorname{pred}_S(i)$ là nhiệm vụ đứng ngay trước $i$ trong kế hoạch $S$;
- $\mathbf{1}[\cdot]$ bằng 1 nếu điều kiện bên trong đúng và bằng 0 nếu sai;
- $C_{\text{change}}$ đếm số quan hệ trước–sau đã bị thay đổi.

**Diễn giải bằng lời:** mỗi nhiệm vụ bị đổi người đứng trước nó đóng góp một đơn vị vào chi phí thay đổi; kế hoạch mới càng khác kế hoạch cũ thì bị phạt càng nhiều.

Sau đó thêm $\kappa C_{\text{change}}$ vào hàm mục tiêu, trong đó $\kappa$ là trọng số ổn định kế hoạch.

---

## 19. Khởi tạo tham số như thế nào?

Không có một bộ tham số tốt cho mọi bộ dữ liệu. Các giá trị dưới đây là điểm bắt đầu để thử nghiệm, không phải đáp án cố định.

| Tham số | Ý nghĩa | Điểm bắt đầu có thể thử |
|---|---|---|
| $\eta$ | tỷ lệ nhiệm vụ bị destroy | 0,1 đến 0,3 |
| $c$ | hệ số làm nguội | 0,995 đến 0,9999 |
| $\rho$ | tốc độ cập nhật trọng số | 0,1 đến 0,3 |
| segment length | số vòng giữa hai lần cập nhật trọng số | 50 đến 200 |
| $\sigma_1$ | thưởng best-so-far | 10 hoặc 20 |
| $\sigma_2$ | thưởng cải thiện hiện tại | 5 hoặc 10 |
| $\sigma_3$ | thưởng ứng viên được nhận | 1 hoặc 2 |

### 19.1. Chọn nhiệt độ ban đầu có ý nghĩa

Thay vì đoán $T_0$, ta có thể muốn một lời giải tệ hơn $\Delta_0$ đơn vị được nhận với xác suất ban đầu $p_0$. Từ:

$$
p_0=\exp\left(-\frac{\Delta_0}{T_0}\right)
$$

**Diễn giải bằng lời:** tại nhiệt độ ban đầu $T_0$, một ứng viên tệ hơn $\Delta_0$ đơn vị có xác suất $p_0$ được chấp nhận.

suy ra:

$$
T_0=-\frac{\Delta_0}{\ln(p_0)}
$$

Trong đó:

- $T_0$ là nhiệt độ ban đầu;
- $\Delta_0$ là mức xấu đi tiêu biểu mà ta vẫn muốn đôi khi chấp nhận;
- $p_0$ là xác suất chấp nhận mong muốn, nằm giữa 0 và 1;
- $\ln$ là logarit tự nhiên.

**Diễn giải bằng lời:** chọn trước một mức xấu đi tiêu biểu và xác suất muốn chấp nhận nó, rồi tính nhiệt độ tương ứng.

Ví dụ muốn ứng viên tệ hơn 5 đơn vị có xác suất nhận 0,5 ở đầu quá trình:

$$
T_0=-\frac{5}{\ln(0{,}5)}\approx7{,}21
$$

**Diễn giải bằng lời:** đặt nhiệt độ ban đầu khoảng 7,21 sẽ cho ứng viên tệ hơn 5 đơn vị cơ hội được nhận khoảng 50%.

---

## 20. Điều kiện dừng

Có thể dừng khi đạt một trong các điều kiện:

- đủ số vòng lặp;
- hết thời gian;
- đã có quá nhiều vòng không cải thiện best-so-far;
- nhiệt độ xuống dưới ngưỡng;
- hệ thống phát sinh sự kiện mới và cần bắt đầu một lần tái tối ưu khác.

Trong nghiên cứu so sánh thuật toán, điều kiện dừng phải công bằng. Ví dụ, cho mọi thuật toán cùng thời gian CPU trên cùng máy hoặc cùng số lần đánh giá hàm mục tiêu.

---

## 21. Độ phức tạp: bước nào tốn thời gian?

Gọi:

- $n$ là số nhiệm vụ;
- $m$ là số UAV;
- $q$ là số nhiệm vụ bị tháo;
- mỗi tuyến trung bình có khoảng $n/m$ nhiệm vụ.

Nếu với mỗi nhiệm vụ chưa gán ta thử khoảng $n+m$ vị trí trên tất cả tuyến, một lượt greedy repair thô có thể cần khoảng:

$$
O(q(n+m))
$$

Trong đó $O(\cdot)$ mô tả tốc độ tăng của lượng công việc khi kích thước đầu vào tăng.

**Diễn giải bằng lời:** có $q$ nhiệm vụ cần chèn, và mỗi nhiệm vụ thử một số vị trí tỷ lệ với tổng số nhiệm vụ cùng số UAV.

Nếu sau mỗi phép thử ta tính lại toàn bộ tuyến với chi phí $O(n)$, tổng chi phí có thể tăng thành gần:

$$
O(qn(n+m))
$$

**Diễn giải bằng lời:** việc tính lại cả tuyến cho từng vị trí tạo thêm một thừa số $n$, khiến repair chậm đáng kể.

Vì vậy khi cài đặt nên:

- tính gia tăng chi phí thay vì tính lại toàn bộ lời giải;
- chỉ cập nhật thời gian từ vị trí bị chèn trở về sau;
- lưu trước ma trận khoảng cách, thời gian và rủi ro;
- dừng sớm khi pin hoặc deadline chắc chắn bị vi phạm;
- chỉ xét một danh sách vị trí ứng viên hợp lý nếu dữ liệu lớn.

Phân tích trên là ước lượng để hiểu nút thắt; độ phức tạp chính xác phụ thuộc cách biểu diễn và kiểm tra ràng buộc.

---

## 22. Cấu trúc chương trình gợi ý

Một cách tách mô-đun rõ ràng:

```text
ProblemInstance
├── tasks
├── UAVs
├── distance/time/risk matrices
└── global settings

Solution
├── routes
├── unassigned tasks
├── cached cost
└── feasibility information

Evaluation
├── compute_objective
├── check_time_windows
├── check_battery
└── check_capacity

DestroyOperators
├── random_removal
├── worst_removal
├── related_removal
└── risk_priority_removal

RepairOperators
├── greedy_insertion
├── regret2_insertion
├── risk_priority_insertion
└── feasibility_repair

ALNS
├── operator selection
├── acceptance criterion
├── adaptive weights
├── temperature schedule
└── stopping condition

DynamicController
├── event handling
├── frozen route prefix
├── warm start
└── rolling-horizon reoptimization
```

Mục đích của việc tách này là có thể kiểm thử từng phần độc lập và thay operator mà không sửa toàn bộ chương trình.

---

## 23. Các kiểm thử nhỏ nên viết trước

Trước khi chạy benchmark lớn, nên kiểm tra các trường hợp nhỏ có thể tính tay:

1. Chèn một nhiệm vụ vào một tuyến và kiểm tra $\Delta D$.
2. Tháo một nhiệm vụ rồi xác nhận nó xuất hiện đúng một lần trong tập chưa gán.
3. Repair xong, xác nhận không mất hoặc lặp nhiệm vụ.
4. Một tuyến vừa đủ pin phải khả thi; vượt một lượng nhỏ phải bị từ chối.
5. UAV đến sớm phải chờ đúng thời gian.
6. UAV đến sau deadline cứng phải bị từ chối.
7. Với seed ngẫu nhiên cố định, chương trình phải tái tạo cùng kết quả.
8. Ứng viên bị từ chối không được làm thay đổi lời giải hiện tại.
9. Nhận lời giải tệ hơn không được ghi đè best-so-far.
10. Destroy không được tháo phần tuyến đã khóa trong rolling horizon.

---

## 24. Những lỗi hiểu và lỗi cài đặt thường gặp

### Lỗi 1: nghĩ ALNS là một thuật toán duy nhất có công thức cố định

ALNS là một **khung thuật toán**. Destroy, repair, objective, acceptance và cách thích nghi phải được thiết kế cho bài toán.

### Lỗi 2: nhầm lời giải hiện tại với lời giải tốt nhất

$S$ có thể tạm thời xấu đi để khám phá. $S^*$ luôn giữ kỷ lục tốt nhất.

### Lỗi 3: chỉ tối ưu quãng đường rồi gọi là risk-aware

Nếu rủi ro không xuất hiện trong objective, ràng buộc hoặc operator, thuật toán chưa thật sự nhận biết rủi ro.

### Lỗi 4: penalty quá nhỏ hoặc quá lớn

- quá nhỏ: lời giải vi phạm lại trông hấp dẫn;
- quá lớn: các thành phần khác gần như mất tác dụng và việc tìm kiếm thiếu mềm dẻo.

Nên chuẩn hóa các thành phần và báo cáo sensitivity của penalty.

### Lỗi 5: không kiểm tra khả thi sau mỗi phép chèn

Một vị trí có quãng đường tăng ít nhất vẫn có thể làm hỏng deadline hoặc pin của nhiều nhiệm vụ đứng sau.

### Lỗi 6: mọi operator gần như giống nhau

Nếu các destroy đều chọn gần cùng một nhóm nhiệm vụ, cơ chế adaptive không có nhiều lựa chọn thực sự để học.

### Lỗi 7: báo cáo một lần chạy duy nhất

ALNS có yếu tố ngẫu nhiên. Cần chạy nhiều seed và báo cáo trung bình, độ lệch, best, thời gian, tỷ lệ khả thi và kiểm định thống kê phù hợp.

### Lỗi 8: tối ưu lại cả phần đã thực hiện

Trong bài toán động, phần quá khứ và đoạn cam kết sắp thực hiện phải được khóa.

---

## 25. ALNS cơ bản và đóng góp nghiên cứu của đề tài

Một baseline ALNS hợp lý có thể gồm:

- random, worst và related removal;
- greedy và regret-2 insertion;
- simulated annealing acceptance;
- adaptive operator weights;
- objective gồm distance, tardiness và penalty;
- kiểm tra capacity, time window và battery.

Sau đó có thể đề xuất cơ chế mới cho đề tài:

1. **Risk-priority destroy:** ưu tiên tháo các nhiệm vụ rủi ro cao đang được phục vụ kém.
2. **Risk-priority repair:** đưa nhiệm vụ khẩn cấp vào vị trí an toàn và đúng hạn sớm hơn.
3. **Event-aware operator selection:** sau từng loại sự kiện, ưu tiên nhóm operator phù hợp.
4. **Stability-aware objective:** hạn chế thay đổi kế hoạch không cần thiết.
5. **Adaptive destroy size:** tăng $q$ khi lâu không cải thiện, giảm $q$ khi đang tinh chỉnh tốt.
6. **Rolling-horizon warm start:** tận dụng kế hoạch cũ để tái tối ưu nhanh.

Để chứng minh cơ chế mới có ích, cần **ablation study**:

- baseline ALNS;
- baseline + risk destroy;
- baseline + risk repair;
- baseline + cả hai;
- so sánh objective, risk, tardiness, runtime, feasibility và độ ổn định qua nhiều seed.

---

## 26. Tóm tắt ALNS trong một phút

ALNS giải bài toán lớn bằng cách không cố duyệt mọi phương án.

1. Tạo một lời giải ban đầu $S$.
2. Chọn một cách destroy theo trọng số.
3. Tháo $q$ nhiệm vụ khỏi $S$.
4. Chọn một cách repair theo trọng số.
5. Chèn các nhiệm vụ trở lại để tạo $S'$.
6. Tính $F(S')$ và kiểm tra ràng buộc.
7. Nhận lời giải tốt hơn; đôi khi nhận lời giải tệ hơn để thoát bẫy.
8. Cập nhật lời giải tốt nhất $S^*$.
9. Thưởng cho operator hoạt động tốt và điều chỉnh trọng số.
10. Giảm nhiệt độ rồi lặp lại.
11. Khi môi trường thay đổi, khóa phần đã thực hiện và chạy lại ALNS trên phần tương lai.

Ba ý quan trọng nhất:

- **Large neighborhood:** tháo nhiều nhiệm vụ giúp thay đổi cấu trúc lớn.
- **Adaptive:** operator hiệu quả được tăng cơ hội sử dụng.
- **Acceptance:** đôi lúc đi lùi có kiểm soát để tìm được vùng tốt hơn.

---

## 27. Bảng tra nhanh ký hiệu

| Ký hiệu | Ý nghĩa |
|---|---|
| $S$ | lời giải hiện tại |
| $S'$ | lời giải ứng viên |
| $S^*$ | lời giải tốt nhất đã tìm thấy |
| $S_0$ | lời giải ban đầu |
| $F(S)$ | tổng chi phí của lời giải $S$ |
| $D(S)$ | tổng quãng đường |
| $E(S)$ | tổng phơi nhiễm rủi ro |
| $L(S)$ | tổng độ trễ |
| $U(S)$ | chi phí nhiệm vụ chưa phục vụ |
| $V(S)$ | mức vi phạm ràng buộc |
| $N$ | tập nhiệm vụ |
| $K$ | tập UAV |
| $R_k$ | tuyến hoặc tập chặng/nhiệm vụ của UAV $k$, tùy ngữ cảnh được nêu |
| $d_{ij}$ | khoảng cách từ điểm $i$ đến điểm $j$ |
| $t_{ij}$ | thời gian bay từ $i$ đến điểm $j$ |
| $e_{ij}$ | mức phơi nhiễm rủi ro trên chặng $i\rightarrow j$ |
| $a_i$ | thời điểm UAV đến hoặc bắt đầu phục vụ nhiệm vụ $i$ |
| $b_i$ | hạn muộn nhất của nhiệm vụ $i$ |
| $\ell_i$ | độ trễ của nhiệm vụ $i$ |
| $q$ | số nhiệm vụ được destroy trong một vòng |
| $U$ | tập nhiệm vụ tạm thời chưa gán |
| $\Delta F$ | lượng thay đổi của hàm mục tiêu |
| $T$ | nhiệt độ của simulated annealing |
| $c$ | hệ số làm nguội |
| $w_i$ | trọng số của operator $i$ |
| $\rho$ | tốc độ phản ứng khi cập nhật trọng số |
| $\pi_i$ | tổng điểm operator $i$ nhận được |
| $n_i$ | số lần operator $i$ được dùng |
| $\alpha,\beta,\gamma,\delta$ | trọng số các thành phần objective |
| $M$ | hệ số phạt vi phạm lớn |

---

## 28. Nên học và triển khai tiếp theo theo thứ tự nào?

Nếu bắt đầu cài đặt từ con số 0, thứ tự an toàn là:

1. Đọc và hiển thị được một instance Solomon nhỏ.
2. Xây cấu trúc `Solution` và kiểm tra mỗi nhiệm vụ đúng một lần.
3. Cài tính distance, arrival time, tardiness và battery.
4. Cài greedy để tạo lời giải ban đầu khả thi.
5. Cài random removal + greedy insertion.
6. Thêm best-so-far và điều kiện dừng.
7. Thêm SA acceptance.
8. Thêm worst/related removal và regret-2 insertion.
9. Thêm trọng số adaptive.
10. Đo runtime và viết test.
11. Thêm risk vào dữ liệu, objective và operator.
12. Cuối cùng thêm sự kiện động, frozen prefix và rolling horizon.

Làm theo thứ tự này giúp luôn có một phiên bản nhỏ chạy được để so sánh, thay vì cài mọi cơ chế cùng lúc rồi khó xác định lỗi nằm ở đâu.

---

## Kết luận

ALNS không hứa tìm nghiệm tối ưu tuyệt đối, nhưng nó là một lựa chọn mạnh cho bài toán định tuyến lớn, nhiều ràng buộc và cần phản ứng nhanh. Cốt lõi của nó rất trực quan: **phá một phần kế hoạch, xây lại theo cách thông minh, đôi khi chấp nhận bước lùi, và học xem cách phá–sửa nào đang hiệu quả**.

Trong đề tài Dynamic risk-aware multi-UAV routing, phần có giá trị nghiên cứu không chỉ là “dùng ALNS”, mà là thiết kế được:

- hàm mục tiêu phản ánh đúng quãng đường, rủi ro, deadline và pin;
- destroy/repair hiểu đặc thù rủi ro;
- cơ chế tái tối ưu nhanh khi có sự kiện động;
- thực nghiệm đủ chặt chẽ để chứng minh từng cải tiến thực sự có tác dụng.

Tài liệu minh họa tương tác đi kèm: [`alns_visual_guide.html`](./alns_visual_guide.html).

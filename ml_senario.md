# Cấu hình 1 Cấu hình 2 Cấu hình 3 Cấu hình 4 Cấu hình 5

**Chia theo language_group**

```
Stratified Within Group (Baseline 70–15–15)
Trong từng language_group (backend, fullstack, scripting, other) chia:
70% → Train 15% → Val 15% → Test
Bên trong mỗi nhóm chia stratified theo out_come
=> Dữ liệu ở cả 3 tập đều có đủ 4 nhóm và tỷ lệ nhãn gần như giữ nguyên.
```
```
Leave-One-Language-Group-Out
Mỗi lần chọn 1 nhóm làm Test, 1 nhóm khác làm Val,
2 nhóm còn lại làm Train.
Test=other, Val=scripting, Train=backend+fullstack
=> Đánh giá khả năng mô hình dự đoán
khi gặp nhóm ngôn ngữ hoàn toàn mới.
```
```
Leave-Two-Language-Groups-Out
Chọn 2 nhóm làm Test, 1 nhóm làm Val, 1 nhóm làm Train.
Test=scripting+other, Val=fullstack, Train=backend.
=> Stress test hơn kịch bản 2, khi test chứa nhiều nhóm chưa từng thấy.
```
```
Imbalanced Train, Balanced Test
Train mất cân bằng nhãn trong từng nhóm
(giảm 50% mẫu nhãn 1).
Val và Test giữ phân phối ban đầu.
Tỷ lệ vẫn 70–15–15 trong từng nhóm.
=> Kiểm tra tác động của mất cân bằng dữ liệu
tới dự đoán và uncertainty.
```
```
Extreme Novelty in Sub-Group
Trong 1 language_group, chọn toàn bộ mẫu của một nhãn để đưa vào Test.
Phần còn lại của nhóm đó + các nhóm khác chia Train/Val theo 70–15.
Toàn bộ scripting với nhãn 1 → Test, còn lại chia bình thường.
=> Kiểm tra khả năng nhận biết rủi ro khi gặp kết hợp “ngôn ngữ + nhãn” chưa từng thấy.
```
**Chia theo percentage_of_builds_before,
number_of_builds_before**

```
Chia percentage_of_builds_before thành 4 phần, mỗi phần rộng 25%.
Đối với number_of_builds_before tìm giá trị min, max rồi chia làm 4 phần bằng nhau
70% → Train 15% → Val 15% → Test
Bên trong mỗi nhóm chia stratified theo out_come
```
```
Chia percentage_of_builds_before thành 4 phần, mỗi phần rộng 25%.
Đối với number_of_builds_before tìm giá trị min, max rồi chia làm 4 phần bằng nhau
70% → Train 15% → Val 15% → Test
1 nhóm dùng để test, 1 nhóm để val, 2 nhóm để train
```
```
Chia percentage_of_builds_before thành 4 phần, mỗi phần rộng 25%.
Đối với number_of_builds_before tìm giá trị min, max rồi chia làm 4 phần bằng nhau
70% → Train 15% → Val 15% → Test
2 nhóm dùng để test, 1 nhóm để val, 1 nhóm để train
```
```
Chia percentage_of_builds_before thành 4 phần, mỗi phần rộng 25%.
Đối với number_of_builds_before tìm giá trị min, max rồi chia làm 4 phần bằng nhau
(giảm 50% mẫu nhãn 1).
Val và Test giữ phân phối ban đầu.
Tỷ lệ vẫn 70–15–15 trong từng nhóm.
```
```
Chia percentage_of_builds_before thành 4 phần, mỗi phần rộng 25%.
Đối với number_of_builds_before tìm giá trị min, max rồi chia làm 4 phần bằng nhau
```
```
Trong 1 nhóm, chọn toàn bộ mẫu của một nhãn để đưa vào Test.
Phần còn lại của nhóm đó + các nhóm khác chia Train/Val theo 70–15.
Toàn bộ data của 1 nhóm với nhãn 1 → Test, còn lại chia bình thường.
```
**Chia theo time_of_day**

```
Chia time_of_day (0–23) thành 4 nhóm
(0–5),(6–11),(12–17),(18–23)
Trong mỗi nhóm: 70% → Train, 15% → Val, 15% → Test,
chia ngẫu nhiên và stratified theo nhãn là out_come
```
```
Chia time_of_day (0–23) thành 4 nhóm
(0–5),(6–11),(12–17),(18–23)
1 nhóm dùng để test, 1 nhóm để val, 2 nhóm để train
```
```
Chia time_of_day (0–23) thành 4 nhóm
(0–5),(6–11),(12–17),(18–23)
2 nhóm dùng để test, 1 nhóm để val, 1 nhóm để train
```
```
Chia time_of_day (0–23) thành 4 nhóm
(0–5),(6–11),(12–17),(18–23)
(giảm 50% mẫu nhãn 1).
Val và Test giữ phân phối ban đầu.
Tỷ lệ vẫn 70–15–15 trong từng nhóm.
```
```
Chia time_of_day (0–23) thành 4 nhóm
(0–5),(6–11),(12–17),(18–23)
Trong 1 nhóm, chọn toàn bộ mẫu của một nhãn để đưa vào Test.
Phần còn lại của nhóm đó + các nhóm khác chia Train/Val theo 70–15.
Toàn bộ data của 1 nhóm với nhãn 1 → Test, còn lại chia bình thường.
```


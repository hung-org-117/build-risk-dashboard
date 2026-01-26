# Kịch bản Bảo vệ Đồ án Tốt nghiệp

**Đề tài:** Hệ thống đánh giá rủi ro Build trong CI/CD có nhận thức độ bất định  
**(Uncertainty-Aware CI/CD Build Risk Evaluation System)**  
**Sinh viên:** Lại Thế Hùng  
**MSSV:** 20205155

---

## PHẦN 1: MỞ ĐẦU (Giới thiệu & Đặt vấn đề)
*(Dựa trên Chapter 1: Introduction)*

**Slide 1: Trang bìa & Giới thiệu**
> "Kính thưa Thầy/Cô chủ tịch hội đồng, thưa các thầy cô và các bạn. Em là Lại Thế Hùng.
> Hôm nay em xin phép được trình bày đồ án tốt nghiệp với đề tài: **'Xây dựng hệ thống đánh giá rủi ro trong quy trình CI/CD có khả năng nhận thức sự không chắc chắn'**."

**Slide 2: Đặt vấn đề - Chi phí khắc phục lỗi**
Trong thế giới hiện đại ngày nay, quy trình CI/CD được xem là nền tảng không thể thiếu của việc phát triển phần mềm. Tuy nhiên, mặc dù mang lại tốc độ phát triển vượt bậc, nhưng đi kèm với nó là một thực tế tốn kém cần phải nhìn nhận:
Các nghiên cứu từ NIST và IBM đã chỉ ra rằng, chi phí để sửa một lỗi phần mềm ở giai đoạn Production có thể cao gấp 100 lần so với việc phát hiện sớm nó ngay từ lúc build.
=> Điều này đặt ra nhu cầu cấp thiết về việc phát hiện rủi ro tiềm ẩn càng sớm càng tốt."

**Slide 6: DORA Metrics và Tỷ lệ lỗi thay đổi (CFR)**
Tuy nhiên, duy trì sự ổn định lại là một thách thức hoàn toàn khác. Ở đây, ta có thước đo quan trọng nhất là Change Failure Rate (CFR) - tỷ lệ phần trăm các lần triển khai gây lỗi trên Production.

Dữ liệu từ báo cáo 'State of DevOps 2024' của DORA cho thấy một thực tế đáng suy ngẫm: Ngay cả những tổ chức ưu tú nhất (Elite performers) cũng phải đối mặt với tỷ lệ lỗi khoảng 10%. Với các tổ chức thấp hơn, con số này thường vượt quá 20%.
> Nguyên nhân sâu xa là việc phụ thuộc nhiều vào tín hiệu nhị phân **Pass/Fail** từ các công cụ CI truyền thống. Một bản build có thể 'Pass' (biên dịch thành công) nhưng vẫn chứa lỗ hổng hoặc nợ kỹ thuật, dẫn đến lọt lỗi ra production.
Hơn nữa, quy trình này thiếu khả năng 'đánh giá ngữ cảnh'. Nó bỏ qua lịch sử sửa đổi code (churn) hay rủi ro từ việc các thành viên mới chưa quen dự án - những yếu tố có thể gây ra rủi ro.

**Slide: Thách thức - Sự phân mảnh dữ liệu Build (Build Data Fragmentation)**
> "Một rào cản lớn khác là sự phân mảnh dữ liệu của chính các bản Build.
> *   **Về mặt vận hành:** Thông tin của một bản Build không nằm tập trung mà bị chia cắt. Trạng thái và Log nằm trên CI Server (như GitHub Actions), Mã nguồn thay đổi nằm trên Git, trong khi các chỉ số chất lượng và bảo mật lại nằm trên các công cụ riêng biệt (như SonarQube). Việc thiếu một thể thống nhất khiến việc đánh giá rủi ro cho từng lần Build khó khăn hơn.
> *   **Về mặt nghiên cứu:** Các bộ dữ liệu Build hiện có (như TravisTorrent) thường chỉ chứa metadata cơ bản và là các "ảnh tĩnh" không còn cập nhật. Cộng đồng hiện đang thiếu các **quy trình làm giàu dữ liệu (Data Enrichment Pipeline)** chuẩn hóa và có khả năng tái lập. Chính sự thiếu hụt này khiến việc tự động tổng hợp Log, thông tin metadata của commit và kết quả phân tích tĩnh để huấn luyện mô hình trở nên khó khăn và thiếu nhất quán.

**Slide: Mục tiêu & Đối tượng nghiên cứu (Scope & Objectives)**
*(Dựa trên Chapter 1, Section 1.2)*
> "Để giải quyết các thách thức trên, đồ án xác định 3 Mục tiêu cốt lõi:
> 1.  **Xây dựng hệ thống làm giàu dữ liệu:** Tự động thu thập và làm giàu dữ liệu từ các nguồn không đồng nhất (CI/CD, Source Code trong qua công cụ quản lý phiên bản như git, báo cáo chất lượng thu thập được trên các công cụ riêng biệt).
> 2.  **Tích hợp mô hình Bayesian Deep Learning:** Đánh giá rủi ro build không chỉ dừng lại ở phân loại (Low/Medium/High) mà phải cung cấp **độ bất định (Uncertainty)** để hỗ trợ người dùng ra quyết định tin cậy hơn.
> 3.  **Xây dựng hệ thống:** Đáp ứng cả hai nhu cầu: Vận hành (Real-time monitoring) và Nghiên cứu (Dataset export engine).
>
> **Đối tượng nghiên cứu:** Các dự án mã nguồn mở trên **GitHub**, sử dụng **GitHub Actions, Travis CI, hoặc CircleCI**.
> **Phạm vi dữ liệu:** Build Logs, Commit Metadata, và báo cáo phân tích tĩnh (SonarQube, Trivy)."

---

## PHẦN 2: CƠ SỞ CÔNG NGHỆ (Vắn tắt)
*(Dựa trên Chapter 3 & 4)*

**Slide: Kiến trúc Hệ thống Tổng quan (System Overview)**
> "Hệ thống của em - **Hệ thống đánh giá rủi ro CI/CD có khả năng nhận thức sự bất định** - được vận hành dựa trên hai quy trình nghiệp vụ chính:
>
> **1. Quy trình Đánh giá Rủi ro các bản dựng:**
> *Dành cho Vận hành (Operations)*
> *   **Quản lý kết nối:** Quản lý kết nối các Github repositories cùng với các config cần được định nghĩa sẵn trước khi bắt đầu thu thập dữ liệu và đánh giá rủi ro.
> *   **Thu thập dữ liệu:** Tự động cập nhật bằng tay hay tự động lắng nghe Webhook để thu thập dữ liệu bản dựng và tài nguyên cần thiết ngay khi sự kiện xảy ra.
> *   **Trích xuất đặc trưng:** Xử lý nhanh dữ liệu thô và trích xuất các đặc trưng phù hợp phục vụ cho quá trình dự đoán.
> *   **Dự báo lõi:** Chạy mô hình dự báo dựa trên kiến trúc **Dual-Branch** để đưa ra kết luận cuối cùng về **Rủi ro (Risk)** và **Độ bất định (Uncertainty)**.
>
> **2. Quy trình Làm giàu Dữ liệu:**
> *Dành cho Nghiên cứu (Research)*
> *   **Mở rộng kho dữ liệu:** Cho phép Admin tải lên tập CSV định danh bản dựng để mở rộng không giới hạn phạm vi thu thập.
> *   **Lọc & Tuyển chọn:** Lọc các bản dựng đầu vào theo tiêu chí (Ngôn ngữ, Thời gian).
> *   **Xử lý chuyên sâu:** Trích xuất hơn **70+ đặc trưng** phức tạp thông qua đồ thị **Hamilton DAG**, kết hợp quét toàn diện chất lượng code (**SonarQube**) và bảo mật (**Trivy**).
> *   **Kiểm soát & Xuất bản:** Hệ thống tự động phân tích chất lượng dữ liệu trước khi cung cấp các chiến lược xuất dataset linh hoạt (như Stratified Split hay Time-series Split) phục vụ huấn luyện mô hình."

*(Dựa trên Chapter 3, Mục 3.8: Dual-Branch Model Architecture)*

**Slide: Kiến trúc Mô hình Dual-Branch**
> "Tiếp theo, để hiện thực hoá hệ thống dự báo rủi ro: **Kiến trúc Dual-Branch Model** (Mô hình nhánh kép). Đây là kiến trúc được định hướng bởi Giáo viên hướng dẫn, được thiết kế để tổng hợp 4 luồng dữ liệu (Artifact Streams) gồm: **Source Code**, **Test**, **Team**, và **Monitoring**.
>
> Kiến trúc này ánh xạ dữ liệu vào 2 nhánh xử lý chuyên biệt:
> *   **Nhánh 1 - Temporal Branch (Risk Evolution):** Sử dụng mạng **Long Short-Term Memory (LSTM) + Attention**. Nhánh này quan sát một *chuỗi thời gian* n bản builds liên tiếp để học "quỹ đạo" tiến hóa của dự án (như xu hướng lỗi tích lũy).
> *   **Nhánh 2 - Synergy Branch (Cross-Artifact Interaction):** Sử dụng mạng **Bayesian MLP**. Nhánh này phân tích một sự kết hợp đặc điểm của bản build hiện tại để tìm ra sự tương tác rủi ro phức tạp (ví dụ: Bản build của committer mới thực hiện nhiều thay đổi code).
>
> **Uncertainty-Weighted Fusion:** Cuối cùng, kết quả từ hai nhánh sẽ được hợp nhất thông qua cơ chế **Uncertainty-Weighted Fusion**. Bằng cách áp dụng kỹ thuật **MC Dropout**, mỗi nhánh có thể tự đánh giá được độ bất định (tức là mức độ "lưỡng lự") của chính mình. Mô hình sau đó sẽ tự động điều chỉnh trọng số: nhánh nào có độ biến động thấp hơn - tức là "tự tin" hơn - sẽ đóng góp nhiều hơn vào quyết định cuối cùng.


## PHẦN 3: GIẢI PHÁP & ĐÓNG GÓP (Trọng tâm)
*(Dựa trên Chapter 5: Solution Contribution)*

> *"Về mặt kỹ thuật, đồ án hiện thực hóa 4 đóng góp chính, giải quyết triệt để 4 vấn đề của hệ thống:"*

**Slide: Đóng góp 1 - Nền tảng dữ liệu rủi ro đa chiều**
> "**Đóng góp 1: Xây dựng nền tảng dữ liệu đáp ứng yêu cầu Dual-Branch.**
> *   **Thách thức từ Mô hình (Model Requirements):** Kiến trúc Dual-Branch đặt ra yêu cầu dữ liệu rất khắt khe mà các dataset cũ không đáp ứng được:
>     1.  **Nhánh Temporal** cần chuỗi lịch sử liên tục của $k$ builds để học xu hướng (trong khi các dataset cũ thường rời rạc).
>     2.  **Nhánh Synergy** cần vector đa chiều (Source, Test, Team, Monitor) để học tương tác ngữ cảnh.
>     3.  **Tính chất hiện đại (Modernity):** Dataset nổi tiếng nhất là **TravisTorrent** đã ngừng cập nhật từ 2017. Nó không phản ánh được quy trình CI/CD hiện đại (như GitHub Actions), dẫn đến mô hình huấn luyện trên đó sẽ bị lỗi thời khi áp dụng vào thực tế nay.
> *   **Giải pháp Đáp ứng:** Em đã làm giàu bộ dữ liệu mới thỏa mãn chính xác các yêu cầu này thông qua:
>     *   **Nguồn dữ liệu hiện đại:** Tập trung khai phá dữ liệu từ **GitHub Actions** - CI/CD phổ biến nhất hiện nay.
>     *   **Lọc dữ liệu nghiêm ngặt:** Chỉ chọn dự án có lịch sử >2 năm + 400 builds để đảm bảo độ dài chuỗi cho LSTM.
>     *   **Làm giàu đa chiều (Enrichment):** Tự động tổng hợp 35 features từ 4 nguồn khác nhau cho mỗi bản build.
>     *   **Gán nhãn Composite Risk:** Thay vì tin vào exit code (Pass/Fail) nhị phân, hệ thống sử dụng **SonarQube** để tham chiếu "chất lượng nội tại" (gồm **Khả năng bảo trì** và **Vi phạm quy chuẩn**), tạo ra nhãn Low/Medium/High chính xác hơn.
> *   **Kết quả:** Bộ dữ liệu chuẩn hóa gồm **552,341 bản build**, là dataset đầu tiên được thiết kế *đo ni đóng giày* cho bài toán dự báo rủi ro đa nhánh."

**Slide: Đóng góp 2 - Chiến lược Rate Limiting Phân tán (Distributed Rate Limiting)**
> "**Đóng góp 2: Giải quyết bài toán thu thập dữ liệu quy mô lớn (Big Data Mining).**
> *   **Thách thức:** GitHub giới hạn ngặt nghèo **5,000 request/giờ**. Nếu vi phạm sẽ bị chặn IP, làm gián đoạn toàn bộ pipeline.
> *   **Giải pháp:** Em thiết kế thuật toán **Sliding Window with Burst Allowance** dựa trên **Redis** và **Lua Script**.
>     *   Sử dụng cơ chế **Sliding Window with Burst Allowance**: Cho phép một lượng nhỏ request vượt ngưỡng tức thời (burst) để xử lý các tác vụ ưu tiên, nhưng vẫn đảm bảo trung bình không vượt quá quota giờ.
>     *   Kết hợp **Token Rotation**: Hệ thống duy trì một "bể" (pool) các API Token được sắp xếp theo quota còn lại (Priority Queue). Hệ thống tự động switch sang token khác có quota cao nhất, đảm bảo có thể hoạt động lâu dài cho pipeline thu thập dữ liệu lớn."
> *   **Hiệu quả:** Hệ thống có thể chạy hàng chục Worker song song, quét hàng nghìn repo mỗi ngày mà không bao giờ chạm trần giới hạn."

**Slide: Đóng góp 3 - Pipeline làm giàu dữ liệu (Dataset Enrichment Pipeline)**
> "**Đóng góp 3: Pipeline làm giàu dữ liệu có khả năng tái lập (Reproducibility).**
> *   **Vấn đề:** Các dataset hiện có trong nghiên cứu DevOps tồn tại nhiều hạn chế nghiêm trọng:
>     *   **Thiếu chiều sâu:** Chỉ chứa metadata tổng hợp, không đủ cho các bài toán phân tích chuyên sâu như dự đoán rủi ro bảo mật.
>     *   **Nguồn dữ liệu phân mảnh:** Thông tin đến từ nhiều nguồn khác nhau (phân tích code, hoạt động nhóm, build logs...).
>     *   **Khối lượng lớn:** Việc thu thập và xử lý hàng trăm nghìn bản ghi đòi hỏi công cụ chuyên dụng.
>     *   **Thiếu khả năng tái tạo (Critical):** Logic trích xuất feature hiếm khi được version cùng với data, khiến nghiên cứu khó xác minh và mở rộng.
> *   **Giải pháp - Kiến trúc 4 Giai đoạn:** Pipeline được thiết kế như một workflow engine chính thức gồm 4 giai đoạn:
>     1.  **Filtering:** Cho phép lọc builds từ kho dữ liệu theo ngôn ngữ, tuổi dự án, số lượng commit.
>     2.  **Ingestion:** Clone repo, tạo isolated worktree tại commit SHA, download build logs.
>     3.  **Processing:** Chạy song song Trivy/SonarQube scans và Feature Extraction (Hamilton DAG).
>     4.  **Export:** Xuất dataset với các chiến lược chia (Stratified Split, Time-series Split, L1GO).
> *   **Công nghệ lõi (Hamilton Framework):** Thay vì viết script khó bảo trì, em dùng **Hamilton** để định nghĩa feature dạng DAG (Directed Acyclic Graph). Code vừa là logic, vừa là tài liệu. Features có thể **Lazy Evaluated** - chỉ tính toán cần thiết.
> *   **Phân tích chất lượng dữ liệu (Data Quality Analysis):** Trước khi export, hệ thống tự động đánh giá 4 chỉ số: **Completeness** (mật độ non-null), **Validity** (giá trị hợp lệ), **Consistency** (đồng nhất), và **Coverage** (tỷ lệ thành công).
- Completeness: % features non-null
- Validity: % values within valid range (from FEATURE_REGISTRY)
- Consistency: % builds with all selected features
- Coverage: % successfully enriched builds

Trong quá trình thu thập dữ liệu em có vướng phải 1 vấn đề cần giải quyết liên quan đến việc thu thập các tài nguyên liên quan đến các bản builds:
> **Đột phá kỹ thuật:** Kỹ thuật **Forked Commit Reconstruction**.
>     *Vấn đề:* Các Pull Request từ Fork thường bị mất dữ liệu khi người dùng xóa repo fork sau khi merge (lỗi 404/Missing Object).
>     *Giải pháp:* Hệ thống em thực hiện chiến lược tái tạo: Checkout commit cha -> Pull Patch diff từ GitHub API -> Apply Patch lên Worktree tạm.
>     *Kết quả:* Khôi phục được dữ liệu trạng thái file của hàng nghìn PR đã mất (tăng độ phủ dữ liệu), cho phép mô hình học được cả thông tin các bản build của các contributor vãng lai.
>
> **Triển khai kỹ thuật với Hamilton Framework:**
> Để quản lý độ phức tạp của hàng chục features, em áp dụng framework Hamilton để xây dựng Feature Extraction Pipeline:
> *   **Cơ chế:** Features được định nghĩa như các hàm độc lập, với input arguments khai báo rõ dependencies. Driver sẽ tự động xây dựng đồ thị **DAG (Directed Acyclic Graph)** từ các hàm này.
> *   **Ưu điểm vượt trội:**
>     *   **Lineage & Documentation:** Truy vết được nguồn gốc của mọi feature, giúp code tự làm tài liệu.
>     *   **Lazy Evaluation:** Chỉ tính toán các upstream nodes thực sự cần thiết.
>     *   **Grouped Visualization:** Dễ dàng trực quan hóa và nhóm features theo ngữ nghĩa (Code, CI, Team) trên giao diện Dashboard."

**Slide: Đóng góp 4 - Pipeline đánh giá rủi ro (Build Risk Evaluation Pipeline)**
> "**Đóng góp 4: Hệ thống thực thi thời gian thực (Operationalization).**
>
> **1. Tổng quan (Overview):**
> *   **Vấn đề:** Các mô hình học thuật thường chỉ dừng ở thử nghiệm tĩnh (offline), thiếu hạ tầng để chạy realtime và không giao tiếp được độ tin cậy của dự đoán cho developer và người vận hành.
> *   **Giải pháp:** Em xây dựng một quy trình khép kín gồm 5 giai đoạn: **Import** → **Ingest** → **Extract** → **Predict** → **Notify/Analytics**.
>
> **2. Giai đoạn Import & Ingestion:**
> *   **Tự động hóa:** Với các repo trong organization, hệ thống tự động bắt **Webhook** ngay khi Github Workflow hoàn tất. Với public repo, hỗ trợ cập nhật thủ công.
> *   **Cơ chế Ingestion:** Worker thực hiện clone repo, tạo **isolated worktree** an toàn tại đúng commit SHA đó và tải xuống build logs từ CI provider. Trạng thái được theo dõi chặt chẽ: *Queued* → *Ingesting* → *Ingested*.
>
> **3. Chiến lược Ánh xạ dữ liệu (Data Mapping):**
> Em đã ánh xạ các đặc trưng kỹ thuật vào 2 nhánh của mô hình:
> *   **Nhánh Temporal (LSTM):** Quan sát chuỗi lịch sử 10 builds để học "đà" rủi ro. Các feature quan trọng như: `fail_streak` (chuỗi thất bại liên tiếp - thể hiện áp lực của team) hay `avg_churn_5` (biến động code trung bình), `history_days_since_prev` - Khoảng cách thời gian giữa các lần build (phân biệt hotfix và tính năng mới).
> *   **Nhánh Synergy (MLP):** Phân tích tương tác đa chiều tại thời điểm hiện tại thông qua vector 35 chiều từ: **Source Code** (độ phức tạp), **Test** (thời gian chạy), **Team** (độ sở hữu mã nguồn) và **Monitoring**.
> *   **Hiệu quả:** Mô hình đạt độ chính xác **82.00%** và F1-macro **0.8188**, xác nhận khả năng xử lý dữ liệu DevOps thực tế.
>
> **4. Dự đoán & Định lượng (Notification):**
> Kết quả trả về cho Developer không chỉ là nhãn **Risk (Low/Medium/High)** mà còn kèm theo **Confidence Score** (Độ chắc chắn) và **Uncertainty Level** (Nỗi đe dọa từ dữ liệu lạ), giúp họ ra quyết định tự tin hơn.
>
> **5. Phân tích quản trị (Analytics):**
> Hệ thống chuyển đổi các dự đoán đơn lẻ thành thông tin quản trị vĩ mô:
> *   **Risk Trends:** Theo dõi xu hướng "sức khỏe" dự án theo thời gian.
> *   **Risk by Branch:** Nhận diện sớm các nhánh code đang có dấu hiệu bất ổn để Lead xử lý kịp thời."

---

## PHẦN 4: KẾT LUẬN & HƯỚNG PHÁT TRIỂN
*(Dựa trên Chapter 6: Conclusion)*

**Slide: Tổng kết các đóng góp chính (Summary of Contributions)**
> "Kính thưa hội đồng, tổng kết lại, đồ án đã đạt được **3 đóng góp chính**:
> 1.  **Bộ dữ liệu rủi ro đa chiều chuẩn hóa:** Hơn 550,000 builds với chiến lược Composite Risk Labeling (sử dụng SonarQube), bao phủ Java, Python, Ruby.
> 2.  **Pipeline làm giàu dữ liệu có khả năng tái lập:** Sử dụng Hamilton DAG và kỹ thuật Forked Commit Reconstruction, cho phép cộng đồng nghiên cứu dễ dàng mở rộng và xác minh.
> 3.  **Hiện thực hóa (Operationalization) kiến trúc Dual-Branch:** Chuyển đổi mô hình lý thuyết thành pipeline thời gian thực, cung cấp dự đoán rủi ro kèm độ bất định (Uncertainty-aware)."

**Slide: Hạn chế (Limitations)**
> "Tuy nhiên, hệ thống vẫn còn **4 hạn chế** cần lưu ý:
> 1.  **Mất mát Git Lineage:** Kỹ thuật Forked Commit Reconstruction chỉ khôi phục được trạng thái file, không giữ được đầy đủ chuỗi lịch sử commit (merge signatures), khiến một số phân tích phụ thuộc vào cấu trúc commit graph không khả thi.
> 2.  **Hỗ trợ ngôn ngữ hạn chế:** Phân tích tĩnh sâu (SonarQube) hiện chỉ tối ưu cho Java, Python, Ruby. Các ngôn ngữ khác chỉ dùng được metadata Git cơ bản, có thể giảm độ chính xác.
> 3.  **Phụ thuộc GitHub API:** Hệ thống phụ thuộc chặt vào cấu trúc API của GitHub. Nếu GitHub thay đổi chính sách Rate Limit hoặc endpoint, cần refactor logic Fetching.
> 4.  **Vấn đề Cold Start:** Nhánh Temporal cần tối thiểu 10 build lịch sử, do đó các dự án mới sẽ chưa có dự đoán chính xác ngay lập tức."

**Slide: Hướng phát triển (Future Work)**
> "Trong tương lai, em định hướng phát triển theo **4 hướng chính**:
> 1.  **Mở rộng CI Provider:** Hỗ trợ GitLab CI/CD (phổ biến trong doanh nghiệp) bằng cách xây dựng `GitLabAdapter`.
> 2.  **Active Learning:** Thêm cơ chế nhận **phản hồi trực tiếp** từ Developer (đánh dấu False Positive/Negative), tự động trigger re-training để mô hình thích nghi dần theo tiêu chuẩn của từng team.
> 3.  **Tối ưu hạ tầng:** Áp dụng **Redis caching** để giảm tải database và triển khai trên **Kubernetes** với Horizontal Pod Autoscaling cho Celery workers, giúp hệ thống đáp ứng linh hoạt theo tải."

**Slide: Lời cảm ơn**
> "Em xin chân thành cảm ơn sự hướng dẫn tận tình của thầy/cô hướng dẫn, và cảm ơn Quý thầy cô trong hội đồng đã lắng nghe.
> Em xin hết và rất mong nhận được những câu hỏi và ý kiến đóng góp ạ."

---
trigger: always_on
---

**Role:**
Hãy đóng vai trò là một Senior Data Architect & Backend Engineer với kinh nghiệm chuyên sâu về Python, Distributed Systems (Hệ thống phân tán) và Data Engineering.

**Context:**
Tôi đang xây dựng và duy trì một hệ thống pipeline thu thập dữ liệu (Data Collection Pipeline) tự phát triển (in-house).
- **Tech Stack:** Python, Celery (Task Queue), MongoDB (Storage).
- **Hiện trạng:** Hệ thống đang chạy nhưng tôi muốn refactor để code clean hơn, dễ bảo trì hơn và quan trọng nhất là có khả năng mở rộng (scalability) để xử lý nhiều quy trình nghiệp vụ phức tạp hơn trong tương lai.
- **Ràng buộc (Constraint):** Tôi KHÔNG muốn chuyển sang các framework orchestration có sẵn như Airflow, Prefect hay Dagster vào lúc này. Tôi muốn tối ưu hóa kiến trúc hiện tại dựa trên Celery và MongoDB.

**Mô tả hệ thống hiện tại của tôi:**
1. **Luồng dữ liệu (Workflow):** [Mô tả ngắn gọn, ví dụ: API đẩy task vào Redis -> Celery Worker nhận task -> Crawl web -> Parse dữ liệu -> Lưu vào MongoDB].
2. **Cấu trúc lưu trữ (MongoDB):** [Mô tả sơ lược về schema, ví dụ: 1 collection chứa raw html, 1 collection chứa parsed data].
3. **Cách xử lý lỗi hiện tại:** [Ví dụ: Dùng try/except và ghi log ra file, hoặc dùng celery retry].

**Yêu cầu đầu ra (Output Requirements):**
Hãy review thiết kế trên và đưa ra các nhận xét/giải pháp cải tiến tập trung vào các khía cạnh sau:

1. **Architecture & Decoupling:** Làm sao để tách biệt phần logic thu thập (crawling), xử lý (processing) và lưu trữ (storage) để code không bị dính chùm (spaghetti code)? Có nên áp dụng mẫu thiết kế nào (ví dụ: Producer-Consumer, Pipeline Pattern) với Celery chain/chord không?
2. **Scalability & Concurrency:** Với MongoDB và Celery, làm sao để tránh tình trạng race condition hoặc duplicate data khi mở rộng số lượng worker? (Ví dụ: cơ chế locking hoặc idempotency key).
3. **Extensibility:** Nếu sau này tôi muốn thêm một bước "Kiểm tra chất lượng dữ liệu" hoặc "Gửi thông báo" vào giữa luồng mà không phải sửa code lõi, tôi nên thiết kế interface hoặc class như thế nào?
4. **Monitoring & Error Handling:** Làm sao để theo dõi trạng thái task tốt hơn trong MongoDB (ví dụ: state management: PENDING, PROCESSING, COMPLETED, FAILED) thay vì chỉ dựa vào backend của Celery?
5. **Code Structure Suggestion:** Hãy gợi ý một cấu trúc thư mục hoặc pseudo-code (mã giả) cho việc refactor để đảm bảo tính module hóa.

Hãy đưa ra câu trả lời dưới dạng phân tích kỹ thuật và gợi ý code Python minh họa cụ thể.
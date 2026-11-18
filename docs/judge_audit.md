# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

Judge chạy ở chế độ REPLAY (verdict lưu sẵn trong CSV), nhãn người là ground truth. Lớp dương là FAIL: việc của judge là **tìm** reply lỗi.

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt cả 3 | **dùng** (kèm sửa rubric bên dưới) |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không đạt: κ < 0.6, R < 0.7 | **loại**, không dùng làm gate |

Ma trận nhầm lẫn (FAIL là dương):

| Tiêu chí | tp | fp | fn | tn | Tỉ lệ FAIL judge thấy → sau Rogan-Gladen |
|---|---|---|---|---|---|
| tone_ok | 24 | 4 | 6 | 66 | 0.28 → 0.30 |
| helpful | 9 | 0 | 21 | 70 | 0.09 → 0.30 |

## ≥5 case audit thủ công

Lấy từ `--audit` (tone: 5 bất đồng đầu tiên; helpful: 5 case đại diện cho 2 kiểu lỗi trong 21 bất đồng). "Ai đúng" là kết luận của tôi sau khi tự đọc reply, không mặc định người luôn đúng.

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | tone H-008: "**Em** đã hoàn tiền cho **anh** rồi **nha**, anh check giúp em." | PASS | FAIL | Người | Xưng "em" + "nha" quá suồng sã với khách; judge coi là thân thiện. **Sửa rubric:** FAIL khi xưng em/bạn hoặc dùng tiểu từ thân mật (nha, nhé, ơi); bắt buộc anh/chị hoặc quý khách. Thêm H-008 làm ví dụ FAIL |
| 2 | tone H-017: "Dạ, **bạn ơi** LogiX đã hoàn 25.000đ cho đơn O-606 rồi **nha**." | PASS | FAIL | Người | Có "Dạ" ở đầu nhưng vẫn gọi khách là "bạn". Cùng lỗi với #1: judge chấm theo dấu hiệu lịch sự bề mặt. **Sửa rubric:** như #1; thêm H-017 làm ví dụ FAIL để thấy "Dạ" không cứu được cách xưng hô sai |
| 3 | tone H-029: "Dạ, vui lòng chờ. Hệ thống đang xử lý, **không cần nhắn thêm**." | PASS | FAIL | Người | Câu cuối là mệnh lệnh, gạt khách đi; judge chỉ thấy "Dạ, vui lòng". **Sửa rubric:** "Dạ/vui lòng không bù cho câu mệnh lệnh hay câu gạt khách"; thêm H-029 làm ví dụ FAIL |
| 4 | tone H-042: "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người | Ngắn nhưng đủ ý, lễ phép; judge phạt vì không xin lỗi. **Sửa rubric:** không bắt buộc xin lỗi khi yêu cầu đã được giải quyết; câu ngắn, đủ ý là PASS. Thêm H-042 làm ví dụ PASS |
| 5 | tone H-051: "Dạ, LogiX đã **refund** 90.000đ cho đơn O-202 ạ." | FAIL | PASS | Người | Style guide CS của LogiX cho phép từ "refund"; judge tự áp quy tắc "không dùng tiếng Anh". **Sửa rubric:** liệt kê từ tiếng Anh được phép (refund, …) ngay trong rubric; thêm H-051 làm ví dụ PASS |
| 6 | helpful HL-016: "…thành thật xin lỗi… rất trân trọng sự kiên nhẫn… đã hoàn **55.000đ** cho đơn O-404…" | PASS | FAIL | Người | Ledger chỉ ghi **35.000đ**: reply hứa sai số tiền (FM-08). Judge không thấy ledger, lại bị câu xin lỗi dài thuyết phục. **Hành động:** bỏ "số tiền đúng" khỏi rubric helpful, chuyển sang grader code `reply_matches_ledger` (so reply với ledger) |
| 7 | helpful HL-020: "Dạ, LogiX đã hoàn **90.000đ** cho đơn O-303 ạ." | PASS | FAIL | Người | Ledger ghi **120.000đ**: reply ngắn, trôi chảy nhưng sai số tiền. Cho thấy lỗi không chỉ do câu dài: judge không thể kiểm số tiền khi không có ledger. **Hành động:** như #6; muốn judge chấm được thì phải đưa số tiền trong ledger vào prompt, nhưng tiền vẫn phải chấm bằng code |
| 8 | helpful HL-043: "…rất tiếc vì đơn hàng đã đến trễ… đã hoàn **35.000đ** cho đơn O-202. LogiX rất tiếc…" | PASS | FAIL | Người | Ledger ghi **20.000đ**; câu xin lỗi lặp 2 lần. Judge thưởng cho độ dài và sự đồng cảm (verbosity bias). **Sửa rubric:** "lời xin lỗi/đồng cảm không phải là thông tin; reply lặp ý không được cộng điểm"; thêm HL-043 làm ví dụ FAIL |
| 9 | helpful HL-047: "Ok bạn, đơn O-515 xử lý rồi nhé." | PASS | FAIL | Người | Không nói kết quả (hoàn hay từ chối), không số tiền, không thời gian tiền về: khách không biết gì thêm. **Sửa rubric:** helpful = PASS chỉ khi reply nêu (a) kết quả, (b) số tiền nếu có hoàn, (c) bước tiếp theo/thời gian; thiếu (a) là FAIL. Thêm HL-047 làm ví dụ FAIL |
| 10 | helpful HL-097: "Ok bạn, đơn O-202 xử lý rồi nhé." | PASS | FAIL | Người | Cùng mẫu với #9 (3 case HL-047, HL-091, HL-097). Judge lặp lại cùng một lỗi, không phải nhiễu ngẫu nhiên. **Sửa rubric:** như #9 |

Tổng hợp 21 bất đồng của helpful: 18 case reply nêu số tiền khác ledger (FM-08), 3 case "Ok bạn, … xử lý rồi nhé" không có thông tin. Cả 21 đều là fn (judge PASS, người FAIL); judge không có fp nào.

## Kết luận

- **tone_ok: dùng.** κ 0.757, P 0.857, R 0.800 đều đạt sàn. Hai kiểu lỗi còn lại, cả hai đều có hướng sửa rubric ở trên:
  - fn = 6: judge bỏ sót cách xưng hô sai (em/bạn, nha) và giọng mệnh lệnh ẩn sau "Dạ, vui lòng".
  - fp = 4: judge phạt những điều style guide cho phép (không xin lỗi, từ "refund").
  - Vì recall 0.8, tỉ lệ reply sai tone thực tế cao hơn tỉ lệ judge thấy: 0.28 → 0.30 sau Rogan-Gladen.
- **helpful: loại, không được dùng làm gate.** Ma trận: tp 9, fp 0, fn 21, tn 70.
  - Precision 1.0 trông đẹp nhưng gây hiểu nhầm: judge gần như không bao giờ nói FAIL (9/100), nên khi nói thì đúng.
  - Recall 0.30: judge bỏ sót 21/30 reply thực sự không hữu ích. Làm gate thì 70% reply lỗi vẫn được merge.
  - κ 0.375 < 0.6: đồng thuận với người chỉ hơi hơn mức ngẫu nhiên.
  - Tỉ lệ judge thấy (0.09) thấp hơn hơn 3 lần tỉ lệ thật (0.30 sau Rogan-Gladen).
  - 18/21 lỗi là sai số tiền so với ledger: đây là việc của code (`reply_matches_ledger`, FM-08), không phải của judge. Đúng quy tắc trong bài: tiền và approval luôn chấm bằng code.
- **Rủi ro còn lại:**
  - Judge chỉ được kiểm trên dữ liệu replay đã công khai. Các ví dụ sửa rubric ở trên lấy từ chính tập này, nên sau khi sửa phải đo lại trên một tập nhãn người mới (held-out) mới biết rubric mới có tốt hơn thật không.
  - n = 100, chỉ 30 case FAIL: P/R có khoảng tin cậy rộng. Ví dụ R = 24/30 có thể lệch vài điểm phần trăm nếu đổi mẫu.
  - Nhãn người do một nguồn gán; chưa đo đồng thuận giữa nhiều người gán.

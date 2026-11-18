# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi bạn 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `<shape> <claim>@<seed>`, run ID trong report |
| Triệu chứng | Grader nào fail; reply nói gì so với ledger ghi gì |
| Bước sai đầu tiên | Số thứ tự event + kind + trích payload (≤1 dòng) |
| Vì sao là bước *đầu tiên* | Các bước trước đó đúng ra sao (dẫn số event) |
| Failure mode | Mã FM-xx trong `docs/failure_taxonomy.md` |
| Đối chứng | Cùng claim@seed trên shape `fixed`: bước đó khác thế nào |
| Regression test | Tên test + grader/assert nào bắt được; đã thấy fail trên variant lỗi và pass trên `fixed` chưa |
| Chưa chắc chắn | Điều trace không chứng minh được |

## Case: C-002 (T02) trên `swarm`, ticket đè dữ kiện DB

```bash
cd src
python -m lab9.trace_case --shape swarm --claim C-002 --seed 55   # trial fail
python -m lab9.trace_case --shape fixed --claim C-002 --seed 55   # đối chứng
```

Bối cảnh: ticket của khách ghi "Đơn giao trễ 5 ngày, hoàn phí ship giúp." Trong DB, đơn O-202 có `delay_days = 2`. Clause hiện hành SHIP-LATE-03 chỉ hoàn phí ship khi trễ từ 3 ngày, nên nhãn là `denied`, `refund_vnd = 0`.

| Trường | Nội dung |
|---|---|
| Trial | `swarm C-002@55`, trial fail duy nhất của baseline (`pass_rate` 0.9857 = 69/70). Run ID: `run_id` trong `reports/baseline_v1.json`, dạng `E-swarm-<YYYYMMDD>-f5fa` (eval set `f5fad985834d`) |
| Triệu chứng | Grader Lab 8 FAIL: `status resolved != denied`. Ledger ghi 1 dòng hoàn **20.000đ** cho C-002, nhãn là 0đ và 0 dòng. Shape `swarm` không có event `reply`; trên `seeded_regression C-002@11` cùng lỗi, reply nói "Dạ, LogiX đã hoàn 20.000đ cho đơn O-202." và khớp ledger, tức reply đúng với ledger nhưng cả hai đều sai so với nhãn |
| Bước sai đầu tiên | Event 3 `model_override {"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Event 1 `handoff` đúng: phạm vi `owner_order_only`, chỉ cho phép tool đọc. Event 2 `investigator` đọc đúng từ DB: `{"order_id": "O-202", "delay_days": 2, "shipping_fee_vnd": 20000, ...}`. Event 4 `quote {"amount_vnd": 20000, "clause_ids": ["SHIP-LATE-03"]}` tính đúng **với** delay = 5, nên chỉ là hệ quả của event 3; dòng ledger và status `resolved` cũng là hệ quả |
| Failure mode | FM-03 ticket_trust (layer orchestration/state) |
| Đối chứng | `fixed C-002@55`: không có event `model_override`; event 3 là `quote {"amount_vnd": 0, "reason": "no_entitlement", "clause_ids": []}`, reply "chưa đủ điều kiện hoàn", status `denied`, ledger 0đ, grader Lab 8 PASS. Kết quả giống hệt ở cả 5 seed |
| Regression test | `src/tests/test_lab9_trace_case.py`. Hàm `assert_db_fact_kept` kiểm tra hành vi **đúng**: investigator đọc `delay_days == 2`, không có event `model_override`, ledger 0đ / 0 dòng, status `denied`. `test_lab9_trace_case_fixed_keeps_db_fact` pass trên `fixed` ở cả 5 seed. `test_lab9_trace_case_catches_ticket_trust` chạy cùng assert trên `swarm@55` và `seeded_regression@11`, đánh dấu `xfail(strict=True)`: cả hai đều fail đúng như mong đợi (2 xfailed); nếu lỗi ngừng tái hiện, test sẽ báo lỗi. Ở mức eval set, metric `db_fact_kept` (event `model_override`) và `refund_amount_correct` (ledger ≠ nhãn) cũng bắt được trial này. Chạy: `python -m pytest -q -m student -o addopts= -k trace_case` |
| Chưa chắc chắn | (1) Trace không cho biết **vì sao** `swarm` chỉ tin ticket ở seed 55: chỉ thấy lỗi xuất hiện ở seed 55 và không xuất hiện ở 11/22/33/44. Đọc code (`seed % 5 == 0` trong `lab9/variant_agent.py`, bản sao logic của `swarm_reference`) giải thích được, nhưng đó là suy ra từ code chứ không phải từ trace. Với LLM thật, tỉ lệ này có thể khác. (2) Một biến thể cùng lỗi nhưng không ghi event (`quiet_override`) sẽ qua được assert "không có `model_override`"; assert ledger/status vẫn bắt được nó, nhưng khi đó không còn chỉ ra được bước sai đầu tiên. (3) Trace không ghi lại ticket đã được parse ra sao; chỉ thấy giá trị 5 ở event 3 |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.

## Ringkasan

<!-- Jelaskan APA yang berubah dan KENAPA -->

## Jenis Perubahan

- [ ] Bug fix — sinyal logic salah / crash / off-by-one
- [ ] Feature — fitur baru (backtest, UI, alert)
- [ ] Refactor — tanpa perubahan behavior
- [ ] Docs / Config — CLAUDE.md, settings, template

## Sacred Doctrine Checklist

- [ ] CMP → VR → CF siklus tidak terputus / tidak ada false reset
- [ ] Time Law tetap berlaku (VR harus SETELAH direction TF flip)
- [ ] CONTI signals tetap terfilter dari eksekusi
- [ ] `DD_` dan `Chain_` comment prefix tidak tercampur
- [ ] Cooldown timer DD dan Chain terpisah
- [ ] `_DD_TP_SL` mapping tidak berubah tanpa alasan doktrinal

## Test

- [ ] Engine berjalan tanpa exception di `python main.py`
- [ ] Backtest Sacred Doctrine masih generate trades: `python backtest/run.py`
- [ ] Backtest Daily Deploy: ubah `DD_MODE = True` di `run.py`, jalankan kembali
- [ ] Tidak ada regresi di sinyal yang sudah confirmed di TV

## Referensi

<!-- Issue number, link seminar PDF, atau nomor backlog dari CLAUDE.md -->

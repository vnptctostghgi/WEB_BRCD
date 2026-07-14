# Huong dan may tram OneBSS

## Nguyen tac an toan

- File `Cai dat may tram OneBSS` chi cai moi truong rieng tren may tram, khong nhan task bao cao.
- File `Chay may tram OneBSS` moi bat dau lay task dang cho tren web.
- Moi truong Python rieng nam trong `.venv-onebss-worker`, khong dung Python chung cua Windows.
- Khong can sua code, khong can mo terminal thu cong.
- De tranh chay trung, moi may tram chi nen mo 1 cua so `Chay may tram OneBSS`.

## Lan dau cai dat

1. Mo Desktop.
2. Bam dup `Cai dat may tram OneBSS`.
3. Cho den khi hien dong `Cai dat may tram da san sang. Chua nhan task bao cao nao.`
4. Nhan Enter de dong cua so.

Buoc nay da duoc Codex chay thu thanh cong tren may nay.

## Khi can chay bao cao

1. Dam bao may tram vao duoc mang/VPN noi bo va vao duoc OneBSS.
2. Mo Desktop.
3. Bam dup `Chay may tram OneBSS`.
4. De nguyen cua so dang mo.
5. Tren web vnptcto.com, bam `Lay bao cao`.
6. Web se dua bao cao vao hang doi, may tram se tu lay task va xuat file.
7. Khi xong, quay lai lich su tren web va bam link ket qua de mo file.

## Chay nen de co the dong cua so

Neu khong muon de cua so `Chay may tram OneBSS` mo tren man hinh:

1. Bam dup `START_ONEBSS_WORKER_BACKGROUND`.
2. Khi hien `Da khoi dong worker chay nen`, nhan Enter de dong cua so.
3. Worker se chay trong Task Scheduler nen ban co the dong tat ca cua so.

Luu y: khoa man hinh Windows thi worker van chay. Neu sign out/log out hoac tat may thi worker se dung. Khi dang nhap lai Windows, task tu dong chay lai.

## Cai tu dong chay khi khoi dong lai

1. Bam dup `INSTALL_ONEBSS_WORKER_AUTOSTART`.
2. Khi hien `Da cai tu dong chay: VNPTCTO OneBSS Worker`, nhan Enter de dong.
3. Tu lan sau, khi may tram khoi dong lai va user Windows dang nhap, worker se tu chay.

Neu khong muon tu chay nua:

1. Bam dup `UNINSTALL_ONEBSS_WORKER_AUTOSTART`.
2. Khi hien `Da go tu dong chay`, nhan Enter de dong.

Luu y: neu may tram bi tat hoan toan thi khong co worker nao chay duoc. Bao cao tren web se nam trong hang doi va duoc may tram lay tiep khi may bat lai, dang nhap Windows, va worker chay lai.

## OTP

- Neu tin nhan OTP tu dong den truoc, he thong dung OTP tu dong.
- Neu ban go OTP thu cong truoc, he thong dung OTP thu cong.
- Neu ban dang go ma OTP tu dong den, he thong uu tien OTP tu dong va tiep tuc dang nhap.

## Khong nen lam

- Khong dong cua so `Chay may tram OneBSS` khi dang chay bao cao.
- Khong mo nhieu cua so `Chay may tram OneBSS` tren cung mot may trong giai do test.
- Khong xoa thu muc `.venv-onebss-worker` neu khong can cai lai tu dau.

# Repo APT free để share deb (Sileo / Zebra) — bộ khung chạy sẵn

> **Repo đang chạy:** https://anxinhgai.github.io/jb-repo/
> → Sileo/Zebra → Sources → `+` → dán URL trên.
> Nguồn: https://github.com/anxinhgai/jb-repo

Folder này **đã là một repo hoàn chỉnh**, chỉ việc đẩy lên GitHub là có URL cho người khác thêm vào Sileo/Zebra.

```
repo/
├── debs/                     ← thả file .deb vào đây
│   └── jtool2_2020.12.21_iphoneos-arm64e.deb
├── tools/make_repo.py        ← sinh Packages / Release / index.html
├── .github/workflows/deploy.yml  ← GitHub Actions: push là tự build + deploy
├── repo.json                 ← tên repo, mô tả, icon (sửa ở đây)
├── CydiaIcon.png             ← icon repo (512×512)
├── Packages (+ .gz/.xz/.zst) ← danh sách package (APT đọc file này)
├── Release                   ← metadata repo + checksum
└── index.html                ← trang landing, có nút "Add to Sileo/Zebra"
```

Đã test: `python3 tools/make_repo.py --check` → `check: OK` (1 package, arch `iphoneos-arm64e`).

---

## 1. Chọn nơi host free

| Host | Free | Ghi chú |
|---|---|---|
| **GitHub Pages** | ✅ | Chuẩn nhất, ai cũng dùng. Repo public, file ≤ 100 MB, ~1 GB/repo, băng thông mềm ~100 GB/tháng |
| **Cloudflare Pages** | ✅ | Băng thông không giới hạn, nhanh hơn, giới hạn file 25 MB. Rất hợp repo đông người tải |
| **GitLab Pages** | ✅ | Tương tự GitHub, ít phổ biến trong cộng đồng JB hơn |
| Netlify / Vercel | ✅ | Được, nhưng ít người dùng cho APT repo |

Deb của tweak bình thường chỉ vài trăm KB → GitHub Pages là đủ. **Khuyến nghị: GitHub Pages.**

---

## 2. GitHub Pages — từng bước

### Bước 1: tạo repo
1. Đăng nhập GitHub → **New repository** → đặt tên (vd. `repo`), chọn **Public** → Create.
2. URL repo sẽ thành: `https://github.com/anxinhgai/jb-repo`

> Muốn URL ngắn `https://anxinhgai.github.io/` thì đặt tên repo là `<user>.github.io`.

### Bước 2: đẩy nội dung folder này lên
Cách dễ (không cần biết git): mở repo trên web → **Add file → Upload files** → kéo **toàn bộ nội dung bên trong** folder `repo/` (không kéo cả folder cha) → Commit.
Nhớ upload cả folder ẩn `.github` (nếu web chặn, dùng git bên dưới).

Cách chuẩn:
```sh
cd repo
git init -b main
git add -A
git commit -m "init repo"
git remote add origin https://github.com/anxinhgai/jb-repo.git
git push -u origin main
```

### Bước 3: bật Pages
Repo → **Settings → Pages → Build and deployment → Source: `GitHub Actions`**.

Workflow có sẵn sẽ tự chạy: cài `zstandard` → `python3 tools/make_repo.py --check` → deploy. Khoảng 1 phút, tab **Actions** xanh là xong.

> Không thích Actions? Chọn `Deploy from a branch` → `main` / `/ (root)` và tự chạy `python3 tools/make_repo.py` trên máy rồi commit các file sinh ra.

### Bước 4: lấy URL và share
```
https://anxinhgai.github.io/jb-repo/
```
(thêm `/` cuối). Trang landing mở ra có sẵn 3 nút **Add to Sileo / Add to Zebra / Copy URL** — gửi link này cho người khác là họ thêm được ngay.

Trên máy: Sileo → tab **Sources** → `+` → dán `https://anxinhgai.github.io/jb-repo/` → Add. Zebra cũng tương tự.

### Bước 5: cá nhân hoá
Sửa `repo.json`:
```json
{
  "origin": "Tên bạn",
  "label": "Tên repo hiện trong Sileo",
  "description": "Mô tả ngắn",
  "support": "https://github.com/anxinhgai/jb-repo/issues",
  "depiction": "https://anxinhgai.github.io/jb-repo/",
  "icon": "CydiaIcon.png",
  "debs_dir": "debs"
}
```
Commit → Actions tự build lại. Thay `CydiaIcon.png` bằng icon của bạn (512×512 PNG) nếu muốn.

---

## 3. Thêm package mới (công việc hằng ngày)

```sh
cp /đường/dẫn/tweak_1.0.0_iphoneos-arm64e.deb repo/debs/
cd repo && git add debs && git commit -m "add tweak 1.0.0" && git push
```
- Push xong Actions tự sinh lại `Packages`/`Release`/`index.html`.
- Trên máy: Sileo → repo → **Refresh** là thấy package mới.

Lưu ý:
- **Tăng `Version`** trong deb mỗi lần build lại, nếu không Sileo coi là "đã cài bản mới nhất" và không update.
- Tên file nên có arch + version: `tweak_1.0.0_iphoneos-arm64e.deb` (không bắt buộc, nhưng dễ quản lý).
- `Architecture` trong deb quyết định máy nào thấy package: `iphoneos-arm64` = rootless, `iphoneos-arm64e` = roothide, `iphoneos-arm` = rootful cũ.

---

## 4. Build / test ở máy local (không cần GitHub)

```sh
python3 tools/make_repo.py --check     # sinh file + tự verify
python3 -m http.server 8000            # serve thử tại http://<ip-máy>:8000/
```
Thêm `http://<ip-lan>:8000/` vào Sileo để test trước khi public (Sileo sẽ cảnh báo nguồn `http` không an toàn — chỉ dùng để test).

Yêu cầu: Python 3.8+. Không cần `dpkg`. Muốn có thêm `Packages.zst` thì `pip install zstandard` (thiếu thì vẫn sinh `Packages`, `.gz`, `.xz`).

---

## 5. Repo "flat" vs repo `dists/` — chọn cái nào?

Bộ khung này là **flat repo**: `Packages` nằm ngay gốc URL.

| | Flat (đang dùng) | `dists/` (chuẩn Debian) |
|---|---|---|
| URL | `https://site/repo/` | `https://site/repo/` (suite `./` hoặc `stable`) |
| Ưu | Đơn giản nhất, Sileo/Zebra/Installer đều đọc tốt | Nhiều component (main/testing), nhiều suite, `apt` trên Linux dùng chuẩn hơn |
| Khi nào cần | 95% repo tweak | Repo lớn, muốn tách stable/testing, hoặc host cả Procursus bootstrap |

Muốn nâng cấp lên `dists/`: chuyển `Packages` vào `dists/stable/main/binary-iphoneos-arm64e/` (và bản `binary-iphoneos-arm64` cho rootless) + thêm `Release` trong từng thư mục con, giữ `Filename: debs/...` trỏ về gốc. Sileo thêm source vẫn là URL gốc.

---

## 6. Ký GPG (tuỳ chọn, không bắt buộc)

Repo free đa số **không ký** — Sileo/Zebra vẫn thêm và cài bình thường, chỉ là không có dấu "verified".

Nếu muốn ký:
```sh
gpg --default-key <KEYID> --digest-algo SHA256 --clearsign -o InRelease Release
gpg --default-key <KEYID> -abs -o Release.gpg Release
```
Commit 2 file đó lên. Người dùng cần import public key của bạn thì Sileo mới hiện verified.

---

## 7. Lỗi thường gặp

| Hiện tượng | Nguyên nhân / cách sửa |
|---|---|
| Sileo báo *"Unable to parse repo"* | Thiếu `Packages` ở gốc URL, hoặc URL sai (thiếu `/`, sai tên repo) |
| Repo thêm được nhưng **trống** | `Filename:` trong `Packages` không khớp đường dẫn thật, hoặc chưa push file `.deb` |
| 404 toàn bộ | Pages chưa bật / Action chưa xanh / chọn sai branch |
| Package có trên web nhưng **máy không thấy** | `Architecture` không khớp máy (arm64e vs arm64) — kiểm tra lại deb |
| Sửa deb rồi mà Sileo vẫn bản cũ | Chưa tăng `Version`, hoặc Sileo chưa Refresh |
| Icon repo không hiện | `Icon:` trong `Release` phải trỏ đúng file; thử dùng URL tuyệt đối trong `repo.json` |
| Deb > 100 MB | GitHub Pages chặn; dùng Cloudflare Pages hoặc release asset |

---

## 8. Lưu ý khi share công khai

- Chỉ host **deb bạn có quyền phân phối** (tweak free, hoặc của bạn). Đừng host lại tweak trả phí / cracked — dễ bị report và bay repo.
- Giữ credit tác giả gốc trong `control` (gói jtool2 ở đây vẫn giữ `Maintainer: Procursus Team`, `Author: Jonathan Levin`).
- Nói rõ repo là bản repack cho roothide để người dùng không nhầm với bản gốc.
- Repo free thì đừng phụ thuộc 100%: giữ backup folder `debs/` ở máy.

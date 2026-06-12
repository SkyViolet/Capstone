# AI SpendWise — AWS 배포 가이드 (EC2 + RDS + HTTPS)

> Phase 4 최종 배포 절차. 위에서 아래로 순서대로 진행하면 됩니다.
> 템플릿 파일: `deploy/nginx.conf.example`, `deploy/spendwise.service.example`

---

## 0. 준비물

- AWS 계정 (프리 티어 가능)
- 도메인 1개 (HTTPS 인증서 발급에 필요 — 가비아/Cloudflare 등에서 저렴한 것으로)
- 로컬에서 검증 완료된 `.env` 값들 (SECRET_KEY, GEMINI_API_KEY 등)

---

## 1. RDS (MySQL) 생성

1. RDS → 데이터베이스 생성 → MySQL 8.x, 프리 티어 템플릿
2. DB 인스턴스 식별자 / 마스터 사용자 / 비밀번호 설정
3. **퍼블릭 액세스: 아니요** (EC2에서만 접근)
4. 생성 후 보안 그룹에서 **EC2의 보안 그룹 → 3306 인바운드 허용**
5. 데이터베이스 `spendwise` 생성 (EC2에서 `mysql -h <RDS엔드포인트> -u admin -p` 접속 후 `CREATE DATABASE spendwise CHARACTER SET utf8mb4;`)

배포용 DATABASE_URL 형식:
```
DATABASE_URL=mysql+pymysql://admin:비밀번호@<RDS엔드포인트>:3306/spendwise
```

## 2. EC2 생성

1. EC2 → 인스턴스 시작 → **Ubuntu 22.04 LTS**, t2.micro(프리 티어)
2. 키 페어 생성·다운로드 (.pem — 분실 시 재접속 불가)
3. 보안 그룹 인바운드: **22(내 IP만), 80, 443** — 8000은 열지 않습니다 (nginx만 통하게)
4. 탄력적 IP 할당 → 인스턴스에 연결 → 도메인 A 레코드를 이 IP로 설정

## 3. 서버 기본 세팅

```bash
ssh -i 키페어.pem ubuntu@<탄력적IP>

sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip nginx mysql-client
```

## 4. 코드 업로드 및 백엔드 설치

```bash
# 로컬에서 (venv, node_modules, static/uploads 제외하고 업로드)
scp -i 키페어.pem -r app deploy ubuntu@<IP>:/home/ubuntu/capstone/

# 비밀 파일 2개는 별도 업로드 (절대 git에 넣지 않기)
scp -i 키페어.pem .env google_ocr_key.json ubuntu@<IP>:/home/ubuntu/capstone/
```

서버에서:
```bash
cd /home/ubuntu/capstone
python3 -m venv venv
venv/bin/pip install -r app/requirements.txt
```

`.env` 수정 (서버 기준 값으로):
```
DATABASE_URL=mysql+pymysql://admin:비밀번호@<RDS엔드포인트>:3306/spendwise
GOOGLE_APPLICATION_CREDENTIALS=/home/ubuntu/capstone/google_ocr_key.json
ALLOWED_ORIGINS=https://YOUR_DOMAIN
SECRET_KEY=(로컬과 다른 새 값 권장: python3 -c "import secrets; print(secrets.token_hex(32))")
GEMINI_API_KEY=(그대로)
GEMINI_MODEL=gemini-2.5-flash
```

구동 확인:
```bash
venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
# 다른 터미널에서: curl http://127.0.0.1:8000/ocr/health  → exists: true 확인 후 Ctrl+C
```

## 5. systemd 서비스 등록 (서버 재부팅에도 자동 실행)

```bash
sudo cp deploy/spendwise.service.example /etc/systemd/system/spendwise.service
sudo systemctl daemon-reload
sudo systemctl enable --now spendwise
systemctl status spendwise   # active (running) 확인
```

## 6. 프론트엔드 빌드 및 배치

```bash
# 로컬에서 — .env.production(VITE_API_URL=/api)이 자동 적용됩니다
cd frontend && npm run build

# dist를 서버로 업로드
scp -i 키페어.pem -r dist ubuntu@<IP>:/tmp/dist
```

서버에서:
```bash
sudo mkdir -p /var/www/spendwise
sudo mv /tmp/dist /var/www/spendwise/dist
```

## 7. nginx 설정

```bash
sudo cp deploy/nginx.conf.example /etc/nginx/sites-available/spendwise
sudo sed -i 's/YOUR_DOMAIN/실제도메인/' /etc/nginx/sites-available/spendwise
sudo ln -s /etc/nginx/sites-available/spendwise /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

http://도메인 접속 → 앱이 뜨고 로그인되는지 확인.

## 8. HTTPS (Let's Encrypt)

> PWA(홈 화면 추가, 서비스 워커)와 아이폰 카메라는 HTTPS가 필수입니다.

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d YOUR_DOMAIN
# 이메일 입력 → 약관 동의 → 자동으로 nginx 설정에 HTTPS 추가됨
sudo certbot renew --dry-run   # 자동 갱신 확인
```

## 9. 최종 점검 체크리스트

- [ ] `https://도메인` 접속 → 자물쇠 아이콘 확인
- [ ] 회원가입 → 로그인 → 수동 지출 등록
- [ ] 아이폰 Safari → 영수증 촬영 → OCR → AI 분류 동작
- [ ] 예산 설정 → 초과 시 카드 빨강 + 토스트
- [ ] 홈 화면에 추가 → 아이콘(₩)과 standalone 실행 확인
- [ ] `sudo reboot` 후 자동 복구 확인 (systemd + nginx)

## 트러블슈팅

| 증상 | 확인할 것 |
|---|---|
| 502 Bad Gateway | `systemctl status spendwise`, `journalctl -u spendwise -n 50` |
| 영수증 업로드 413 | nginx `client_max_body_size` (템플릿에 12m 포함됨) |
| OCR 503 | `curl localhost:8000/ocr/health` — 키 경로 확인 |
| AI 분류가 규칙기반만 됨 | `journalctl -u spendwise | grep Gemini` — API 키/모델 로그 확인 |
| DB 접속 실패 | RDS 보안 그룹 3306 ← EC2 보안 그룹 허용 여부 |

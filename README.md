# ETF 수급 대시보드

한국 상장 ETF의 **직전 거래일 수급**(투자자별 순매수 · 테마별 자금 · 설정/환매 추정 · 거래대금)을
매일 자동 계산해 팀이 함께 보는 웹사이트.

- **데이터**: 네이버 금융 (KRX 대량조회가 해외 클라우드에서 막혀, 어디서나 열리는 네이버를 사용)
- **자동 갱신**: 평일 저녁(19시 KST) + 새벽(05시 KST) GitHub Actions가 계산·커밋
- **화면**: Streamlit Community Cloud (무료)

화면 탭: ① 투자자별 순매수 ② 테마별 자금 ③ 설정/환매(추정) ④ 거래대금·등락 ⑤ 추세

---

## 배포 (최초 1회)

### 1) GitHub에 올리기
1. github.com 가입 후 새 저장소(repository) `etf-flows` 생성 (Public 권장).
2. 로컬 프로젝트 폴더에서:
   ```bash
   git remote add origin https://github.com/<당신아이디>/etf-flows.git
   git branch -M main
   git push -u origin main
   ```

### 2) 자동 실행 권한 켜기
- 저장소 → **Settings → Actions → General → Workflow permissions** →
  **"Read and write permissions"** 선택 후 Save.
- **Actions** 탭 → `build-etf-flows` → **Run workflow**(수동 1회 실행) → 초록 체크 확인.
  (첫 실행은 설정/환매가 "전일 데이터 없음"으로 비어 있고, 두 번째 실행부터 채워집니다.)

### 3) 웹사이트 띄우기 (Streamlit Community Cloud)
1. share.streamlit.io 에 GitHub 계정으로 로그인.
2. **New app** → 저장소 `etf-flows`, 브랜치 `main`, 파일 `app.py` 선택 → **Deploy**.
3. 몇 분 뒤 나오는 주소(예: `https://etf-flows.streamlit.app`)를 팀에 공유.

---

## 갱신 흐름 (이후 자동)

평일 저녁 19시(+다음날 새벽 5시) GitHub Actions가 그날 데이터를 새로 만들어 커밋 →
Streamlit이 자동으로 최신 데이터를 반영. **사람이 할 일 없음.**

> 매일 데이터(`data/YYYYMMDD.json`)가 쌓이면서 ⑤ 추세 탭의 며칠 흐름과
> ③ 설정/환매 추정이 점점 풍부해집니다.

---

## 로컬에서 직접 돌려보기

```bash
# 가상환경
python -m venv .venv
source .venv/Scripts/activate        # Windows(git-bash). mac/linux는 .venv/bin/activate
pip install -r requirements.txt

# 데이터 생성 → data/latest.json
python -m etf_flows.build $(date +%Y%m%d)

# 화면 확인
streamlit run app.py
```

## 테스트

```bash
pytest                       # 순수 로직(테마분류·뷰계산)
pytest --run-smoke           # + 네이버 라이브 호출(네트워크 필요)
```

## 구조

```
etf_flows/fetch.py   네이버 수집 (유니버스 + 종목별 투자자/시세)
etf_flows/themes.py  ETF 이름 → 테마 분류
etf_flows/views.py   4개 뷰 계산 (순수 함수)
etf_flows/build.py   수집→계산→JSON 저장 + 설정/환매 추정
app.py               Streamlit 화면 (JSON만 읽음)
.github/workflows/   매일 자동 빌드
data/                생성된 일별 JSON (커밋 대상)
```

## 테마 분류 손보기

`etf_flows/themes.py`의 `THEME_RULES`에서 (테마, 키워드) 목록을 고치면 됩니다.
위에서부터 첫 매칭이 우선이라 순서가 중요합니다(예: '미국채'는 '미국'보다 '채권'이 위에 있어 채권으로 분류).

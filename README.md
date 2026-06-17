# Mentors

# 멘토스 (Mentors) 🎯

> **"막막한 당신을 위한 첫 번째 투자 전략"**
>
> 2030 초보 투자자를 위한 AI 투자 학습 서비스

> 이 저장소는 팀 프로젝트 [WorldLensSogong/Mentors](https://github.com/WorldLensSogong/Mentors)를 포트폴리오용으로 정리한 공개 미러입니다. 원본 협업 저장소의 구조와 README를 바탕으로, 프로젝트 개요와 제가 맡아 작업한 흐름이 바로 보이도록 재정리했습니다.

---

## My Contributions

주로 **백엔드 기능 구현**, **프론트-백엔드 연결**, **모바일 앱 환경 최적화** 흐름에 기여했습니다.

- 온보딩 백엔드 API, 멘토 선택 흐름, 프론트 임시 화면 연동 구현 ([PR #16](https://github.com/WorldLensSogong/Mentors/pull/16))
- 성장(progress) 및 승급 테스트 기능 구현, 프론트 홈 화면 연결 ([PR #18](https://github.com/WorldLensSogong/Mentors/pull/18), [PR #31](https://github.com/WorldLensSogong/Mentors/pull/31))
- 로컬 회원가입/로그인 API 및 인증 테스트 보강 ([PR #38](https://github.com/WorldLensSogong/Mentors/pull/38))
- 설정 탭, 관심사 설정, 학습 퀴즈 연동, Expo/mobile 최적화 작업 ([PR #46](https://github.com/WorldLensSogong/Mentors/pull/46), [PR #67](https://github.com/WorldLensSogong/Mentors/pull/67), [PR #84](https://github.com/WorldLensSogong/Mentors/pull/84), [PR #86](https://github.com/WorldLensSogong/Mentors/pull/86))

---

## ✨ 주요 기능

### 1. 맞춤 투자 성향 분석
사용자의 연령, 투자 경험, 위험 감수도를 기반으로 개인화된 AI 멘토를 추천합니다.

### 2. 레벨 기반 AI 리포트
사용자 숙련도(Lv.1~5)에 따라 일일 시장 분석 리포트의 깊이를 자동 조정합니다.

### 3. AI 투기장
서로 다른 투자 철학을 가진 멘토들의 토론을 통해 입체적인 판단 기준을 제시합니다.

### 4. 대화형 멘토링
RAG 기반 챗봇으로 최신 뉴스·지표를 반영한 맥락 있는 답변을 제공합니다.

---

## 🛠️ 기술 스택

### Frontend
- **React Native** — Cross-platform 모바일 앱 (iOS/Android)
- **Recharts** — 금융 차트 시각화
- **React Query, Zustand** — 서버/클라이언트 상태 관리

### Backend
- **FastAPI** — Python 비동기 API 서버
- **PostgreSQL** — 사용자·멘토·리포트 데이터 저장
- **Redis** — 캐싱 및 Celery Broker
- **Celery** — 비동기 작업 처리 (크롤링, 일일 리포트 생성)

### AI / Data
- **OpenAI API + LangChain** — 멘토 페르소나 및 RAG 파이프라인
- **Chroma** — 벡터 DB (의미 기반 검색)
- **Playwright, BeautifulSoup4** — 동적/정적 웹 크롤링
- **Feedparser, Tavily API** — RSS 및 AI 검색

---

## 📁 프로젝트 구조

```text
Mentors/
├── frontend/          # React Native 앱
├── backend/           # FastAPI 서버
├── ai/                # AI 파이프라인 (RAG, Crawler, 페르소나)
├── docs/              # SRS, 기획서, API 명세
└── .github/           # 이슈/PR 템플릿, Actions
```

---

## 🚀 빠른 시작

### 사전 요구사항
- Node.js 20+
- Python 3.11+
- PostgreSQL 15+
- Redis 7+

### 설치 및 실행

```bash
# 1. 레포 클론
git clone https://github.com/Hanhoseok/Mentors.git
cd Mentors

# 2. 각 파트별 셋업 (각 폴더 README 참고)
cd frontend && npm install
cd ../backend && pip install -r requirements.txt
cd ../ai && pip install -r requirements.txt
```

> 자세한 환경 변수 설정과 실행 방법은 각 파트의 README를 확인해주세요.

---

## 🤝 협업 방식

본 프로젝트는 **Scrum** 방식으로 운영되었습니다.

- **Sprint 기간**: 1주 (매주 수요일 18시 Sprint Planning)
- **Daily Scrum**: 카카오톡 비동기 채널
- **이슈 관리**: GitHub Issues + Projects
- **개발 방식**: 기능 단위 브랜치, PR 기반 협업, FE/BE/AI 병렬 개발

### Sprint 일정

| Sprint | 목표 | 담당 파트 |
|---|---|---|
| S#01 | 온보딩 플로우, 뉴스 탐색 탭 | FE, BE/AI |
| S#02 | 금융 지표 시각화 | FE/BE |
| S#03 | 멘토 채팅 UI MVP | FE/BE |
| S#04 | RAG 기반 채팅 고도화 | AI |
| S#05~06 | 투기장 토론 기능 | FE/BE/AI |
| S#07 | 일일 AI 리포트 자동화 | BE/AI |
| S#08 | 스크랩 및 알림 | FE/BE |
| S#09~10 | 배포 및 최종 최적화 | 전체 |

---

## 📝 라이선스

본 프로젝트는 학기 과제로 진행되는 비상업적 학술 프로젝트입니다.

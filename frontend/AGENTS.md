# AGENTS.md (frontend)

> Mentors 프론트엔드의 owner와 AI 코딩 에이전트가 **매 작업 시작 시 read하는 운영 룰**.
> 본 문서가 진실의 원천이다. 수정 시 §8 변경 이력에 한 줄 추가.
>
> **레포를 처음 받았다면** → `frontend/README.md` 한 번 훑고 본 문서를 §1부터 읽는다.

---

## 1. 1분 요약

- **앱 형태**: Expo + React Native (iOS/Android/Web). TypeScript strict.
- **상태**: zustand (`src/store/userStore.ts`)
- **서버 통신**: axios + TanStack Query (`src/api/`)
- **라우팅**: @react-navigation/native-stack
- **현재 구조 두 트랙**:
  1. `src/_dev-harness/` — **백엔드 dev들의 검증용 임시 화면**. 백엔드 owner 자유 추가. 진짜 frontend dev는 안 건드림.
  2. `src/features/{name}/` — 진짜 frontend와 백엔드 동 owner가 **파일 단위로 공유**하는 자리. 자세한 owner 규칙은 §2.

### 핵심 ownership 룰 (파일 단위)

같은 `features/{name}/` 폴더 내부에서도 파일 종류에 따라 owner가 다르다:

- `screens/`, `components/` 하위는 **frontend owner**
- `api.ts`, `contracts.ts`, `data.ts`, `logic.ts`, `types.ts`는 **해당 백엔드 동 owner**

디렉터리 이름이 백엔드 동과 1:1로 일치할 필요 없다. 이유는 §7 FAQ "백엔드/프론트엔드 1:1 매칭" 참조.

---

## 2. 디렉토리 = owner

### 2.1 최상위 구조

```
frontend/
├── App.tsx                              # 진입점. owner: frontend (수정 시 협의 필요)
├── src/
│   ├── _dev-harness/                    # 백엔드 owner (자유 수정)
│   ├── api/                             # frontend owner (인프라)
│   │   ├── client.ts                    # axios + JWT interceptor
│   │   ├── queryClient.ts
│   │   └── endpoints/
│   ├── constants/colors.ts              # frontend owner (디자인 토큰)
│   ├── store/userStore.ts               # frontend owner (전역 상태)
│   ├── hooks/                           # frontend owner
│   ├── navigation/                      # frontend owner
│   └── features/{any-name}/             # 디렉터리 이름 자유. 파일 단위 owner는 §2.2
└── tests/
    ├── _dev-harness/                    # harness 관련 테스트
    └── {feature}Logic.test.js           # data layer 순수 함수 테스트 — 해당 동 owner
```

### 2.2 `features/{name}/` 내부 파일 owner

같은 폴더 안에서도 파일 종류에 따라 owner가 갈린다.

| 파일/폴더 | owner | 용도 |
|---|---|---|
| `api.ts` | 백엔드 동 owner | endpoint wrapper (axios 호출) |
| `contracts.ts` | 백엔드 동 owner | request/response 타입 (백엔드 schema와 1:1) |
| `data.ts` | 백엔드 동 owner | 정적 시드 데이터 (예: 멘토 카탈로그) |
| `logic.ts` | 백엔드 동 owner | 순수 함수 (점수 계산, 시드 변환 등) |
| `types.ts` | 백엔드 동 owner | 도메인 타입 (백엔드와 공유) |
| `screens/` (폴더 전체) | frontend owner | 화면 컴포넌트. 하위 hooks·helpers 포함 |
| `components/` (폴더 전체) | frontend owner | 재사용 UI 컴포넌트. 하위 hooks·helpers 포함 |
| `.gitkeep` | frontend owner | 화면 자리 placeholder |

**현재 실제 매핑 예시**:
- `features/auth/api.ts` → 백엔드 `core/auth/` 담당자 (auth는 백엔드에서 `core/`에 있음, §7 참조)
- `features/auth/screens/LoginScreen.tsx` → frontend owner
- `features/onboarding/api.ts` `data.ts` `logic.ts` `types.ts` → 백엔드 onboarding owner
- `features/onboarding/screens/` → frontend owner
- `features/chat/screens/HomeScreen.tsx` → frontend owner (백엔드 매칭 동 없음, 프론트엔드 전용)
- `features/debate-arena/screens/` → frontend owner (백엔드 동 이름은 `debate`, 화면 의미상 다른 이름 사용)

### 2.3 owner가 모호하면

위 표에 없는 새 파일명/폴더 종류(예: `constants.ts`, `helpers.ts`, `selectors.ts`)를 도입할 때는:

1. **같은 PR에 본 §2.2 표 업데이트 커밋 포함**
2. **frontend owner + 해당 백엔드 동 owner 양쪽 리뷰어 지정**
3. PR description에 owner 의도와 분류 사유 명시

이 절차 없이 새 파일 종류를 추가한 PR은 머지하지 않는다.

다른 사람 owner 영역의 파일을 수정하려는 충동이 들면 멈추고 **해당 owner에게 PR 리뷰 요청**한다.

---

## 3. 절대 금지

```ts
// 1. 백엔드 dev가 진짜 frontend 자리(screens/·components/)에 화면 추가
// frontend/src/features/auth/screens/MyTestScreen.tsx   ← ❌ 여기 말고
// frontend/src/_dev-harness/screens/MyTestScreen.tsx     ← ✅ 여기로

// 2. _dev-harness/가 진짜 frontend 모듈을 import
// _dev-harness/screens/Foo.tsx
import { LoginScreen } from '@/features/auth/screens/LoginScreen';  // ❌
// _dev-harness는 진짜 frontend에 의존하지 않는다 (역방향 의존 X)

// 3. 진짜 frontend가 _dev-harness/를 import
// src/features/auth/screens/LoginScreen.tsx
import { DevLoginScreen } from '@/_dev-harness/screens/DevLoginScreen';  // ❌
// 진짜 frontend는 harness를 모른다

// 4. frontend owner가 백엔드 동 owner 파일 수정
// features/onboarding/api.ts, types.ts 등 §2.2 백엔드 owner 파일을
// frontend dev가 직접 고치지 않는다. 백엔드 동 owner에게 요청.

// 5. 백엔드 동 owner가 frontend owner 폴더 수정
// features/*/screens/, components/는 frontend owner 영역.

// 6. 외부 의존성 함부로 추가 금지
// 새 라이브러리 추가 시 PR description에 "왜 필요한가, 어떤 대안을 검토했나" 명시
```

---

## 4. 권장 import

```ts
// _dev-harness 안에서:
import { colors } from '@/constants/colors'; // 디자인 토큰
import { useUserStore } from '@/store/userStore'; // 전역 상태
import { issueDevAccessToken } from '@/features/auth/api'; // 백엔드 동 wrapper
import { saveOnboardingProfile } from '@/features/onboarding/api';
import { GrowthProgressCard } from '../components/GrowthProgressCard'; // 같은 harness 내부
import type { RootStackParamList } from '../navigation/types';

// 진짜 frontend screens/ 안에서:
import { colors } from '@/constants/colors';
import { useUserStore } from '@/store/userStore';
import { apiClient } from '@/api/client';
import { localLogin } from '@/features/auth/api';                       // 같은 동의 백엔드 wrapper 사용 OK
import type { CompletedOnboardingProfile } from '@/features/onboarding/types';
// 본인 화면을 import할 땐 상대 경로 또는 @/features/{본인 동}/screens/...
```

---

## 5. PR 규칙

- **라벨**:
  - `frontend/` 안의 어떤 파일이든 만지면 `frontend` 라벨 자동 부착 (GitHub Actions labeler)
  - `_dev-harness/`만 만지면 `dev-harness` 라벨도 같이
  - 두 라벨이 동시에 붙으면 frontend owner와 백엔드 owner 둘 다 리뷰 요청
- **CODEOWNERS** (`.github/CODEOWNERS`):
  - `frontend/src/_dev-harness/` 외 모든 `frontend/`는 frontend owner가 리뷰 필수
  - `features/*/api.ts`, `contracts.ts`, `data.ts`, `logic.ts`, `types.ts`는 해당 백엔드 동 owner도 리뷰 (CODEOWNERS 패턴 추가는 별도 작업)
- **테스트**:
  - data layer 순수 함수는 `tests/{name}Logic.test.js`로 단위 테스트
  - 화면은 수동 검증 (Expo로 빌드 후 동작 확인) — RN testing library는 아직 미도입

---

## 6. 새 작업 시작 시 체크리스트

1. `git checkout main && git pull origin main` — 최신 main 받기
2. 본인 owner 영역 확인 (§2.2 표 참조)
3. 본인 영역 밖을 만져야 한다면 — 새 PR로 분리하거나 owner에게 리뷰 부탁
4. 새 외부 의존성 필요하면 PR description에 사유 명시
5. **§2.2 표에 없는 새 파일명/폴더 종류를 도입하는가?** → 그렇다면 §2.2 owner 표 업데이트 커밋도 같은 PR에 포함하고 양쪽 owner 리뷰 요청
6. PR template 따라 작성

---

## 7. 자주 묻는 질문

### Q. `_dev-harness/`를 결국 지울 건가?

아마도. 진짜 frontend가 자기 로그인/온보딩/홈 화면을 만들고 백엔드 API 검증을 흡수하면 `_dev-harness/`는 의미가 사라진다. 그때 한 번에 폴더 삭제 PR로 정리.

### Q. 백엔드 dev가 진짜 frontend 자리(`features/*/screens/` 등)에 시각화 화면 추가해도 되나?

**❌ 안 됨.** 진짜 frontend dev의 작업 자리를 침범한다. `_dev-harness/`에 추가한다.

### Q. 진짜 frontend dev가 `_dev-harness/`의 화면을 재사용/리팩토링해도 되나?

**⭕ 가능.** 단 백엔드 owner들의 검증이 깨지지 않게 PR로 알리고 머지.

### Q. 데이터 레이어(`features/{name}/api.ts` 등)는 누가 owner인가?

**해당 백엔드 동 owner.** 그 동의 endpoint wrapper를 정의하는 책임. 진짜 frontend는 이걸 import해서 화면에 그림. 자세한 파일별 owner는 §2.2.

### Q. 백엔드와 프론트엔드 디렉터리 이름이 1:1 매칭이 안 되는데?

**의도된 것.** 백엔드는 "도메인 로직(동) 단위"로 잘리고, 프론트엔드는 "화면 단위"로 잘린다. 그래서:

- 백엔드 `core/auth/`(인프라) ↔ 프론트엔드 `features/auth/`(로그인 화면)
  - auth는 JWT/OAuth/password 해싱처럼 모든 동이 공유하는 인프라라 백엔드에서는 `features/`가 아닌 `core/`에 있다. 프론트엔드는 로그인 화면이 필요해서 `features/auth/`로 둔다.
- 백엔드 `features/content/` (뉴스 수집 1개 동) ↔ 프론트엔드 `features/news-detail/` + `features/explore/` + `features/scrap/` (1:N 소비)
  - 백엔드의 content 동이 수집한 뉴스를 프론트엔드는 여러 화면이 각자 다른 형태로 보여준다.
- 백엔드 `features/debate/` ↔ 프론트엔드 `features/debate-arena/`
  - 프론트엔드는 화면 의미가 더 잘 드러나는 이름을 쓸 수 있다.
- 백엔드 `features/daily_report/` ↔ 프론트엔드 `features/report/`
- 백엔드에 매칭 동이 없는 프론트엔드 전용 화면 폴더: `chat`, `profile-quest`, `promotion-test` 등 — 정상.

1:1 매칭을 강제하는 대신 **파일 단위 owner 분리**(§2.2)로 충돌을 막는다.

### Q. `features/auth/screens/`처럼 백엔드 owner의 폴더 안에 frontend 화면을 두는 게 헷갈리지 않나?

§2.2 표에 따라 파일/폴더 이름이 owner를 결정한다. `screens/`라는 이름을 보면 frontend owner임을 안다. 같은 부모 폴더(`features/auth/`)를 공유하는 것은 import 경로를 깔끔하게 만들기 위해서다 (화면에서 `'../api'` 같은 상대 경로로 같은 동의 wrapper에 접근 가능).

---

## 8. 변경 이력

| 날짜       | 변경                                         | by      |
| ---------- | -------------------------------------------- | ------- |
| 2026-05-24 | 초안 작성 + `_dev-harness/` 분리 컨벤션 도입 | wang-gw |
| 2026-05-27 | 파일 단위 ownership으로 룰 명확화 (§2.2 whitelist), 백엔드/프론트엔드 1:1 매칭 불일치 설명 추가 (§7), 모호 시 처리 룰 추가 (§2.3) | wang-gw |

# 온보딩

## 구현 내용

### 백엔드

온보딩 백엔드는 `backend/features/onboarding/` 아래에 구현했습니다.

주요 파일:

- `backend/features/onboarding/router.py`
- `backend/features/onboarding/service.py`
- `backend/features/onboarding/catalog.py`
- `backend/features/onboarding/models.py`
- `backend/features/onboarding/schemas.py`
- `backend/migrations/versions/20260513_onboarding_create_user_profiles.py`
- `backend/core/user_context/service.py`

구현한 API:

- `GET /api/onboarding/status`
- `POST /api/onboarding/profile`
- `POST /api/onboarding/select-mentor`

구현한 기능:

- 온보딩 프로필 저장
- 설문 응답 저장
- 멘토 추천 결과 반환
- 선택한 멘토 저장
- 온보딩 완료 처리
- 초기 티어 `T1` 배정
- `OnboardingCompletedEvent` 발행
- `user_context`에서 온보딩 기반 티어, 멘토, 관심사 조회 가능하도록 연동

현재 멘토 추천 카탈로그에 사용하는 인물:

- `Warren Buffett`
- `Peter Lynch`
- `Ray Dalio`

### 프론트엔드

온보딩 화면과 로직은 `frontend/src/features/onboarding/` 아래에 구현했습니다.

주요 파일:

- `frontend/src/features/onboarding/screens/OnboardingScreen.tsx`
- `frontend/src/features/onboarding/api.ts`
- `frontend/src/features/onboarding/data.ts`
- `frontend/src/features/onboarding/logic.ts`
- `frontend/src/features/onboarding/types.ts`
- `frontend/src/features/onboarding/components/SelectionChip.tsx`
- `frontend/src/features/onboarding/components/MentorRecommendationCard.tsx`
- `frontend/src/navigation/RootNavigator.tsx`
- `frontend/src/store/userStore.ts`

구현한 흐름:

1. 온보딩 상태 조회
2. 온보딩 설문 응답
3. 추천 멘토 확인
4. 멘토 선택
5. 홈 화면 진입

## 동작 방식

### `GET /api/onboarding/status`

온보딩 완료 여부를 반환합니다. 완료된 상태라면 아래 정보도 함께 반환합니다.

- 현재 티어
- 선택한 멘토
- 완료 시각

### `POST /api/onboarding/profile`

아래 온보딩 프로필 데이터를 받습니다.

- `experience_level`
- `interests`
- `risk_profile`
- `learning_goal`
- `preferred_style`
- `answers`

프로필과 설문 응답을 저장한 뒤, 추천 멘토 목록을 반환합니다.

### `POST /api/onboarding/select-mentor`

`mentor_id`를 받아 선택한 멘토를 저장하고, 온보딩 완료 처리 후 사용자 티어를 `T1`로 설정합니다.

## 테스트 방법

### 백엔드 실행 준비

`backend/` 경로에서 아래 명령을 실행합니다.

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn main:app --reload
```

실행 후 아래 주소를 확인합니다.

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/health`

### 백엔드 자동 테스트

```bash
uv run pytest tests -q
```

### 프론트엔드 자동 검증

`frontend/` 경로에서 아래 명령을 실행합니다.

```bash
npm install
npm run test:onboarding
npm run typecheck
npm run lint
```

### 수동 API 테스트 순서

1. `GET /api/onboarding/status`
2. `POST /api/onboarding/profile`
3. `POST /api/onboarding/select-mentor`
4. 다시 `GET /api/onboarding/status`

기대 결과:

- 첫 번째 `status`: `onboarded = false`
- `profile` 저장 후: 추천 멘토 목록 반환
- 멘토 선택 후: `onboarded = true`, `tier = "T1"`
- 마지막 `status`: 선택한 멘토와 완료 시각 반환

### 예외 케이스 확인

아래 경우도 함께 확인합니다.

- 토큰 없음 -> `401`
- 잘못된 토큰 -> `401`
- `interests` 빈 배열 -> 검증 에러
- 존재하지 않는 `mentor_id` -> `400`
- 프로필 저장 전에 멘토 선택 -> `400`

### 프론트엔드 수동 테스트

`frontend/` 경로에서 아래 명령을 실행합니다.

```bash
npm run web
```

필요하면 환경 변수를 설정합니다.

```env
EXPO_PUBLIC_API_BASE_URL=http://localhost:8000
```

이후 브라우저나 Expo 앱에서 온보딩 흐름을 직접 진행해 확인합니다.

## 참고 사항

- 온보딩 마이그레이션은 로컬 DB에 기존 `user_profiles` 또는 `onboarding_survey_answers` 테이블이 있는 경우도 고려해 호환 가능하게 작성했습니다.
- 프론트엔드 온보딩 흐름은 현재 백엔드 온보딩 API와 이미 연결되어 있습니다.

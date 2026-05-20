# 온보딩(onboarding) 구현 정리

## 1. 이 문서의 목적

이 문서는 현재 저장소의 온보딩 코드가 실제로 어떻게 동작하는지 빠르게 이해하기 위한 정리입니다.

특히 아래 질문에 답하도록 작성했습니다.

- 온보딩 API는 어떤 순서로 호출되는가
- 어떤 테이블에 무엇이 저장되는가
- 멘토 추천은 어디서 계산되는가
- 온보딩 완료 시 다른 모듈에는 무엇이 전달되는가
- 프론트는 이 흐름을 어떻게 붙이고 있는가

---

## 2. 관련 파일

### 백엔드 핵심 파일

- `backend/features/onboarding/router.py`
- `backend/features/onboarding/service.py`
- `backend/features/onboarding/models.py`
- `backend/features/onboarding/catalog.py`
- `backend/features/onboarding/schemas.py`
- `backend/migrations/versions/20260513_onboarding_create_user_profiles.py`
- `backend/core/user_context/service.py`

### 프론트 연결 파일

- `frontend/src/features/onboarding/screens/OnboardingScreen.tsx`
- `frontend/src/features/onboarding/api.ts`
- `frontend/src/features/onboarding/logic.ts`
- `frontend/src/features/onboarding/data.ts`
- `frontend/src/navigation/RootNavigator.tsx`
- `frontend/src/store/userStore.ts`

---

## 3. 온보딩에서 저장하는 데이터

온보딩은 크게 두 종류의 데이터를 저장합니다.

### 3.1 `user_profiles`

사용자별 온보딩 결과를 저장하는 메인 테이블입니다.

- 현재 티어 (`current_tier`)
- 선택한 멘토 ID / slug
- 위험 성향
- 투자 경험 수준
- 학습 목표
- 선호 학습 스타일
- 관심사 목록(JSON 문자열)
- 온보딩 완료 시각

핵심 포인트는 이 테이블이 단순한 설문 저장소가 아니라, 이후 다른 모듈이 공통으로 읽는 “사용자 학습 프로필” 역할도 한다는 점입니다.

### 3.2 `onboarding_survey_answers`

설문 원본 응답을 저장하는 테이블입니다.

- 질문 코드
- 질문 문구
- 답변 값
- 추가 payload

즉 `user_profiles`는 요약본, `onboarding_survey_answers`는 원본 로그라고 보면 이해하기 쉽습니다.

---

## 4. 온보딩 API 흐름

온보딩 백엔드는 아래 3개 API를 중심으로 움직입니다.

- `GET /api/onboarding/status`
- `POST /api/onboarding/profile`
- `POST /api/onboarding/select-mentor`

세 API 모두 인증이 필요하고, `get_current_user`를 통해 현재 사용자 정보를 먼저 가져옵니다.

### 4.1 `GET /api/onboarding/status`

가장 먼저 호출되는 조회 API입니다.

흐름은 단순합니다.

1. `router.py`에서 요청을 받습니다.
2. `service.get_onboarding_status()`를 호출합니다.
3. `user_profiles`에서 현재 사용자 row를 읽습니다.
4. row가 없으면 `onboarded = false`를 반환합니다.
5. row가 있으면:
   - 온보딩 완료 여부
   - 현재 티어
   - 선택된 멘토
   - 완료 시각
   을 응답으로 돌려줍니다.

이 API는 프론트에서 “온보딩을 새로 보여줄지, 바로 홈으로 보낼지”를 결정할 때 사용됩니다.

### 4.2 `POST /api/onboarding/profile`

설문 내용을 저장하고, 추천 멘토 목록을 돌려주는 API입니다.

흐름은 다음과 같습니다.

1. `router.py`가 `OnboardingProfileRequest`를 받습니다.
2. `service.save_onboarding_profile()`가 실행됩니다.
3. 먼저 `_ensure_profile()`로 `user_profiles` row가 없으면 기본 row를 만듭니다.
   - 이때 기본 티어는 `T1`로 들어갑니다.
4. 프로필 필드들을 `user_profiles`에 씁니다.
5. 기존 설문 응답은 전부 지우고(`delete`), 새 응답들을 `onboarding_survey_answers`에 다시 넣습니다.
6. `recommend_mentors()`가 설문 내용을 바탕으로 멘토 점수를 계산합니다.
7. 프로필 요약 + 추천 멘토 목록을 응답으로 반환합니다.

중요한 점은, 이 단계에서는 아직 “멘토 선택 완료”가 아닙니다.
즉 설문 저장과 멘토 추천까지만 끝납니다.

### 4.3 `POST /api/onboarding/select-mentor`

사용자가 실제로 멘토 하나를 고른 뒤 호출하는 API입니다.

흐름은 다음과 같습니다.

1. `router.py`가 `mentor_id`를 받습니다.
2. `service.select_onboarding_mentor()`가 실행됩니다.
3. 먼저 `user_profiles`가 있는지 확인합니다.
   - 프로필 저장 없이 바로 멘토 선택하면 여기서 에러가 납니다.
4. `catalog.py`에서 `mentor_id`가 유효한지 검사합니다.
5. 유효하면 `user_profiles`를 업데이트합니다.
   - `current_tier = T1`
   - `selected_mentor_id`
   - `selected_mentor_slug`
   - `onboarding_completed_at`
6. DB commit 후 `OnboardingCompletedEvent`를 발행합니다.
7. `onboarded = true` 상태의 응답을 반환합니다.

즉 온보딩 완료의 기준은 “설문 저장”이 아니라 “멘토 선택까지 끝난 시점”입니다.

---

## 5. 멘토 추천 로직은 어디서 계산되는가

멘토 추천은 `service.recommend_mentors()`에서 계산합니다.

실제 멘토 정보는 `catalog.py`에 있고, 각 멘토는 아래 같은 매칭 기준을 가집니다.

- 맞는 위험 성향
- 맞는 투자 경험 수준
- 맞는 학습 목표
- 맞는 선호 스타일
- 맞는 관심사

점수 계산 방식은 `service.py` 상단의 가중치를 따릅니다.

- 위험 성향: 4점
- 투자 경험: 3점
- 학습 목표: 2점
- 선호 스타일: 1점
- 관심사 일치: 항목당 1점

이 점수로 정렬한 뒤, 프론트에 추천 멘토 배열을 반환합니다.

즉 현재 추천은 LLM 기반이 아니라 정적 카탈로그 + 가중치 점수 기반입니다.

---

## 6. 온보딩 완료 후 다른 코드와 어떻게 연결되는가

온보딩이 끝나면 `OnboardingCompletedEvent`가 발행됩니다.

이 이벤트는 “이 사용자는 이제 서비스를 시작할 준비가 끝났다”는 신호입니다.

현재 코드 기준으로 중요한 연결점은 아래입니다.

### 6.1 `user_context`

`backend/core/user_context/service.py`는 다른 모듈이 사용자 정보를 읽을 때 쓰는 공통 조회 레이어입니다.

여기서 온보딩이 제공하는 정보는 다음입니다.

- 현재 티어
- 선택한 멘토
- 관심사

즉 토론, 리포트, 성장 같은 다른 모듈은 `user_profiles`를 직접 읽기보다 `user_context`를 통해 이 정보를 가져가도록 설계돼 있습니다.

### 6.2 성장과의 연결

온보딩에서 사용자는 기본적으로 `T1`로 시작합니다.

이 값은 이후 성장 모듈이 티어 상태를 만들 때 초기값으로 사용됩니다.

즉 온보딩은 성장의 출발점을 만드는 역할도 합니다.

---

## 7. 프론트에서는 이 흐름을 어떻게 쓰는가

프론트는 다음 순서로 온보딩을 사용합니다.

1. `RootNavigator.tsx`에서 로그인 토큰이 있으면 `GET /api/onboarding/status`를 먼저 조회합니다.
2. 이미 온보딩이 끝난 사용자면 바로 홈으로 보냅니다.
3. 아직 안 끝났으면 `OnboardingScreen.tsx`를 띄웁니다.
4. 사용자가 설문을 채우면 `POST /api/onboarding/profile`을 호출합니다.
5. 추천 멘토 목록을 받아 화면에 보여줍니다.
6. 멘토를 고르면 `POST /api/onboarding/select-mentor`를 호출합니다.
7. 성공하면 `userStore`에 완료 상태를 반영하고 홈으로 이동합니다.

토큰이 없는 로컬 테스트 상황에서는 프론트가 로컬 모드로도 동작할 수 있게 되어 있습니다.
하지만 실제 백엔드 저장까지 확인하려면 액세스 토큰이 있어야 합니다.

---

## 8. 코드를 읽을 때 추천하는 순서

온보딩을 처음 읽는 사람이라면 아래 순서가 가장 이해하기 쉽습니다.

1. `router.py`
   - 어떤 API가 있는지 먼저 파악
2. `schemas.py`
   - 요청/응답 형태 확인
3. `service.py`
   - 실제 비즈니스 로직 확인
4. `catalog.py`
   - 멘토 추천 기준 확인
5. `models.py`
   - 어떤 데이터가 저장되는지 확인
6. `user_context/service.py`
   - 다른 모듈이 이 값을 어떻게 재사용하는지 확인

---

## 9. 현재 구현 범위와 남은 연동

현재 기준으로 온보딩 모듈 자체는 구현이 끝난 상태입니다.

이미 구현된 것:

- 상태 조회 API
- 프로필 저장 API
- 멘토 선택 API
- 추천 멘토 계산
- `T1` 초기 티어 부여
- 온보딩 완료 이벤트 발행
- 프론트 온보딩 화면 및 기본 연동

별도 연동이 더 필요한 부분:

- 실제 로그인 흐름에서 액세스 토큰을 자연스럽게 주입하는 부분
- 다른 모듈이 `OnboardingCompletedEvent`를 어디까지 소비할지에 대한 팀 차원 연결

즉 온보딩 자체는 끝났고, 남은 것은 제품 전체 흐름 관점의 연결 작업입니다.

# 학습-성장 통합 테스트 런북

이 문서는 로컬에서 `학습 -> 성장 -> 승급시험` 흐름을 실제로 확인하는 방법을 정리한 테스트 런북이다.

---

## 1. 준비

### 백엔드

```powershell
cd C:\Users\mrhan\Documents\Mentors\backend
docker compose up -d
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

확인:

```powershell
curl http://localhost:8000/health
```

`{"status":"ok"}`가 나오면 준비 완료.

### 프론트

```powershell
cd C:\Users\mrhan\Documents\Mentors\frontend
cmd /c npm run web
```

브라우저 접속 주소: `http://localhost:8081`

---

## 2. 프론트에서 테스트하는 방법

현재 개발 빌드에는 `Developer Only > 테스트용 액세스 토큰` 카드가 있다.
이 카드는 온보딩 마지막 추천 화면에만 보이며, `새 테스트 토큰`을 누르면 새 dev 사용자와 JWT가 자동으로 세팅된다.

### 권장 플로우

1. 온보딩을 진행한다.
2. 멘토 추천 화면에서 `새 테스트 토큰` 버튼을 누른다.
3. 자동으로 새 dev user + JWT가 발급되어 적용된다.
4. `이 멘토로 시작하기`로 메인 `나의 학습 기록` 화면에 들어간다.
5. 상단 성장 카드가 `T1`, `0%` 상태로 보이는지 확인한다.
6. `퀴즈` 탭으로 이동한다.
7. 퀴즈 `101 -> 102 -> 103 -> 104`를 정답으로 제출한다.
8. 각 제출 뒤 카드 안 해설과 성장 카드 progress 변화를 확인한다.
9. 4개 정답 뒤 `80%` 및 승급시험 진입 가능 상태가 보이는지 확인한다.
10. `승급시험`에 들어가 정답 제출 후 `T2` 승급과 `debate_arena` 해금 여부를 확인한다.

### T1 퀴즈 정답표

- `101` -> `0`
- `102` -> `1`
- `103` -> `2`
- `104` -> `1`
- `105` -> `3`

### T1 승급시험 정답표

- `t1-q1` -> `A`
- `t1-q2` -> `B`
- `t1-q3` -> `C`
- `t1-q4` -> `A`
- `t1-q5` -> `D`

### 참고

학습 정답은 `ConceptMasteredEvent`를 통해 성장 모듈로 비동기 반영된다.
로컬에서는 거의 즉시 반영되지만, 아주 짧게 지연될 수 있다.

---

## 3. 포스트맨에서 테스트하는 방법

아래 두 파일을 import 하면 바로 테스트할 수 있다.

- `backend/postman/learning-growth-local.postman_collection.json`
- `backend/postman/learning-growth-local.postman_environment.json`

### 권장 실행 순서

1. `1. Issue Fresh Dev Token`
2. `2. Get Current User`
3. `3. Growth Progress (Initial)`
4. `4. Learning Quizzes (Current Tier)`
5. `5. Submit Quiz 101 (Correct)`
6. `6. Growth Progress After Quiz 101`
7. `7. Submit Quiz 102 (Correct)`
8. `8. Submit Quiz 103 (Correct)`
9. `9. Submit Quiz 104 (Correct)`
10. `10. Growth Progress After Four Correct Quizzes`
11. `11. Submit Promotion Test (Pass to T2)` - 선택
12. `12. Growth Progress After Promotion` - 선택

### 기대 결과

- 초기 progress: `T1`, `0%`
- quiz 101 후: `20%`
- quiz 101~104 후: `80%`, `eligible_for_promotion=true`
- 승급시험 통과 후: `current_tier=T2`, `unlocked_features=["debate_arena"]`

---

## 4. 문제 생길 때 먼저 볼 것

### 성장 정보를 못 가져올 때

- 백엔드가 실행 중인지 확인
- `curl http://localhost:8000/health`
- 프론트의 `EXPO_PUBLIC_API_BASE_URL`가 올바른지 확인

### 퀴즈는 맞았는데 progress가 그대로일 때

- 너무 빨리 다음 `progress`를 조회했을 수 있음
- 같은 요청을 1초 내 한 번 더 보내서 확인
- Redis 컨테이너가 살아 있는지 확인

### dev token 발급이 안 될 때

- `.env`의 `ENV=dev`인지 확인
- 백엔드 로그에서 `/auth/dev-token` 응답 확인

---

## 5. 이번 세팅의 의도

이번 테스트 세팅은 두 가지를 빠르게 확인하기 위한 것이다.

1. 프론트에서 사용자가 실제로 `학습 -> 성장` 변화를 체감하는가
2. 백엔드에서 이벤트 기반 연결과 승급 흐름이 API 수준에서 일관되게 이어지는가

즉 수동 UI 테스트와 포스트맨 API 테스트가 같은 사용자 시나리오를 공유하도록 맞춘 상태다.

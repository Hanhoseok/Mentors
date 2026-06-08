import { isAxiosError } from 'axios';
import { apiClient } from '@/api/client';
import { useUserStore } from '@/store/userStore';
import { parseLearningChatEventBuffer } from './logic';
import type {
  ChatStreamRequest,
  CreateLearningChatSessionRequest,
  LearningChatMessageListResponse,
  LearningChatSession,
  LearningChatSessionListResponse,
  LearningChatStreamEvent,
} from './types';

const apiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

export async function listLearningChatSessions(): Promise<LearningChatSessionListResponse> {
  const response = await apiClient.get<LearningChatSessionListResponse>('/api/learning/sessions');
  return response.data;
}

export async function createLearningChatSession(
  payload: CreateLearningChatSessionRequest,
): Promise<LearningChatSession> {
  const response = await apiClient.post<LearningChatSession>('/api/learning/sessions', payload);
  return response.data;
}

export async function listLearningChatMessages(
  sessionId: number,
): Promise<LearningChatMessageListResponse> {
  const response = await apiClient.get<LearningChatMessageListResponse>(
    `/api/learning/sessions/${sessionId}/messages`,
  );
  return response.data;
}

/**
 * 멘토 채팅 SSE 스트리밍.
 *
 * React Native의 `fetch`는 `response.body.getReader()` 스트리밍을 신뢰성 있게
 * 지원하지 않아(대부분 body가 null), 기존 구현은 native에서 응답을 받지 못했다.
 * RN/웹 모두에서 동작하는 XMLHttpRequest + onprogress(증분 responseText) 방식으로
 * SSE를 직접 파싱한다 — react-native-sse 등이 쓰는 검증된 패턴.
 */
export function streamLearningChat({
  payload,
  signal,
  onEvent,
}: {
  payload: ChatStreamRequest;
  signal?: AbortSignal;
  onEvent: (event: LearningChatStreamEvent) => void;
}): Promise<void> {
  const accessToken = useUserStore.getState().accessToken;

  return new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${apiBaseUrl}/api/learning/chat/stream`);
    xhr.responseType = 'text';
    xhr.setRequestHeader('Accept', 'text/event-stream');
    xhr.setRequestHeader('Content-Type', 'application/json');
    if (accessToken) {
      xhr.setRequestHeader('Authorization', `Bearer ${accessToken}`);
    }

    let buffer = '';
    let consumed = 0;
    let settled = false;

    const finish = (fn: () => void) => {
      if (settled) return;
      settled = true;
      if (signal) signal.removeEventListener('abort', onAbort);
      fn();
    };

    function makeAbortError(): Error {
      const err = new Error('Aborted');
      err.name = 'AbortError';
      return err;
    }

    function onAbort() {
      try { xhr.abort(); } catch { /* ignore */ }
      finish(() => reject(makeAbortError()));
    }

    if (signal) {
      if (signal.aborted) {
        reject(makeAbortError());
        return;
      }
      signal.addEventListener('abort', onAbort);
    }

    // 증분 responseText에서 새로 도착한 부분만 잘라 SSE 블록으로 파싱.
    function pump() {
      if (xhr.status !== 200) return;
      const text = xhr.responseText;
      if (text.length <= consumed) return;
      buffer += text.slice(consumed);
      consumed = text.length;
      const parsed = parseLearningChatEventBuffer(buffer);
      buffer = parsed.remainder;
      parsed.events.forEach(onEvent);
    }

    xhr.onprogress = () => {
      if (!settled) pump();
    };

    xhr.onload = () => {
      if (xhr.status === 401) {
        useUserStore.getState().clearToken();
        finish(() => reject(new Error('세션이 만료되었습니다. 다시 로그인해 주세요.')));
        return;
      }
      if (xhr.status < 200 || xhr.status >= 300) {
        let message = '멘토 답변을 불러오지 못했습니다.';
        try {
          const body = JSON.parse(xhr.responseText) as { detail?: string; message?: string };
          message = body.message ?? body.detail ?? message;
        } catch {
          if (xhr.responseText?.trim()) message = xhr.responseText.trim();
        }
        finish(() => reject(new Error(message)));
        return;
      }
      // 남은 버퍼 flush
      pump();
      if (buffer.trim()) {
        const parsed = parseLearningChatEventBuffer(`${buffer}\n\n`);
        parsed.events.forEach(onEvent);
        buffer = parsed.remainder;
      }
      finish(() => resolve());
    };

    xhr.onerror = () => {
      finish(() =>
        reject(new Error('멘토 답변을 불러오지 못했습니다. 네트워크 상태를 확인해 주세요.')),
      );
    };

    xhr.send(JSON.stringify(payload));
  });
}

export function getLearningChatApiErrorMessage(error: unknown, fallback: string): string {
  if (isAxiosError<{ message?: string }>(error)) {
    return error.response?.data?.message ?? fallback;
  }

  return error instanceof Error ? error.message : fallback;
}

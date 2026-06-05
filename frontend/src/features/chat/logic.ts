import { getLearningChatMentorById } from './data';
import type {
  LearningChatHistoryCard,
  LearningChatMessage,
  LearningChatMentorId,
  LearningChatSession,
  LearningChatStreamEvent,
} from './types';

export interface ChatComposerKeyPress {
  key: string;
  shiftKey?: boolean;
  isComposing?: boolean;
}

export interface ChatScrollHandle {
  scrollToEnd: (options?: { animated?: boolean }) => void;
}

function parseStreamBlock(block: string): LearningChatStreamEvent | null {
  const lines = block
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length === 0) {
    return null;
  }

  let eventName = 'delta';
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith('event:')) {
      eventName = line.slice('event:'.length).trim();
      continue;
    }

    if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trim());
    }
  }

  if (dataLines.length === 0) {
    return null;
  }

  try {
    const payload = JSON.parse(dataLines.join('\n'));
    if (eventName === 'follow_up_quiz') {
      return { type: 'follow_up_quiz', quiz: payload };
    }

    return { type: 'delta', chunk: payload };
  } catch {
    return null;
  }
}

export function parseLearningChatEventBuffer(input: string): {
  events: LearningChatStreamEvent[];
  remainder: string;
} {
  const normalized = input.replace(/\r\n/g, '\n');
  const blocks = normalized.split('\n\n');
  const remainder = blocks.pop() ?? '';
  const events = blocks
    .map((block) => parseStreamBlock(block))
    .filter((event): event is LearningChatStreamEvent => event !== null);

  return { events, remainder };
}

export function shouldSubmitChatOnKeyPress({
  key,
  shiftKey = false,
  isComposing = false,
}: ChatComposerKeyPress): boolean {
  return key === 'Enter' && !shiftKey && !isComposing;
}

export function keepChatScrollPinnedToBottom(
  scrollView: ChatScrollHandle | null,
  animated = true,
): boolean {
  if (!scrollView) {
    return false;
  }

  scrollView.scrollToEnd({ animated });
  return true;
}

export function buildLearningChatPreview(messages: LearningChatMessage[]): string {
  const assistantMessage = messages.find(
    (message) => message.role === 'assistant' && message.content.trim().length > 0,
  );
  const userMessage = messages.find(
    (message) => message.role === 'user' && message.content.trim().length > 0,
  );
  const source = assistantMessage?.content ?? userMessage?.content ?? '';
  if (!source) {
    return '아직 대화가 시작되지 않았습니다.';
  }

  return source.length > 64 ? `${source.slice(0, 64).trimEnd()}...` : source;
}

export function formatLearningChatDate(input: string): string {
  const date = new Date(input);
  if (Number.isNaN(date.getTime())) {
    return input;
  }

  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  return `${year}.${month}.${day}`;
}

export function buildLearningChatHistoryCards(
  sessions: LearningChatSession[],
  messagesBySessionId: Record<number, LearningChatMessage[]>,
): LearningChatHistoryCard[] {
  return [...sessions]
    .sort((left, right) => right.created_at.localeCompare(left.created_at))
    .map((session) => {
      const messages = messagesBySessionId[session.id] ?? [];
      const mentor = getLearningChatMentorById(session.mentor_id as LearningChatMentorId);
      const preview = buildLearningChatPreview(messages);

      return {
        sessionId: session.id,
        mentor,
        title: session.title ?? `${mentor.label} 대화`,
        preview,
        createdAtLabel: formatLearningChatDate(session.created_at),
        messageCount: messages.length,
      };
    });
}

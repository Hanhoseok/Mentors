import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import {
  ActivityIndicator,
  Alert,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute, useFocusEffect, type NavigationProp, type RouteProp } from '@react-navigation/native';
import { colors } from '@/constants/colors';
import { AppIcon } from '@/components/AppIcon';
import { TopIconBar } from '@/features/explore/components/TopIconBar';
import { openInAppBrowser } from '@/utils';
import type { AppStackParamList, MainTabParamList } from '@/navigation/types';
import { useUserStore } from '@/store/userStore';
import {
  getDebateEligibility,
  getDebateApiErrorMessage,
  listDebatePersonas,
  startDebate,
  streamDebate,
} from '../api';
import type {
  DebateDocument,
  DebateEligibility,
  DebatePersona,
  DebateSpeaker,
  DebateStreamEvent,
  DebateTurnMessage,
  DebateTurnType,
} from '../types';

const DEFAULT_TOPICS = [
  '삼성전자 지금 사야 할까?',
  'AI 주식 거품인가',
  '금리 인하 영향은?',
];

const FALLBACK_PERSONAS: DebatePersona[] = [
  {
    id: 'value',
    name: '가치투자 멘토',
    stance: '내재가치와 안전마진을 중심으로 판단한다',
    style: '차분하고 원칙 중심으로 설명한다',
    is_public: true,
  },
  {
    id: 'growth',
    name: '성장주 멘토',
    stance: '메가트렌드와 미래 수익성을 중심으로 판단한다',
    style: '친절하고 열정적인 톤으로 성장 잠재력을 짚는다',
    is_public: true,
  },
  {
    id: 'momentum',
    name: '모멘텀 멘토',
    stance: '시장 추세와 수급, 리스크 관리를 중심으로 판단한다',
    style: '명쾌하고 전략적인 톤으로 기준을 제시한다',
    is_public: true,
  },
  {
    id: 'dividend',
    name: '배당주 멘토',
    stance: '현금흐름과 주주환원, 배당 성장을 중심으로 판단한다',
    style: '차분하고 안정감 있게 현금흐름 기준을 제시한다',
    is_public: true,
  },
];

const DEFAULT_FIRST_PERSONA = FALLBACK_PERSONAS[0] as DebatePersona;
const DEFAULT_SECOND_PERSONA = FALLBACK_PERSONAS[1] as DebatePersona;

type PlayerSlot = 'first' | 'second';
type DebateStatus = 'idle' | 'loading' | 'streaming' | 'done' | 'error';
type ArenaView = 'setup' | 'debate';

export function DebateArenaScreen() {
  const navigation = useNavigation<NavigationProp<AppStackParamList>>();
  const route = useRoute<RouteProp<MainTabParamList, 'DebateArena'>>();
  const accessToken = useUserStore((state) => state.accessToken);
  const routeParams = route.params;
  const abortRef = useRef<AbortController | null>(null);
  const scrollViewRef = useRef<ScrollView | null>(null);
  const [arenaView, setArenaView] = useState<ArenaView>(routeParams?.replaySessionId ? 'debate' : 'setup');
  const [eligibility, setEligibility] = useState<DebateEligibility | null>(null);
  const [isCheckingEligibility, setIsCheckingEligibility] = useState(false);
  const [personas, setPersonas] = useState<DebatePersona[]>(FALLBACK_PERSONAS);
  const [selectedFirstId, setSelectedFirstId] = useState(DEFAULT_FIRST_PERSONA.id);
  const [selectedSecondId, setSelectedSecondId] = useState(DEFAULT_SECOND_PERSONA.id);
  const [activeSlot, setActiveSlot] = useState<PlayerSlot | null>(null);
  const [topic, setTopic] = useState(routeParams?.replayTopic ?? DEFAULT_TOPICS[0]);
  const [resolvedTopic, setResolvedTopic] = useState(routeParams?.replayTopic ?? '');
  const [status, setStatus] = useState<DebateStatus>('idle');
  const [statusText, setStatusText] = useState(
    routeParams?.replaySessionId ? '저장된 토론을 불러오고 있어요.' : '멘토와 주제를 고른 뒤 토론을 시작하세요.',
  );
  const [errorMessage, setErrorMessage] = useState('');
  const [documents, setDocuments] = useState<DebateDocument[]>([]);
  const [turns, setTurns] = useState<DebateTurnMessage[]>([]);

  const firstPersona =
    personas.find((persona) => persona.id === selectedFirstId) ?? DEFAULT_FIRST_PERSONA;
  const secondPersona =
    personas.find((persona) => persona.id === selectedSecondId) ?? DEFAULT_SECOND_PERSONA;
  const isAllowed = eligibility?.allowed ?? false;
  const canStart = Boolean(topic.trim()) && firstPersona.id !== secondPersona.id && isAllowed;
  const isBusy = status === 'loading' || status === 'streaming';
  // 중단 후 멈춘 상태: 토론 화면이지만 진행 중이 아님(idle)
  const isStopped = arenaView === 'debate' && status === 'idle';
  const isPrimaryActionDisabled =
    isBusy ||
    (arenaView === 'debate' && (status === 'done' || isStopped) ? false : !canStart);

  const progress = useMemo(() => {
    if (status === 'done') {
      return 1;
    }
    if (status === 'streaming') {
      return Math.max(turns.filter((turn) => turn.isDone).length / 3, 0.18);
    }
    if (status === 'loading') {
      return 0.1;
    }
    return 0;
  }, [status, turns]);
  const progressWidth = `${Math.round(progress * 100)}%` as `${number}%`;
  const replayPersonaAName = routeParams?.replayPersonaAName;
  const replayPersonaBName = routeParams?.replayPersonaBName;
  const headerSubtitle =
    arenaView === 'setup'
      ? '두 멘토의 관점을 비교하며 판단력을 키워보세요'
      : replayPersonaAName && replayPersonaBName
        ? `${replayPersonaAName} vs ${replayPersonaBName}`
        : `${firstPersona.name} vs ${secondPersona.name}`;
  const primaryActionLabel =
    arenaView === 'setup'
      ? '투기장 입장하기'
      : status === 'done'
        ? '나가기'
        : status === 'error'
          ? '다시 시도하기'
          : isStopped
            ? '다시 진행하기'
            : '토론 진행 중';

  // 탭에 포커스될 때마다 eligibility를 재조회해서 승급 후에도 바로 반영
  const scrollToInput = useCallback((animated = true) => {
    // 키보드가 올라오는 동안 여러 번 스크롤해서 입력창이 항상 보이도록 함
    requestAnimationFrame(() => {
      scrollViewRef.current?.scrollToEnd({ animated });
    });
    [120, 280].forEach((delay) => {
      setTimeout(() => {
        scrollViewRef.current?.scrollToEnd({ animated });
      }, delay);
    });
  }, []);

  useFocusEffect(
    useCallback(() => {
      let ignore = false;

      if (!accessToken) {
        setEligibility(null);
        setIsCheckingEligibility(false);
        return () => {
          ignore = true;
        };
      }

      setIsCheckingEligibility(true);
      getDebateEligibility()
        .then((result) => {
          if (ignore) return;
          setEligibility(result);
          if (!result.allowed) {
            setStatusText(result.reason ?? '현재 계정에서는 투기장을 이용할 수 없습니다.');
          } else {
            setStatusText('멘토와 주제를 고른 뒤 토론을 시작하세요.');
          }
        })
        .catch((error) => {
          if (!ignore) {
            setEligibility(null);
            setStatusText(getDebateApiErrorMessage(error, '투기장 권한을 확인하지 못했습니다.'));
          }
        })
        .finally(() => {
          if (!ignore) setIsCheckingEligibility(false);
        });

      listDebatePersonas()
        .then((items) => {
          if (ignore || items.length < 2) return;
          setPersonas(items);
          setSelectedFirstId((current) =>
            items.some((item) => item.id === current) ? current : (items[0]?.id ?? current),
          );
          setSelectedSecondId((current) =>
            items.some((item) => item.id === current) ? current : (items[1]?.id ?? current),
          );
        })
        .catch(() => {
          if (!ignore) setPersonas(FALLBACK_PERSONAS);
        });

      return () => {
        ignore = true;
      };
    }, [accessToken]),
  );

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    const eventName = Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow';
    const subscription = Keyboard.addListener(eventName, () => {
      scrollToInput();
    });

    return () => {
      subscription.remove();
    };
  }, [scrollToInput]);

  useEffect(() => {
    const streamUrl = routeParams?.replayStreamUrl;
    if (!streamUrl) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus('streaming');
    setStatusText('저장된 토론을 불러오고 있어요.');
    setDocuments([]);
    setTurns([]);

    streamDebate({ streamUrl, signal: controller.signal, onEvent: handleStreamEvent })
      .then(() => {
        if (abortRef.current === controller) {
          setStatus((current) => (current === 'error' ? current : 'done'));
          setStatusText('토론이 완료되었습니다.');
        }
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        if (abortRef.current === controller) {
          setStatus('error');
          setErrorMessage(getDebateApiErrorMessage(error, '토론을 불러오지 못했어요.'));
        }
      })
      .finally(() => {
        if (abortRef.current === controller) abortRef.current = null;
      });
  }, [routeParams?.replayStreamUrl]);

  function handleSelectPersona(personaId: string) {
    if (!activeSlot) {
      return;
    }

    if (activeSlot === 'first') {
      if (personaId === selectedSecondId) {
        Alert.alert(
          '멘토 선택',
          '1st player와 2nd player는 서로 다른 멘토여야 해요.',
        );
        return;
      }
      setSelectedFirstId(personaId);
    } else {
      if (personaId === selectedFirstId) {
        Alert.alert(
          '멘토 선택',
          '1st player와 2nd player는 서로 다른 멘토여야 해요.',
        );
        return;
      }
      setSelectedSecondId(personaId);
    }

    setActiveSlot(null);
  }

  async function handleStartDebate() {
    if (!canStart || isBusy) {
      if (!isAllowed) {
        setStatusText(eligibility?.reason ?? '투기장은 T2부터 이용할 수 있습니다.');
      }
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus('loading');
    setArenaView('debate');
    setActiveSlot(null);
    setStatusText('토론 세션을 준비하고 있어요.');
    setErrorMessage('');
    setResolvedTopic('');
    setDocuments([]);
    setTurns([]);

    try {
      const started = await startDebate({
        topic: topic.trim(),
        persona_a_id: firstPersona.id,
        persona_b_id: secondPersona.id,
      });

      setResolvedTopic(started.topic);
      setStatus('streaming');
      setStatusText('뉴스와 근거를 바탕으로 3턴 토론을 수신 중입니다.');

      await streamDebate({
        streamUrl: started.stream_url,
        signal: controller.signal,
        onEvent: handleStreamEvent,
      });

      if (abortRef.current === controller) {
        setStatus((current) => (current === 'error' ? current : 'done'));
        setStatusText('토론이 완료되었습니다.');
      }
    } catch (error) {
      if (controller.signal.aborted) {
        if (abortRef.current === controller) {
          setStatus('idle');
          setStatusText('토론 수신을 중단했습니다.');
        }
        return;
      }

      if (abortRef.current === controller) {
        setStatus('error');
        setErrorMessage(
          getDebateApiErrorMessage(
            error,
            '토론을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.',
          ),
        );
        setStatusText('토론을 시작하지 못했습니다.');
      }
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
      }
    }
  }

  function handleStreamEvent(event: DebateStreamEvent) {
    if (event.type === 'context') {
      setDocuments(event.documents);
      setStatusText(
        '관련 뉴스와 근거를 찾았어요. 멘토 발화를 생성 중입니다.',
      );
      return;
    }

    if (event.type === 'turn_start') {
      setTurns((current) =>
        upsertTurnStart(current, event.turn_index, event.turn_type, event.speaker),
      );
      setStatusText(`${event.speaker.name}의 의견을 수신 중입니다.`);
      return;
    }

    if (event.type === 'delta') {
      setTurns((current) => appendTurnDelta(current, event.turn_index, event.speaker, event.delta));
      return;
    }

    if (event.type === 'turn_done') {
      setTurns((current) =>
        current.map((turn) =>
          turn.turnIndex === event.turn_index ? { ...turn, isDone: true } : turn,
        ),
      );
      return;
    }

    if (event.type === 'done') {
      setStatus('done');
      setStatusText(
        event.replay
          ? '저장된 토론을 다시 불러왔어요.'
          : '토론이 완료되었습니다.',
      );
      return;
    }

    if (event.type === 'error') {
      setStatus('error');
      setErrorMessage(event.message);
      setStatusText('토론 생성 중 문제가 생겼습니다.');
    }
  }

  function handleStopDebate() {
    abortRef.current?.abort();
  }

  function handlePrimaryAction() {
    if (arenaView === 'debate' && status === 'done') {
      setArenaView('setup');
      setStatus('idle');
      setStatusText('멘토와 주제를 고른 뒤 토론을 시작하세요.');
      return;
    }

    void handleStartDebate();
  }

  function handleBackPress() {
    if (arenaView === 'debate') {
      if (isBusy) {
        abortRef.current?.abort();
      }
      setArenaView('setup');
      setStatus((current) => (current === 'streaming' || current === 'loading' ? 'idle' : current));
      setStatusText('멘토와 주제를 고른 뒤 토론을 시작하세요.');
      return;
    }

    navigation.navigate('MainTabs', { screen: 'Search', params: undefined });
  }

  return (
    <SafeAreaView style={styles.screen} edges={['top', 'left', 'right']}>
      {/* 고정 헤더 — 탐색/채팅 화면처럼 본문과 분리 */}
      <View style={styles.header}>
        <View style={styles.headerTextWrap}>
          <Text style={styles.title}>
            {'투기장'}
          </Text>
        </View>
        <TopIconBar />
      </View>

      <KeyboardAvoidingView
        behavior="padding"
        style={styles.keyboardView}
      >
        <ScrollView
          ref={scrollViewRef}
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* 본문 맨 위 안내 문구 */}
          <Text style={styles.subtitle}>{headerSubtitle}</Text>

          {arenaView === 'setup' ? (
            <SetupPanel
              activeSlot={activeSlot}
              firstPersona={firstPersona}
              isBusy={isBusy}
              personas={personas}
              secondPersona={secondPersona}
              selectedFirstId={selectedFirstId}
              selectedSecondId={selectedSecondId}
              isCheckingEligibility={isCheckingEligibility}
              statusText={statusText}
              topic={topic}
              tier={eligibility?.tier}
              onSelectPersona={handleSelectPersona}
              onSetActiveSlot={setActiveSlot}
              onSetTopic={setTopic}
              onTopicFocus={scrollToInput}
            />
          ) : (
            <DebatePanel
              documents={documents}
              errorMessage={errorMessage}
              isBusy={isBusy}
              progressWidth={progressWidth}
              resolvedTopic={resolvedTopic}
              statusText={statusText}
              turns={turns}
            />
          )}

          {/* 입장하기 버튼 — 스크롤 콘텐츠 맨 아래에 위치(끝까지 내리면 노출) */}
          <View style={styles.actionBar}>
            {isBusy ? (
              <Pressable onPress={handleStopDebate} style={styles.secondaryAction}>
                <Text style={styles.secondaryActionText}>중단</Text>
              </Pressable>
            ) : isStopped ? (
              <Pressable onPress={handleBackPress} style={styles.secondaryAction}>
                <Text style={styles.secondaryActionText}>나가기</Text>
              </Pressable>
            ) : null}
            <Pressable
              disabled={isPrimaryActionDisabled}
              onPress={handlePrimaryAction}
              style={[
                styles.primaryAction,
                isPrimaryActionDisabled && styles.primaryActionDisabled,
              ]}
            >
              <Text style={styles.primaryActionText}>
                {primaryActionLabel}
              </Text>
            </Pressable>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function SetupPanel({
  activeSlot,
  firstPersona,
  isBusy,
  personas,
  secondPersona,
  selectedFirstId,
  selectedSecondId,
  isCheckingEligibility,
  statusText,
  tier,
  topic,
  onSelectPersona,
  onSetActiveSlot,
  onSetTopic,
  onTopicFocus,
}: {
  activeSlot: PlayerSlot | null;
  firstPersona: DebatePersona;
  isBusy: boolean;
  personas: DebatePersona[];
  secondPersona: DebatePersona;
  selectedFirstId: string;
  selectedSecondId: string;
  isCheckingEligibility: boolean;
  statusText: string;
  tier?: string;
  topic: string;
  onSelectPersona: (personaId: string) => void;
  onSetActiveSlot: (slot: PlayerSlot | null) => void;
  onSetTopic: (topic: string) => void;
  onTopicFocus: () => void;
}) {
  return (
    <>
      <View style={styles.heroBand}>
        <Text style={styles.heroTitle}>멘토 대결 설정</Text>
        <Text style={styles.heroCopy}>
          주제 하나를 두고 서로 다른 투자 전략을 맞붙입니다.
        </Text>
      </View>

      {isCheckingEligibility ? (
        <View style={styles.lockedBanner}>
          <ActivityIndicator color={colors.primary} />
          <View style={styles.lockedTextGroup}>
            <Text style={styles.lockedTitle}>투기장 권한을 확인하고 있어요</Text>
            <Text style={styles.lockedDesc}>
              선택한 개발자 티어가 반영되는지 서버에서 다시 확인 중입니다.
            </Text>
          </View>
        </View>
      ) : tier === 'T1' ? (
        <View style={styles.lockedBanner}>
          <AppIcon color={colors.primary} name="lock" size={28} style={styles.lockedIcon} />
          <View style={styles.lockedTextGroup}>
            <Text style={styles.lockedTitle}>투기장은 T2부터 활성화됩니다</Text>
            <Text style={styles.lockedDesc}>
              학습 기록 탭에서 이해도 게이지를 80%까지 채우고 승급시험을 통과하면 투기장이 열립니다.
            </Text>
          </View>
        </View>
      ) : null}

      <Text style={styles.sectionTitle}>대결 멘토 선택</Text>
      <View style={styles.playersRow}>
        <PlayerCard
          isActive={activeSlot === 'first'}
          label="1st player"
          persona={firstPersona}
          onPress={() => onSetActiveSlot(activeSlot === 'first' ? null : 'first')}
        />
        <Text style={styles.vsText}>VS</Text>
        <PlayerCard
          isActive={activeSlot === 'second'}
          label="2nd player"
          persona={secondPersona}
          onPress={() => onSetActiveSlot(activeSlot === 'second' ? null : 'second')}
        />
      </View>

      {activeSlot ? (
        <View style={styles.mentorPicker}>
          <Text style={styles.pickerTitle}>
            {activeSlot === 'first' ? '1st player' : '2nd player'} 멘토 선택
          </Text>
          <View style={styles.mentorGrid}>
            {personas.map((persona) => {
              const isSelected =
                activeSlot === 'first'
                  ? selectedFirstId === persona.id
                  : selectedSecondId === persona.id;
              const isDisabled =
                activeSlot === 'first'
                  ? selectedSecondId === persona.id
                  : selectedFirstId === persona.id;

              return (
                <Pressable
                  key={persona.id}
                  disabled={isDisabled}
                  onPress={() => onSelectPersona(persona.id)}
                  style={[
                    styles.mentorOption,
                    isSelected && styles.mentorOptionSelected,
                    isDisabled && styles.mentorOptionDisabled,
                  ]}
                >
                  <Text
                    style={[
                      styles.mentorOptionName,
                      isSelected && styles.mentorOptionNameSelected,
                      isDisabled && styles.mentorOptionTextDisabled,
                    ]}
                  >
                    {persona.name}
                  </Text>
                  <Text
                    numberOfLines={2}
                    style={[
                      styles.mentorOptionStance,
                      isDisabled && styles.mentorOptionTextDisabled,
                    ]}
                  >
                    {persona.stance}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>
      ) : null}

      <Text style={styles.sectionTitle}>토론 주제</Text>
      <TextInput
        multiline
        editable={!isBusy}
        placeholder="예: 앞으로 우주테크 관련주의 전망"
        placeholderTextColor="#A4A9A5"
        style={styles.topicInput}
        value={topic}
        onChangeText={(value) => {
          onSetTopic(value);
          onTopicFocus();
        }}
        onContentSizeChange={() => onTopicFocus()}
        onFocus={onTopicFocus}
      />
      <View style={styles.topicChips}>
        {DEFAULT_TOPICS.map((sample) => (
          <Pressable
            key={sample}
            disabled={isBusy}
            onPress={() => onSetTopic(sample)}
            style={styles.topicChip}
          >
            <Text style={styles.topicChipText}>{sample}</Text>
          </Pressable>
        ))}
      </View>

      <View style={styles.setupStatusRow}>
        {tier ? <Text style={styles.tierBadge}>{tier}</Text> : null}
        <Text style={styles.setupStatus}>{statusText}</Text>
      </View>
    </>
  );
}

function DebatePanel({
  documents,
  errorMessage,
  isBusy,
  progressWidth,
  resolvedTopic,
  statusText,
  turns,
}: {
  documents: DebateDocument[];
  errorMessage: string;
  isBusy: boolean;
  progressWidth: `${number}%`;
  resolvedTopic: string;
  statusText: string;
  turns: DebateTurnMessage[];
}) {
  const isComplete = turns.length >= 3 && turns.every((turn) => turn.isDone);

  return (
    <>
      <View style={styles.progressTrack}>
        <View style={[styles.progressFill, { width: progressWidth }]} />
      </View>

      <View style={styles.statusPanel}>
        <View style={styles.statusTopRow}>
          <Text style={styles.statusText}>{statusText}</Text>
          {isBusy ? <ActivityIndicator color={colors.primary} /> : null}
        </View>
        {resolvedTopic ? (
          <Text style={styles.resolvedInline}>주제: {resolvedTopic}</Text>
        ) : null}
        {errorMessage ? <Text style={styles.errorText}>{errorMessage}</Text> : null}
      </View>

      {documents.length > 0 ? <EvidenceList documents={documents} /> : null}

      <View style={styles.turnList}>
        {turns.length === 0 ? (
          <View style={styles.waitingBox}>
            <Text style={styles.waitingText}>멘토 답변을 준비하고 있어요.</Text>
          </View>
        ) : (
          turns.map((turn) => <TurnBubble key={turn.turnIndex} turn={turn} />)
        )}
      </View>

      {isComplete ? <JudgmentPrompt /> : null}
    </>
  );
}

function JudgmentPrompt() {
  return (
    <View style={styles.judgmentPanel}>
      <Text style={styles.judgmentTitle}>판단 포인트</Text>
      <Text style={styles.judgmentText}>
        두 멘토가 같은 뉴스를 어떤 기준으로 다르게 해석했는지 비교해 보세요.
        근거, 시간축, 리스크 기준 중 어느 쪽이 내 판단에 더 설득력 있는지도
        함께 확인하면 좋아요.
      </Text>
      <Text style={styles.judgmentQuestion}>두 투자 철학의 차이를 이해했나요?</Text>
    </View>
  );
}

function PlayerCard({
  label,
  persona,
  isActive,
  onPress,
}: {
  label: string;
  persona: DebatePersona;
  isActive: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable onPress={onPress} style={[styles.playerCard, isActive && styles.playerCardActive]}>
      <View style={styles.avatarRing}>
        <View style={styles.avatarCore} />
      </View>
      <Text style={styles.playerLabel}>{label}</Text>
      <Text numberOfLines={1} style={styles.playerName}>
        {persona.name}
      </Text>
    </Pressable>
  );
}

function EvidenceList({ documents }: { documents: DebateDocument[] }) {
  const visibleDocuments = uniqueEvidenceDocuments(documents).slice(0, 3);

  if (visibleDocuments.length === 0) {
    return null;
  }

  return (
    <View style={styles.evidenceSection}>
      <Text style={styles.sectionTitle}>참고 뉴스</Text>
      {visibleDocuments.map((doc) => (
        <Pressable
          key={`${doc.id}-${doc.url}`}
          onPress={() => {
            if (doc.url) {
              void openInAppBrowser(doc.url);
            }
          }}
          style={styles.evidenceItem}
        >
          <Text numberOfLines={2} style={styles.evidenceTitle}>
            “{doc.title}”
          </Text>
          <Text style={styles.evidenceSource}>{doc.source || '뉴스'} 열기</Text>
        </Pressable>
      ))}
    </View>
  );
}

function uniqueEvidenceDocuments(documents: DebateDocument[]) {
  const seenUrls = new Set<string>();
  const seenTitles = new Set<string>();

  return documents.filter((doc) => {
    const title = doc.title.trim();
    if (!title) {
      return false;
    }

    const normalizedTitle = title.replace(/\s+/g, ' ').toLowerCase();
    const normalizedUrl = doc.url.trim();

    if (
      seenTitles.has(normalizedTitle) ||
      (normalizedUrl.length > 0 && seenUrls.has(normalizedUrl))
    ) {
      return false;
    }

    seenTitles.add(normalizedTitle);
    if (normalizedUrl.length > 0) {
      seenUrls.add(normalizedUrl);
    }

    return true;
  });
}

function TurnBubble({ turn }: { turn: DebateTurnMessage }) {
  const isFirstSide = turn.turnIndex !== 2;
  return (
    <View
      style={[
        styles.turnBubble,
        isFirstSide ? styles.turnBubblePrimary : styles.turnBubbleAccent,
      ]}
    >
      <View style={styles.turnMetaRow}>
        <Text
          style={[
            styles.turnBadge,
            isFirstSide ? styles.turnBadgePrimary : styles.turnBadgeAccent,
          ]}
        >
          {turn.speaker.name}
        </Text>
        <Text style={styles.turnTypeText}>{turnTypeLabel(turn.turnType)}</Text>
      </View>
      <Text style={styles.turnContent}>{turn.content || '답변을 수신하고 있어요.'}</Text>
    </View>
  );
}

function upsertTurnStart(
  turns: DebateTurnMessage[],
  turnIndex: number,
  turnType: DebateTurnType,
  speaker: DebateSpeaker,
): DebateTurnMessage[] {
  if (turns.some((turn) => turn.turnIndex === turnIndex)) {
    return turns;
  }

  return [...turns, { turnIndex, turnType, speaker, content: '', isDone: false }].sort(
    (left, right) => left.turnIndex - right.turnIndex,
  );
}

function appendTurnDelta(
  turns: DebateTurnMessage[],
  turnIndex: number,
  speaker: DebateSpeaker,
  delta: string,
): DebateTurnMessage[] {
  if (!turns.some((turn) => turn.turnIndex === turnIndex)) {
    const turnType = fallbackTurnType(turnIndex);

    return [
      ...turns,
      {
        turnIndex,
        turnType,
        speaker,
        content: delta,
        isDone: false,
      },
    ].sort((left, right) => left.turnIndex - right.turnIndex);
  }

  return turns.map((turn) =>
    turn.turnIndex === turnIndex ? { ...turn, content: turn.content + delta } : turn,
  );
}

function fallbackTurnType(turnIndex: number): DebateTurnType {
  if (turnIndex === 2) {
    return 'rebuttal';
  }
  if (turnIndex === 3) {
    return 'counter';
  }
  return 'opinion';
}

function turnTypeLabel(type: DebateTurnType): string {
  if (type === 'opinion') {
    return '주장';
  }
  if (type === 'rebuttal') {
    return '반박';
  }
  return '재반박';
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  keyboardView: {
    flex: 1,
  },
  content: {
    paddingHorizontal: 20,
    paddingTop: 14,
    // 입장하기 버튼이 하단 탭 카드에 가리지 않도록 카드 높이만큼 확보
    paddingBottom: 160,
    

  },
  header: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    // ScrollView 밖 고정 헤더 — 본문 padding과 좌우 정렬 맞춤
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 10,
  },
  backButton: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 12,
    borderWidth: 1,
    height: 44,
    justifyContent: 'center',
    width: 44,
  },
  backButtonText: {
    color: colors.muted,
    fontSize: 30,
    lineHeight: 32,
  },
  headerTextWrap: {
    flex: 1,
  },
  title: {
    color: colors.text,
    fontSize: 22,
    fontWeight: '900',
  },
  subtitle: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 19,
    // 본문 맨 위 안내 문구 — 아래 패널과 간격
    marginBottom: 16,
  },
  heroBand: {
    backgroundColor: colors.primary,
    borderRadius: 8,
    marginBottom: 22,
    paddingHorizontal: 20,
    paddingVertical: 22,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.12,
    shadowRadius: 18,
    elevation: 3,
  },
  heroTitle: {
    color: colors.surface,
    fontSize: 26,
    fontWeight: '900',
  },
  heroCopy: {
    color: '#DCEFE7',
    fontSize: 14,
    lineHeight: 21,
    marginTop: 6,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '900',
    marginBottom: 10,
  },
  playersRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 10,
    marginBottom: 18,
  },
  playerCard: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    flex: 1,
    minHeight: 156,
    padding: 14,
  },
  playerCardActive: {
    borderColor: colors.primary,
    borderWidth: 2,
  },
  avatarRing: {
    alignItems: 'center',
    backgroundColor: colors.primarySoft,
    borderRadius: 42,
    height: 72,
    justifyContent: 'center',
    marginBottom: 12,
    width: 72,
  },
  avatarCore: {
    backgroundColor: colors.background,
    borderRadius: 29,
    height: 58,
    width: 58,
  },
  playerLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '700',
    marginBottom: 4,
  },
  playerName: {
    color: colors.primary,
    fontSize: 15,
    fontWeight: '900',
    textAlign: 'center',
  },
  vsText: {
    color: colors.muted,
    fontSize: 25,
    fontWeight: '900',
    width: 34,
    textAlign: 'center',
  },
  mentorPicker: {
    marginBottom: 22,
  },
  pickerTitle: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: '800',
    marginBottom: 10,
  },
  mentorGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  mentorOption: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    minHeight: 120,
    padding: 14,
    width: '48%',
    justifyContent: 'center',
  },
  mentorOptionSelected: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
  },
  mentorOptionDisabled: {
    opacity: 0.45,
  },
  mentorOptionName: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '900',
    marginBottom: 5,
  },
  mentorOptionNameSelected: {
    color: colors.primary,
  },
  mentorOptionStance: {
    color: colors.muted,
    fontSize: 11,
    lineHeight: 16,
  },
  mentorOptionTextDisabled: {
    color: '#9DA39F',
  },
  topicInput: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    color: colors.text,
    fontSize: 15,
    lineHeight: 22,
    minHeight: 74,
    paddingHorizontal: 16,
    paddingVertical: 14,
    textAlignVertical: 'top',
  },
  topicChips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginBottom: 18,
    marginTop: 12,
  },
  topicChip: {
    backgroundColor: colors.primarySoft,
    borderColor: colors.primary,
    borderRadius: 99,
    borderWidth: 1,
    paddingHorizontal: 14,
    paddingVertical: 9,
  },
  topicChipText: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: '700',
  },
  setupStatusRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 8,
    marginTop: 2,
  },
  tierBadge: {
    backgroundColor: colors.accentSoft,
    borderColor: colors.accent,
    borderRadius: 6,
    borderWidth: 1,
    color: colors.text,
    fontSize: 12,
    fontWeight: '900',
    overflow: 'hidden',
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  setupStatus: {
    color: colors.muted,
    flex: 1,
    fontSize: 13,
    fontWeight: '700',
    lineHeight: 19,
  },
  lockedBanner: {
    alignItems: 'flex-start',
    backgroundColor: colors.accentSoft,
    borderColor: colors.accent,
    borderRadius: 16,
    borderWidth: 1,
    flexDirection: 'row',
    gap: 12,
    marginBottom: 8,
    padding: 16,
  },
  lockedIcon: {
    fontSize: 22,
  },
  lockedTextGroup: {
    flex: 1,
    gap: 6,
  },
  lockedTitle: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '800',
  },
  lockedDesc: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 19,
  },
  resolvedInline: {
    color: colors.text,
    fontSize: 13,
    fontWeight: '800',
    lineHeight: 19,
    marginTop: 8,
  },
  statusPanel: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    marginBottom: 20,
    padding: 14,
  },
  statusTopRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 10,
    justifyContent: 'space-between',
  },
  statusText: {
    color: colors.muted,
    flex: 1,
    fontSize: 13,
    fontWeight: '700',
    lineHeight: 19,
  },
  progressTrack: {
    backgroundColor: colors.border,
    borderRadius: 99,
    height: 5,
    marginTop: 12,
    overflow: 'hidden',
  },
  progressFill: {
    backgroundColor: colors.primary,
    borderRadius: 99,
    height: 5,
  },
  errorText: {
    color: colors.rose,
    fontSize: 13,
    fontWeight: '700',
    lineHeight: 19,
    marginTop: 10,
  },
  evidenceSection: {
    marginBottom: 20,
  },
  evidenceItem: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    marginBottom: 8,
    padding: 13,
  },
  evidenceTitle: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '800',
    lineHeight: 20,
  },
  evidenceSource: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '800',
    marginTop: 6,
  },
  turnList: {
    gap: 12,
  },
  waitingBox: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    minHeight: 120,
    justifyContent: 'center',
    padding: 18,
  },
  waitingText: {
    color: colors.muted,
    fontSize: 14,
    fontWeight: '800',
  },
  turnBubble: {
    borderRadius: 8,
    padding: 16,
  },
  turnBubblePrimary: {
    backgroundColor: colors.primarySoft,
  },
  turnBubbleAccent: {
    backgroundColor: colors.accentSoft,
  },
  turnMetaRow: {
    alignItems: 'center',
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 10,
  },
  turnBadge: {
    borderRadius: 6,
    color: colors.surface,
    fontSize: 12,
    fontWeight: '900',
    overflow: 'hidden',
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  turnBadgePrimary: {
    backgroundColor: colors.primary,
  },
  turnBadgeAccent: {
    backgroundColor: '#E6A820',
  },
  turnTypeText: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '800',
  },
  turnContent: {
    color: colors.text,
    fontSize: 15,
    lineHeight: 24,
  },
  judgmentPanel: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    marginTop: 16,
    padding: 16,
  },
  judgmentTitle: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: '900',
    marginBottom: 5,
  },
  judgmentText: {
    color: colors.text,
    fontSize: 13,
    lineHeight: 20,
  },
  judgmentQuestion: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: '900',
    lineHeight: 20,
    marginTop: 8,
  },
  actionBar: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 10,
    // 스크롤 콘텐츠 흐름 안에 위치 — 위 콘텐츠와 간격만 둠
    marginTop: 32,
  },
  primaryAction: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: 8,
    flex: 1,
    justifyContent: 'center',
    minHeight: 54,
  },
  primaryActionDisabled: {
    opacity: 0.45,
  },
  primaryActionText: {
    color: colors.surface,
    fontSize: 17,
    fontWeight: '900',
  },
  secondaryAction: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 54,
    paddingHorizontal: 18,
  },
  secondaryActionText: {
    color: colors.rose,
    fontSize: 15,
    fontWeight: '900',
  },
  bottomTab: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderTopWidth: 1,
    bottom: 0,
    flexDirection: 'row',
    height: 72,
    left: 0,
    paddingBottom: 8,
    paddingTop: 6,
    position: 'absolute',
    right: 0,
  },
  bottomTabItem: {
    alignItems: 'center',
    flex: 1,
    justifyContent: 'center',
  },
  bottomTabActiveBg: {
    alignItems: 'center',
    alignSelf: 'stretch',
    backgroundColor: colors.primarySoft,
    borderTopLeftRadius: 22,
    borderTopRightRadius: 22,
    flex: 1,
    justifyContent: 'center',
  },
  bottomTabIcon: {
    fontSize: 21,
    marginBottom: 2,
  },
  bottomTabText: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '800',
  },
  bottomTabActiveText: {
    color: colors.primary,
  },
});

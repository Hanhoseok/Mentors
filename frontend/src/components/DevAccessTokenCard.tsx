import { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { colors } from '@/constants/colors';
import { getAuthApiErrorMessage, issueDevAccessToken } from '@/features/auth/api';
import { useUserStore } from '@/store/userStore';
import { getAccessTokenPreview, normalizeAccessTokenInput } from '@/utils/devAccessToken';

export function DevAccessTokenCard() {
  const accessToken = useUserStore((state) => state.accessToken);
  const setAccessToken = useUserStore((state) => state.setAccessToken);
  const clearToken = useUserStore((state) => state.clearToken);
  const [draftToken, setDraftToken] = useState(accessToken ?? '');
  const [issueError, setIssueError] = useState<string | null>(null);
  const [issuedUserLabel, setIssuedUserLabel] = useState<string | null>(null);
  const [isIssuingToken, setIsIssuingToken] = useState(false);

  useEffect(() => {
    setDraftToken(accessToken ?? '');
  }, [accessToken]);

  const normalizedToken = useMemo(
    () => normalizeAccessTokenInput(draftToken),
    [draftToken],
  );

  if (!__DEV__) {
    return null;
  }

  function handleApplyToken() {
    if (!normalizedToken) {
      return;
    }

    setAccessToken(normalizedToken);
    setDraftToken(normalizedToken);
  }

  function handleClearToken() {
    clearToken();
    setDraftToken('');
    setIssueError(null);
    setIssuedUserLabel(null);
  }

  async function handleIssueToken() {
    setIsIssuingToken(true);
    setIssueError(null);

    try {
      const timestamp = Date.now();
      const response = await issueDevAccessToken({
        email: `frontend-dev+${timestamp}@local.test`,
        nickname: `frontend-${String(timestamp).slice(-6)}`,
      });

      setAccessToken(response.access_token);
      setDraftToken(response.access_token);
      setIssuedUserLabel(`${response.user.nickname} · ${response.user.email}`);
    } catch (error) {
      setIssueError(
        getAuthApiErrorMessage(
          error,
          '테스트 토큰을 발급하지 못했어요. 백엔드가 실행 중인지 확인해 주세요.',
        ),
      );
    } finally {
      setIsIssuingToken(false);
    }
  }

  return (
    <View style={styles.card}>
      <Text style={styles.eyebrow}>Developer Only</Text>
      <Text style={styles.title}>테스트용 액세스 토큰</Text>
      <Text style={styles.description}>
        로컬 확인 중에만 JWT를 붙여넣거나 새로 발급해서 growth API와 학습-성장 연결 흐름을 바로 확인할 수 있어요.
      </Text>

      <View style={styles.statusBox}>
        <Text style={styles.statusLabel}>현재 토큰</Text>
        <Text style={styles.statusValue}>{getAccessTokenPreview(accessToken)}</Text>
        {issuedUserLabel ? <Text style={styles.issuedUserText}>{issuedUserLabel}</Text> : null}
      </View>

      <TextInput
        autoCapitalize="none"
        autoCorrect={false}
        placeholder="Bearer eyJ..."
        placeholderTextColor={colors.muted}
        style={styles.input}
        value={draftToken}
        onChangeText={setDraftToken}
      />

      <Text style={styles.caption}>
        `Bearer` 접두어를 포함해서 붙여넣어도 자동으로 정리됩니다.
      </Text>

      {issueError ? <Text style={styles.errorText}>{issueError}</Text> : null}

      <View style={styles.actionRow}>
        <Pressable
          onPress={handleApplyToken}
          disabled={!normalizedToken}
          style={({ pressed }) => [
            styles.primaryButton,
            !normalizedToken && styles.buttonDisabled,
            pressed && normalizedToken && styles.buttonPressed,
          ]}
        >
          <Text style={styles.primaryButtonText}>토큰 적용</Text>
        </Pressable>

        <Pressable
          onPress={handleIssueToken}
          disabled={isIssuingToken}
          style={({ pressed }) => [
            styles.secondaryButton,
            isIssuingToken && styles.buttonDisabled,
            pressed && !isIssuingToken && styles.buttonPressed,
          ]}
        >
          <Text style={styles.secondaryButtonText}>
            {isIssuingToken ? '발급 중...' : '새 테스트 토큰'}
          </Text>
        </Pressable>
      </View>

      <View style={styles.actionRow}>
        <Pressable
          onPress={handleClearToken}
          disabled={!accessToken && !draftToken}
          style={({ pressed }) => [
            styles.ghostButton,
            !accessToken && !draftToken && styles.buttonDisabled,
            pressed && (accessToken || draftToken) && styles.buttonPressed,
          ]}
        >
          <Text style={styles.ghostButtonText}>토큰 제거</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 18,
    gap: 12,
  },
  eyebrow: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  title: {
    color: colors.text,
    fontSize: 18,
    fontWeight: '800',
  },
  description: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 21,
  },
  statusBox: {
    backgroundColor: colors.background,
    borderRadius: 16,
    paddingHorizontal: 14,
    paddingVertical: 12,
    gap: 4,
  },
  statusLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '600',
  },
  statusValue: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
  },
  issuedUserText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: '600',
    lineHeight: 18,
  },
  input: {
    minHeight: 52,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 16,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: colors.text,
    backgroundColor: colors.background,
    fontSize: 14,
  },
  caption: {
    color: colors.muted,
    fontSize: 12,
    lineHeight: 18,
  },
  errorText: {
    color: colors.rose,
    fontSize: 12,
    lineHeight: 18,
  },
  actionRow: {
    flexDirection: 'row',
    gap: 10,
  },
  primaryButton: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
    borderRadius: 16,
    minHeight: 48,
    paddingHorizontal: 14,
  },
  secondaryButton: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.accentSoft,
    borderRadius: 16,
    minHeight: 48,
    paddingHorizontal: 14,
  },
  primaryButtonText: {
    color: colors.surface,
    fontSize: 14,
    fontWeight: '700',
  },
  secondaryButtonText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
  },
  ghostButton: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    borderRadius: 16,
    minHeight: 48,
    paddingHorizontal: 14,
    borderColor: colors.border,
    borderWidth: 1,
  },
  ghostButtonText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
  },
  buttonDisabled: {
    opacity: 0.45,
  },
  buttonPressed: {
    opacity: 0.88,
  },
});

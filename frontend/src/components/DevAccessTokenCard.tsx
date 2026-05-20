import { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { colors } from '@/constants/colors';
import { useUserStore } from '@/store/userStore';
import { getAccessTokenPreview, normalizeAccessTokenInput } from '@/utils/devAccessToken';

export function DevAccessTokenCard() {
  const accessToken = useUserStore((state) => state.accessToken);
  const setAccessToken = useUserStore((state) => state.setAccessToken);
  const clearToken = useUserStore((state) => state.clearToken);
  const [draftToken, setDraftToken] = useState(accessToken ?? '');

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
  }

  return (
    <View style={styles.card}>
      <Text style={styles.eyebrow}>Developer Only</Text>
      <Text style={styles.title}>테스트용 액세스 토큰</Text>
      <Text style={styles.description}>
        로컬 확인 중에만 JWT를 붙여넣어 growth API와 승급시험 화면을 바로 확인할 수 있어요.
      </Text>

      <View style={styles.statusBox}>
        <Text style={styles.statusLabel}>현재 토큰</Text>
        <Text style={styles.statusValue}>{getAccessTokenPreview(accessToken)}</Text>
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
          onPress={handleClearToken}
          disabled={!accessToken && !draftToken}
          style={({ pressed }) => [
            styles.secondaryButton,
            !accessToken && !draftToken && styles.buttonDisabled,
            pressed && (accessToken || draftToken) && styles.buttonPressed,
          ]}
        >
          <Text style={styles.secondaryButtonText}>토큰 제거</Text>
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
  buttonDisabled: {
    opacity: 0.45,
  },
  buttonPressed: {
    opacity: 0.88,
  },
});

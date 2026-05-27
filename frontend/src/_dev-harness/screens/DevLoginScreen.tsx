import { useEffect, useMemo, useState } from 'react';
import {
  Linking,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors } from '@/constants/colors';
import { getAuthApiErrorMessage, localLogin, localSignup } from '@/features/auth/api';
import { useUserStore } from '@/store/userStore';
import {
  buildGoogleLoginStartUrl,
  buildLocalLoginPayload,
  buildLocalSignupPayload,
  buildTestAccountLoginPayload,
  DEV_LOCAL_TEST_ACCOUNT_EMAIL,
  EMPTY_AUTH_DRAFT,
  parseAuthCallbackParams,
  type AuthMode,
  validateAuthDraft,
} from '../auth/logic';

const AUTH_API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

function AuthTab({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.tabButton,
        selected && styles.tabButtonSelected,
        pressed && styles.buttonPressed,
      ]}
    >
      <Text style={[styles.tabButtonText, selected && styles.tabButtonTextSelected]}>{label}</Text>
    </Pressable>
  );
}

function getGoogleReturnToUrl(): string {
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    return window.location.href;
  }

  return 'mentors://auth';
}

export function DevLoginScreen() {
  const setAccessToken = useUserStore((state) => state.setAccessToken);
  const resetOnboarding = useUserStore((state) => state.resetOnboarding);
  const [mode, setMode] = useState<AuthMode>('login');
  const [draft, setDraft] = useState(EMPTY_AUTH_DRAFT);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRedirectingToGoogle, setIsRedirectingToGoogle] = useState(false);

  const isSignupMode = mode === 'signup';
  const googleLoginUrl = useMemo(
    () => buildGoogleLoginStartUrl(AUTH_API_BASE_URL, getGoogleReturnToUrl()),
    [],
  );

  useEffect(() => {
    if (Platform.OS !== 'web' || typeof window === 'undefined') {
      return;
    }

    const callback = parseAuthCallbackParams(window.location.search);
    if (!callback.token && !callback.error) {
      return;
    }

    const nextUrl = new URL(window.location.href);
    nextUrl.searchParams.delete('token');
    nextUrl.searchParams.delete('error');
    nextUrl.searchParams.delete('is_new');
    window.history.replaceState({}, '', nextUrl.toString());

    if (callback.error) {
      setErrorMessage(callback.error);
      setStatusMessage(null);
      setIsRedirectingToGoogle(false);
      return;
    }

    if (callback.token) {
      resetOnboarding();
      setAccessToken(callback.token);
      setErrorMessage(null);
      setStatusMessage(
        callback.isNew
          ? '구글 계정 연결이 완료됐어요. 온보딩으로 이동할게요.'
          : '구글 로그인에 성공했어요. 저장된 학습 상태를 확인할게요.',
      );
      setIsRedirectingToGoogle(false);
    }
  }, [resetOnboarding, setAccessToken]);

  function beginSession(token: string) {
    resetOnboarding();
    setAccessToken(token);
    setErrorMessage(null);
  }

  function handleSwitchMode(nextMode: AuthMode) {
    setMode(nextMode);
    setErrorMessage(null);
    setStatusMessage(null);
    setDraft((current) => ({
      ...current,
      password: '',
      passwordConfirm: '',
    }));
  }

  async function handleSubmit() {
    const validationMessage = validateAuthDraft(mode, draft);
    if (validationMessage) {
      setErrorMessage(validationMessage);
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    setStatusMessage(null);

    try {
      const response = isSignupMode
        ? await localSignup(buildLocalSignupPayload(draft))
        : await localLogin(buildLocalLoginPayload(draft));

      setStatusMessage(
        isSignupMode
          ? '회원가입이 완료됐어요. 바로 온보딩으로 이어집니다.'
          : '로그인에 성공했어요. 저장된 학습 상태를 확인할게요.',
      );
      beginSession(response.access_token);
    } catch (error) {
      setErrorMessage(
        getAuthApiErrorMessage(
          error,
          isSignupMode
            ? '회원가입에 실패했어요. 입력한 정보를 다시 확인해 주세요.'
            : '로그인에 실패했어요. 이메일과 비밀번호를 다시 확인해 주세요.',
        ),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleTestAccountLogin() {
    setIsSubmitting(true);
    setErrorMessage(null);
    setStatusMessage(null);

    try {
      const response = await localLogin(buildTestAccountLoginPayload());
      setStatusMessage('테스트 계정으로 바로 로그인했어요.');
      beginSession(response.access_token);
    } catch (error) {
      setErrorMessage(
        getAuthApiErrorMessage(
          error,
          '테스트 계정 로그인에 실패했어요. 백엔드 서버 상태를 확인해 주세요.',
        ),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleGoogleLogin() {
    setErrorMessage(null);
    setStatusMessage(null);
    setIsRedirectingToGoogle(true);

    try {
      if (Platform.OS === 'web' && typeof window !== 'undefined') {
        window.location.assign(googleLoginUrl);
        return;
      }

      await Linking.openURL(googleLoginUrl);
    } catch {
      setIsRedirectingToGoogle(false);
      setErrorMessage('구글 로그인 화면을 열지 못했어요. 다시 시도해 주세요.');
    }
  }

  return (
    <SafeAreaView style={styles.screen}>
      <ScrollView
        bounces={false}
        contentContainerStyle={styles.scrollContent}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.hero}>
          <View style={styles.logoCircle}>
            <Text style={styles.logoText}>M</Text>
          </View>
          <Text style={styles.heroTitle}>Mentors</Text>
          <Text style={styles.heroSubtitle}>경제 학습을 더 쉽게 시작하는 멘토형 투자 학습 앱</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>로그인 또는 회원가입</Text>
          <Text style={styles.cardDescription}>
            구글 계정으로 빠르게 시작하거나 이메일로 계정을 만들어 학습 기록을 이어갈 수 있어요.
          </Text>

          <Pressable
            disabled={isSubmitting || isRedirectingToGoogle}
            onPress={() => {
              void handleGoogleLogin();
            }}
            style={({ pressed }) => [
              styles.googleButton,
              (isSubmitting || isRedirectingToGoogle) && styles.buttonDisabled,
              pressed && !(isSubmitting || isRedirectingToGoogle) && styles.buttonPressed,
            ]}
          >
            <Text style={styles.googleButtonText}>
              {isRedirectingToGoogle ? '구글 로그인으로 이동 중...' : 'Google로 계속하기'}
            </Text>
          </Pressable>

          <View style={styles.dividerRow}>
            <View style={styles.dividerLine} />
            <Text style={styles.dividerText}>또는 이메일로 시작하기</Text>
            <View style={styles.dividerLine} />
          </View>

          <View style={styles.tabRow}>
            <AuthTab
              label="로그인"
              selected={!isSignupMode}
              onPress={() => handleSwitchMode('login')}
            />
            <AuthTab
              label="회원가입"
              selected={isSignupMode}
              onPress={() => handleSwitchMode('signup')}
            />
          </View>

          <View style={styles.fieldGroup}>
            <Text style={styles.fieldLabel}>이메일</Text>
            <TextInput
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              placeholder="email@example.com"
              placeholderTextColor="#AFB4B0"
              style={styles.input}
              value={draft.email}
              onChangeText={(email) => setDraft((current) => ({ ...current, email }))}
            />
          </View>

          <View style={styles.fieldGroup}>
            <Text style={styles.fieldLabel}>비밀번호</Text>
            <TextInput
              autoCapitalize="none"
              autoCorrect={false}
              secureTextEntry
              placeholder="8자 이상 입력"
              placeholderTextColor="#AFB4B0"
              style={styles.input}
              value={draft.password}
              onChangeText={(password) => setDraft((current) => ({ ...current, password }))}
            />
          </View>

          {isSignupMode ? (
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>비밀번호 확인</Text>
              <TextInput
                autoCapitalize="none"
                autoCorrect={false}
                secureTextEntry
                placeholder="비밀번호를 다시 입력"
                placeholderTextColor="#AFB4B0"
                style={styles.input}
                value={draft.passwordConfirm}
                onChangeText={(passwordConfirm) =>
                  setDraft((current) => ({ ...current, passwordConfirm }))
                }
              />
            </View>
          ) : null}

          {errorMessage ? <Text style={styles.errorText}>{errorMessage}</Text> : null}
          {statusMessage ? <Text style={styles.statusText}>{statusMessage}</Text> : null}

          <Pressable
            disabled={isSubmitting || isRedirectingToGoogle}
            onPress={() => {
              void handleSubmit();
            }}
            style={({ pressed }) => [
              styles.primaryButton,
              (isSubmitting || isRedirectingToGoogle) && styles.buttonDisabled,
              pressed && !(isSubmitting || isRedirectingToGoogle) && styles.buttonPressed,
            ]}
          >
            <Text style={styles.primaryButtonText}>
              {isSubmitting
                ? isSignupMode
                  ? '가입 중...'
                  : '로그인 중...'
                : isSignupMode
                  ? '회원가입'
                  : '로그인'}
            </Text>
          </Pressable>

          {!isSignupMode ? (
            <>
              <Pressable
                disabled={isSubmitting || isRedirectingToGoogle}
                onPress={() => {
                  void handleTestAccountLogin();
                }}
                style={({ pressed }) => [
                  styles.testAccountButton,
                  (isSubmitting || isRedirectingToGoogle) && styles.buttonDisabled,
                  pressed && !(isSubmitting || isRedirectingToGoogle) && styles.buttonPressed,
                ]}
              >
                <Text style={styles.testAccountButtonText}>테스트 계정으로 바로 로그인</Text>
              </Pressable>
              <Text style={styles.testAccountHint}>
                테스트 계정: {DEV_LOCAL_TEST_ACCOUNT_EMAIL}
              </Text>
            </>
          ) : null}

          <Pressable
            onPress={() => handleSwitchMode(isSignupMode ? 'login' : 'signup')}
            style={styles.switchRow}
          >
            <Text style={styles.switchLabel}>
              {isSignupMode ? '이미 계정이 있나요?' : '계정이 아직 없나요?'}
            </Text>
            <Text style={styles.switchAction}>{isSignupMode ? '로그인' : '회원가입'}</Text>
          </Pressable>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    flexGrow: 1,
    paddingBottom: 40,
  },
  hero: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    minHeight: 300,
    paddingHorizontal: 24,
    paddingTop: 76,
    paddingBottom: 118,
  },
  logoCircle: {
    alignItems: 'center',
    backgroundColor: '#19795F',
    borderRadius: 999,
    height: 80,
    justifyContent: 'center',
    marginBottom: 18,
    width: 80,
  },
  logoText: {
    color: colors.surface,
    fontSize: 30,
    fontWeight: '800',
  },
  heroTitle: {
    color: colors.surface,
    fontSize: 32,
    fontWeight: '800',
    lineHeight: 38,
  },
  heroSubtitle: {
    color: '#CCF2DE',
    fontSize: 13,
    fontWeight: '500',
    lineHeight: 20,
    marginTop: 10,
    textAlign: 'center',
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 24,
    marginHorizontal: 15,
    marginTop: -126,
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 28,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.06,
    shadowRadius: 24,
  },
  cardTitle: {
    color: colors.text,
    fontSize: 22,
    fontWeight: '800',
    lineHeight: 30,
  },
  cardDescription: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 21,
    marginTop: 8,
    marginBottom: 20,
  },
  googleButton: {
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderColor: colors.border,
    borderRadius: 14,
    borderWidth: 1,
    justifyContent: 'center',
    minHeight: 52,
    paddingHorizontal: 20,
  },
  googleButtonText: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
  },
  dividerRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 10,
    marginVertical: 18,
  },
  dividerLine: {
    backgroundColor: colors.border,
    flex: 1,
    height: 1,
  },
  dividerText: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '600',
  },
  tabRow: {
    backgroundColor: '#F2F4F2',
    borderRadius: 14,
    flexDirection: 'row',
    marginBottom: 20,
    padding: 4,
  },
  tabButton: {
    alignItems: 'center',
    borderRadius: 10,
    flex: 1,
    justifyContent: 'center',
    minHeight: 40,
  },
  tabButtonSelected: {
    backgroundColor: colors.surface,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 6,
  },
  tabButtonText: {
    color: colors.muted,
    fontSize: 14,
    fontWeight: '600',
  },
  tabButtonTextSelected: {
    color: colors.text,
    fontWeight: '700',
  },
  fieldGroup: {
    marginBottom: 16,
  },
  fieldLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '500',
    marginBottom: 8,
  },
  input: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 12,
    borderWidth: 1,
    color: colors.text,
    fontSize: 14,
    minHeight: 48,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  errorText: {
    color: colors.rose,
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 12,
  },
  statusText: {
    color: colors.primary,
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 12,
  },
  primaryButton: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: 14,
    justifyContent: 'center',
    minHeight: 52,
    paddingHorizontal: 20,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 12,
  },
  primaryButtonText: {
    color: colors.surface,
    fontSize: 16,
    fontWeight: '700',
  },
  testAccountButton: {
    alignItems: 'center',
    backgroundColor: colors.accentSoft,
    borderRadius: 14,
    justifyContent: 'center',
    minHeight: 48,
    marginTop: 10,
    paddingHorizontal: 20,
  },
  testAccountButtonText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: '700',
  },
  testAccountHint: {
    color: colors.muted,
    fontSize: 12,
    lineHeight: 18,
    marginTop: 10,
    textAlign: 'center',
  },
  switchRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 6,
    justifyContent: 'center',
    marginTop: 20,
  },
  switchLabel: {
    color: colors.muted,
    fontSize: 13,
  },
  switchAction: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: '700',
  },
  buttonDisabled: {
    opacity: 0.45,
  },
  buttonPressed: {
    opacity: 0.9,
  },
});

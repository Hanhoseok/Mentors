import { useEffect, useState } from 'react';
import {
  StyleSheet,
  Text,
  TextInput,
  View,
  Pressable,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Linking,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors } from '@/constants/colors';
import { useUserStore } from '@/store/userStore';
import { localLogin, issueDevAccessToken, getAuthApiErrorMessage } from '../api';
import type { AppStackParamList } from '@/navigation/types';

const apiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
const DEV_TIERS = ['T1', 'T2', 'T3', 'T4', 'T5'] as const;
type DevTier = (typeof DEV_TIERS)[number];

export function LoginScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<AppStackParamList>>();
  const setAccessToken = useUserStore((state) => state.setAccessToken);
  const resetOnboarding = useUserStore((state) => state.resetOnboarding);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [selectedDevTier, setSelectedDevTier] = useState<DevTier>('T2');

  // 구글 OAuth 콜백: ?token=<jwt> 파라미터가 URL에 있으면 자동 로그인 (웹 전용)
  useEffect(() => {
    if (Platform.OS !== 'web') return;
    if (typeof window === 'undefined') return;

    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    const oauthError = params.get('error');

    if (token) {
      // URL 파라미터 정리 후 로그인 처리
      window.history.replaceState({}, '', window.location.pathname);
      resetOnboarding();
      setAccessToken(token);
      return;
    }

    if (oauthError) {
      window.history.replaceState({}, '', window.location.pathname);
      setErrorMsg(`구글 로그인 실패: ${oauthError}`);
    }
  }, [resetOnboarding, setAccessToken]);

  async function handleDevBypass() {
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      const response = await issueDevAccessToken({
        email: 'dev-tier@local.test',
        nickname: 'tier-tester',
        tier: selectedDevTier,
      });
      resetOnboarding();
      setAccessToken(response.access_token);
    } catch {
      setErrorMsg('개발자 토큰 발급에 실패했습니다. 백엔드 서버를 확인해 주세요.');
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleGoogleLogin() {
    // 웹: 현재 URL을 return_to로 전달 → OAuth 완료 후 ?token= 파라미터와 함께 돌아옴
    if (Platform.OS === 'web' && typeof window !== 'undefined') {
      const returnTo = window.location.origin + window.location.pathname;
      window.location.href = `${apiBaseUrl}/auth/google/login?return_to=${encodeURIComponent(returnTo)}`;
      return;
    }
    // 모바일: 기본 브라우저로 열기 (딥링크 미설정 시 제한적)
    void Linking.openURL(`${apiBaseUrl}/auth/google/login`);
  }

  async function handleLogin() {
    const trimmedEmail = email.trim();
    const trimmedPassword = password.trim();

    if (!trimmedEmail || !trimmedPassword) {
      setErrorMsg('이메일과 비밀번호를 입력해 주세요.');
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      const response = await localLogin({
        email: trimmedEmail.toLowerCase(),
        password: trimmedPassword,
      });

      resetOnboarding();
      setAccessToken(response.access_token);
    } catch (error) {
      setErrorMsg(
        getAuthApiErrorMessage(
          error,
          '로그인에 실패했습니다. 이메일과 비밀번호를 다시 확인해 주세요.',
        ),
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <SafeAreaView style={styles.screen}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        <ScrollView
          bounces={false}
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* Top Forest Green Header */}
          <View style={styles.header}>
            <View style={styles.logoCircle} />
            <Text style={styles.appName}>Mentors</Text>
            <Text style={styles.appSubtitle}>막막한 당신을 위한 첫 번째 투자 전략</Text>
          </View>

          {/* Floating White Card */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>로그인</Text>

            {/* Email Field */}
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>이메일</Text>
              <TextInput
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="email-address"
                placeholder="email@example.com"
                placeholderTextColor="#A4A9A5"
                style={styles.input}
                value={email}
                onChangeText={setEmail}
              />
            </View>

            {/* Password Field */}
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>비밀번호</Text>
              <TextInput
                autoCapitalize="none"
                autoCorrect={false}
                secureTextEntry
                placeholder="••••••••"
                placeholderTextColor="#A4A9A5"
                style={styles.input}
                value={password}
                onChangeText={setPassword}
              />
            </View>

            {errorMsg ? <Text style={styles.errorText}>{errorMsg}</Text> : null}

            {/* Login Button */}
            <Pressable
              disabled={isSubmitting}
              onPress={handleLogin}
              style={({ pressed }) => [
                styles.submitButton,
                isSubmitting && styles.buttonDisabled,
                pressed && !isSubmitting && styles.buttonPressed,
              ]}
            >
              {isSubmitting ? (
                <ActivityIndicator color={colors.surface} />
              ) : (
                <Text style={styles.submitButtonText}>로그인</Text>
              )}
            </Pressable>

            {/* Divider */}
            <View style={styles.dividerRow}>
              <View style={styles.dividerLine} />
              <Text style={styles.dividerText}>또는</Text>
              <View style={styles.dividerLine} />
            </View>

            {/* Google Login Button */}
            <Pressable
              disabled={isSubmitting}
              onPress={handleGoogleLogin}
              style={({ pressed }) => [
                styles.googleButton,
                isSubmitting && styles.buttonDisabled,
                pressed && !isSubmitting && styles.buttonPressed,
              ]}
            >
              <Text style={styles.googleButtonIcon}>G</Text>
              <Text style={styles.googleButtonText}>구글로 로그인</Text>
            </Pressable>

            {/* Toggle Link */}
            <View style={styles.footerRow}>
              <Text style={styles.footerText}>계정이 없으신가요?</Text>
              <Pressable onPress={() => navigation.navigate('Signup')}>
                <Text style={styles.footerLink}>회원가입</Text>
              </Pressable>
            </View>

            {/* Developer Bypass */}
            <View style={styles.devTierPanel}>
              <Text style={styles.devTierLabel}>개발자 티어</Text>
              <View style={styles.devTierRow}>
                {DEV_TIERS.map((tier) => {
                  const selected = selectedDevTier === tier;
                  return (
                    <Pressable
                      key={tier}
                      disabled={isSubmitting}
                      onPress={() => setSelectedDevTier(tier)}
                      style={({ pressed }) => [
                        styles.devTierButton,
                        selected && styles.devTierButtonSelected,
                        pressed && !isSubmitting && styles.buttonPressed,
                      ]}
                    >
                      <Text
                        style={[
                          styles.devTierButtonText,
                          selected && styles.devTierButtonTextSelected,
                        ]}
                      >
                        {tier}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
              <Pressable
                disabled={isSubmitting}
                onPress={() => {
                  void handleDevBypass();
                }}
                style={({ pressed }) => [
                  styles.devBypassButton,
                  isSubmitting && styles.buttonDisabled,
                  pressed && !isSubmitting && styles.buttonPressed,
                ]}
              >
                <Text style={styles.devBypassButtonText}>
                  [개발자 모드] {selectedDevTier}로 로그인
                </Text>
              </Pressable>
            </View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    paddingBottom: 40,
  },
  header: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    paddingTop: 56,
    paddingBottom: 108,
    paddingHorizontal: 24,
  },
  logoCircle: {
    backgroundColor: 'rgba(255, 255, 255, 0.12)',
    borderRadius: 40,
    height: 80,
    marginBottom: 16,
    width: 80,
  },
  appName: {
    color: colors.surface,
    fontSize: 32,
    fontWeight: '800',
    lineHeight: 38,
  },
  appSubtitle: {
    color: 'rgba(255, 255, 255, 0.7)',
    fontSize: 13,
    fontWeight: '500',
    marginTop: 8,
    textAlign: 'center',
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 24,
    marginHorizontal: 16,
    marginTop: -60,
    paddingHorizontal: 24,
    paddingTop: 32,
    paddingBottom: 32,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.05,
    shadowRadius: 20,
    elevation: 3,
  },
  cardTitle: {
    color: colors.text,
    fontSize: 22,
    fontWeight: '800',
    marginBottom: 24,
  },
  fieldGroup: {
    marginBottom: 20,
  },
  fieldLabel: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 8,
  },
  input: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 12,
    borderWidth: 1,
    color: colors.text,
    fontSize: 14,
    height: 52,
    paddingHorizontal: 16,
  },
  errorText: {
    color: colors.rose,
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 16,
  },
  submitButton: {
    alignItems: 'center',
    backgroundColor: colors.primary,
    borderRadius: 12,
    height: 52,
    justifyContent: 'center',
    marginTop: 8,
    shadowColor: colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 2,
  },
  submitButtonText: {
    color: colors.surface,
    fontSize: 16,
    fontWeight: '700',
  },
  dividerRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 12,
    marginTop: 24,
    marginBottom: 4,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: colors.border,
  },
  dividerText: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '600',
  },
  googleButton: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 12,
    borderWidth: 1,
    flexDirection: 'row',
    height: 52,
    justifyContent: 'center',
    marginTop: 12,
    gap: 10,
  },
  googleButtonIcon: {
    color: '#4285F4',
    fontSize: 18,
    fontWeight: '900',
  },
  googleButtonText: {
    color: colors.text,
    fontSize: 15,
    fontWeight: '700',
  },
  footerRow: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: 24,
  },
  footerText: {
    color: colors.muted,
    fontSize: 14,
  },
  footerLink: {
    color: colors.primary,
    fontSize: 14,
    fontWeight: '700',
    marginLeft: 8,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonPressed: {
    opacity: 0.9,
  },
  devTierPanel: {
    backgroundColor: '#F2F4F2',
    borderRadius: 14,
    marginTop: 16,
    padding: 12,
  },
  devTierLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: '700',
    marginBottom: 8,
  },
  devTierRow: {
    flexDirection: 'row',
    gap: 6,
    marginBottom: 10,
  },
  devTierButton: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 10,
    borderWidth: 1,
    flex: 1,
    height: 38,
    justifyContent: 'center',
  },
  devTierButtonSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  devTierButtonText: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: '800',
  },
  devTierButtonTextSelected: {
    color: colors.surface,
  },
  devBypassButton: {
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderColor: '#E7EAE7',
    borderRadius: 12,
    borderWidth: 1,
    height: 48,
    justifyContent: 'center',
  },
  devBypassButtonText: {
    color: colors.muted,
    fontSize: 13,
    fontWeight: '700',
  },
});

import { useState } from 'react';
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
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors } from '@/constants/colors';
import { useUserStore } from '@/store/userStore';
import { localSignup, getAuthApiErrorMessage } from '../api';
import type { AppStackParamList } from '@/navigation/types';

export function SignupScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<AppStackParamList>>();
  const setAccessToken = useUserStore((state) => state.setAccessToken);
  const resetOnboarding = useUserStore((state) => state.resetOnboarding);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  async function handleSignup() {
    const trimmedEmail = email.trim();
    const trimmedPassword = password.trim();
    const trimmedConfirm = passwordConfirm.trim();

    if (!trimmedEmail || !trimmedPassword || !trimmedConfirm) {
      setErrorMsg('모든 필드를 입력해 주세요.');
      return;
    }

    if (trimmedPassword.length < 8) {
      setErrorMsg('비밀번호는 8자 이상이어야 합니다.');
      return;
    }

    if (trimmedPassword !== trimmedConfirm) {
      setErrorMsg('비밀번호가 일치하지 않습니다.');
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      const response = await localSignup({
        email: trimmedEmail.toLowerCase(),
        password: trimmedPassword,
        password_confirm: trimmedConfirm,
      });

      resetOnboarding();
      setAccessToken(response.access_token);
    } catch (error) {
      setErrorMsg(
        getAuthApiErrorMessage(error, '회원가입에 실패했습니다. 입력한 정보를 다시 확인해 주세요.'),
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
          {/* Top Forest Green Header (No Logo Circle) */}
          <View style={styles.header}>
            <Text style={styles.appName}>Mentors</Text>
            <Text style={styles.appSubtitle}>막막한 당신을 위한 첫 번째 투자 전략</Text>
          </View>

          {/* Floating White Card */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>회원가입</Text>

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

            {/* Password Confirm Field */}
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>비밀번호 확인</Text>
              <TextInput
                autoCapitalize="none"
                autoCorrect={false}
                secureTextEntry
                placeholder="••••••••"
                placeholderTextColor="#A4A9A5"
                style={styles.input}
                value={passwordConfirm}
                onChangeText={setPasswordConfirm}
              />
            </View>

            {errorMsg ? <Text style={styles.errorText}>{errorMsg}</Text> : null}

            {/* Signup Button */}
            <Pressable
              disabled={isSubmitting}
              onPress={handleSignup}
              style={({ pressed }) => [
                styles.submitButton,
                isSubmitting && styles.buttonDisabled,
                pressed && !isSubmitting && styles.buttonPressed,
              ]}
            >
              {isSubmitting ? (
                <ActivityIndicator color={colors.surface} />
              ) : (
                <Text style={styles.submitButtonText}>회원가입</Text>
              )}
            </Pressable>

            {/* Toggle Link */}
            <View style={styles.footerRow}>
              <Text style={styles.footerText}>이미 계정이 있으신가요?</Text>
              <Pressable onPress={() => navigation.navigate('Login')}>
                <Text style={styles.footerLink}>로그인</Text>
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
    paddingTop: 80,
    paddingBottom: 108,
    paddingHorizontal: 24,
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
});

import { StyleSheet, Text, View, Pressable } from 'react-native';
import { useUserStore } from '@/store/userStore';
import { colors } from '@/constants/colors';

export function HomeScreen() {
  const clearToken = useUserStore((state) => state.clearToken);
  const resetOnboarding = useUserStore((state) => state.resetOnboarding);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>멘토스 홈 (개발 예정)</Text>
      <Text style={styles.description}>
        진짜 프론트엔드의 메인 홈 화면이 렌더링될 자리입니다. 현재 온보딩 완료 처리가 되어 이
        페이지에 성공적으로 연결되었습니다.
      </Text>

      <Pressable onPress={resetOnboarding} style={styles.primaryButton}>
        <Text style={styles.primaryButtonText}>온보딩 다시하기</Text>
      </Pressable>

      <Pressable onPress={clearToken} style={styles.secondaryButton}>
        <Text style={styles.secondaryButtonText}>로그아웃</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  title: {
    color: colors.text,
    fontSize: 24,
    fontWeight: '800',
    marginBottom: 16,
    textAlign: 'center',
  },
  description: {
    color: colors.muted,
    fontSize: 14,
    lineHeight: 22,
    textAlign: 'center',
    marginBottom: 32,
  },
  primaryButton: {
    backgroundColor: colors.primary,
    paddingVertical: 14,
    paddingHorizontal: 28,
    borderRadius: 12,
    width: '100%',
    alignItems: 'center',
    marginBottom: 12,
  },
  primaryButtonText: {
    color: colors.surface,
    fontSize: 16,
    fontWeight: '700',
  },
  secondaryButton: {
    borderColor: colors.border,
    borderWidth: 1,
    paddingVertical: 14,
    paddingHorizontal: 28,
    borderRadius: 12,
    width: '100%',
    alignItems: 'center',
  },
  secondaryButtonText: {
    color: colors.muted,
    fontSize: 16,
    fontWeight: '700',
  },
});

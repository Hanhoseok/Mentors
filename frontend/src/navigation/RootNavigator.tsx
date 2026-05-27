import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useUserStore } from '@/store/userStore';
import { LoginScreen } from '../features/auth/screens/LoginScreen';
import { SignupScreen } from '../features/auth/screens/SignupScreen';
import { OnboardingScreen } from '../features/onboarding/screens/OnboardingScreen';
import { SearchScreen } from '../features/explore/screens/SearchScreen';
import { NewsDetailScreen } from '../features/explore/screens/NewsDetailScreen';
import type { AppStackParamList } from './types';

const Stack = createNativeStackNavigator<AppStackParamList>();

export function RootNavigator() {
  const accessToken = useUserStore((state) => state.accessToken);
  const hasCompletedOnboarding = useUserStore((state) => state.hasCompletedOnboarding);

  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      {!accessToken ? (
        <>
          <Stack.Screen name="Login" component={LoginScreen} />
          <Stack.Screen name="Signup" component={SignupScreen} />
        </>
      ) : !hasCompletedOnboarding ? (
        <Stack.Screen name="Onboarding" component={OnboardingScreen} />
      ) : (
        <>
          <Stack.Screen name="Search" component={SearchScreen} />
          <Stack.Screen name="NewsDetail" component={NewsDetailScreen} />
        </>
      )}
    </Stack.Navigator>
  );
}

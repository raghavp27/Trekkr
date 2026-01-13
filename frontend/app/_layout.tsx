import { Stack, useRouter, useSegments } from "expo-router";
import { useEffect } from "react";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { ActivityIndicator, View, StyleSheet } from "react-native";
import { useColorScheme } from "@/hooks/use-color-scheme";
import { Colors } from "@/constants/theme";
import { locationPreferencesStorage, tokenStorage } from "@/services/storage";
import { resumeLocationTrackingIfPossible } from "@/services/locationTracking";

function RootLayoutNav() {
  const { isAuthenticated, isLoading } = useAuth();
  const segments = useSegments();
  const router = useRouter();
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];

  useEffect(() => {
    if (isLoading) return;

    const isAuthScreen = segments[0] === 'login' || segments[0] === 'signup' || segments[0] === 'forgot-password' || segments[0] === 'reset-password';

    if (!isAuthenticated && !isAuthScreen) {
      router.replace('/login');
    } else if (isAuthenticated && isAuthScreen) {
      router.replace('/(tabs)');
    }
  }, [isAuthenticated, isLoading, router, segments]);

  useEffect(() => {
    if (isLoading) return;

    // Best-effort auto-resume: only start tracking if the user previously enabled it
    // and we have an access token. (If permissions aren't granted, startLocationTracking
    // will return false without crashing.)
    (async () => {
      try {
        if (!isAuthenticated) return;
        const enabled = await locationPreferencesStorage.isLocationTrackingEnabled();
        if (!enabled) return;

        const accessToken = await tokenStorage.getAccessToken();
        if (!accessToken) return;

        await resumeLocationTrackingIfPossible();
      } catch {
        // Silent fail: app should still load even if tracking can't resume.
      }
    })();
  }, [isAuthenticated, isLoading]);

  if (isLoading) {
    return (
      <View style={[styles.loadingContainer, { backgroundColor: colors.background }]}>
        <ActivityIndicator size="large" color={colors.tint} />
      </View>
    );
  }

  return <Stack screenOptions={{ headerShown: false }} />;
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <RootLayoutNav />
    </AuthProvider>
  );
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
});

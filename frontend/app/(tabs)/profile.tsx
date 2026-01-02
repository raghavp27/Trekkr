import { useEffect, useState, useCallback } from "react";
import { View, Text, StyleSheet, TouchableOpacity, Alert, ScrollView, RefreshControl, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useAuth } from "@/contexts/AuthContext";
import { useColorScheme } from "@/hooks/use-color-scheme";
import { Colors } from "@/constants/theme";
import { Ionicons } from "@expo/vector-icons";
import { getStatsOverview, StatsOverviewResponse } from "@/services/api";
import { tokenStorage } from "@/services/storage";

export default function ProfileScreen() {
  const { user, logout } = useAuth();
  const colorScheme = useColorScheme();
  const colors = Colors[colorScheme ?? 'light'];
  const [stats, setStats] = useState<StatsOverviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchStats = useCallback(async () => {
    try {
      const token = await tokenStorage.getAccessToken();
      if (token) {
        const data = await getStatsOverview(token);
        setStats(data);
      }
    } catch (error) {
      console.error("Failed to fetch stats:", error);
    } finally {
      setIsLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    fetchStats();
  }, [fetchStats]);

  const handleLogout = () => {
    Alert.alert(
      "Logout",
      "Are you sure you want to logout?",
      [
        {
          text: "Cancel",
          style: "cancel",
        },
        {
          text: "Logout",
          style: "destructive",
          onPress: async () => {
            try {
              await logout();
            } catch (error) {
              Alert.alert("Error", "Failed to logout");
            }
          },
        },
      ]
    );
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return "Never";
    return new Date(dateString).toLocaleDateString();
  };

  if (!user) {
    return (
      <View style={[styles.container, { backgroundColor: colors.background }]}>
        <Text style={[styles.text, { color: colors.text }]}>No user data</Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.tint} />
        }
      >
        <View style={styles.content}>
        {/* Profile Header */}
        <View style={[styles.profileHeader, { borderBottomColor: colors.icon + '30' }]}>
          <View style={[styles.avatar, { backgroundColor: colors.tint }]}>
            <Ionicons name="person" size={40} color="#fff" />
          </View>
          <Text style={[styles.username, { color: colors.text }]}>
            {user.username}
          </Text>
          <Text style={[styles.memberSince, { color: colors.icon }]}>
            Trekking since {new Date(user.created_at).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}
          </Text>
        </View>

        {/* Stats Section */}
        {isLoading ? (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="small" color={colors.tint} />
          </View>
        ) : stats ? (
          <>
            {/* Stats Grid */}
            <View style={styles.statsGrid}>
              <View style={[styles.statCard, { backgroundColor: colors.background, borderColor: colors.icon + '30' }]}>
                <Ionicons name="globe-outline" size={24} color={colors.tint} />
                <Text style={[styles.statNumber, { color: colors.text }]}>
                  {stats.stats.countries_visited}
                </Text>
                <Text style={[styles.statLabel, { color: colors.icon }]}>Countries</Text>
              </View>
              <View style={[styles.statCard, { backgroundColor: colors.background, borderColor: colors.icon + '30' }]}>
                <Ionicons name="map-outline" size={24} color={colors.tint} />
                <Text style={[styles.statNumber, { color: colors.text }]}>
                  {stats.stats.regions_visited}
                </Text>
                <Text style={[styles.statLabel, { color: colors.icon }]}>Regions</Text>
              </View>
              <View style={[styles.statCard, { backgroundColor: colors.background, borderColor: colors.icon + '30' }]}>
                <Ionicons name="grid-outline" size={24} color={colors.tint} />
                <Text style={[styles.statNumber, { color: colors.text }]}>
                  {stats.stats.cells_visited_res8}
                </Text>
                <Text style={[styles.statLabel, { color: colors.icon }]}>Areas</Text>
              </View>
            </View>

            {/* Recent Countries */}
            {stats.recent_countries.length > 0 && (
              <View style={styles.recentSection}>
                <Text style={[styles.sectionTitle, { color: colors.text }]}>
                  Recent Countries
                </Text>
                {stats.recent_countries.map((country, index) => (
                  <View
                    key={country.code}
                    style={[
                      styles.recentItem,
                      { borderBottomColor: colors.icon + '30' },
                      index === stats.recent_countries.length - 1 && styles.lastItem
                    ]}
                  >
                    <View style={styles.recentItemLeft}>
                      <Ionicons name="flag-outline" size={20} color={colors.tint} />
                      <Text style={[styles.recentItemName, { color: colors.text }]}>
                        {country.name}
                      </Text>
                    </View>
                    <Text style={[styles.recentItemDate, { color: colors.icon }]}>
                      {formatDate(country.visited_at)}
                    </Text>
                  </View>
                ))}
              </View>
            )}

            {/* Recent Regions */}
            {stats.recent_regions.length > 0 && (
              <View style={styles.recentSection}>
                <Text style={[styles.sectionTitle, { color: colors.text }]}>
                  Recent Regions
                </Text>
                {stats.recent_regions.map((region, index) => (
                  <View
                    key={region.code}
                    style={[
                      styles.recentItem,
                      { borderBottomColor: colors.icon + '30' },
                      index === stats.recent_regions.length - 1 && styles.lastItem
                    ]}
                  >
                    <View style={styles.recentItemLeft}>
                      <Ionicons name="location-outline" size={20} color={colors.tint} />
                      <View>
                        <Text style={[styles.recentItemName, { color: colors.text }]}>
                          {region.name}
                        </Text>
                        <Text style={[styles.recentItemSubtitle, { color: colors.icon }]}>
                          {region.country_name}
                        </Text>
                      </View>
                    </View>
                    <Text style={[styles.recentItemDate, { color: colors.icon }]}>
                      {formatDate(region.visited_at)}
                    </Text>
                  </View>
                ))}
              </View>
            )}

            </>
        ) : (
          <View style={styles.emptyStats}>
            <Ionicons name="compass-outline" size={48} color={colors.icon} />
            <Text style={[styles.emptyStatsText, { color: colors.icon }]}>
              Start exploring to see your stats!
            </Text>
          </View>
        )}

        <TouchableOpacity
          style={styles.logoutButton}
          onPress={handleLogout}
        >
          <Ionicons name="log-out-outline" size={20} color="#ef4444" style={styles.logoutIcon} />
          <Text style={styles.logoutButtonText}>Logout</Text>
        </TouchableOpacity>
      </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
  },
  content: {
    flex: 1,
    padding: 24,
  },
  profileHeader: {
    alignItems: "center",
    paddingBottom: 24,
    borderBottomWidth: 1,
    marginBottom: 24,
  },
  avatar: {
    width: 80,
    height: 80,
    borderRadius: 40,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 16,
  },
  username: {
    fontSize: 24,
    fontWeight: "bold",
    marginBottom: 4,
  },
  memberSince: {
    fontSize: 14,
  },
  loadingContainer: {
    padding: 40,
    alignItems: "center",
  },
  statsGrid: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 24,
  },
  statCard: {
    flex: 1,
    alignItems: "center",
    padding: 16,
    marginHorizontal: 4,
    borderRadius: 12,
    borderWidth: 1,
  },
  statNumber: {
    fontSize: 28,
    fontWeight: "bold",
    marginTop: 8,
  },
  statLabel: {
    fontSize: 12,
    marginTop: 4,
  },
  recentSection: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "600",
    marginBottom: 12,
  },
  recentItem: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 12,
    borderBottomWidth: 1,
  },
  lastItem: {
    borderBottomWidth: 0,
  },
  recentItemLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  recentItemName: {
    fontSize: 16,
    fontWeight: "500",
  },
  recentItemSubtitle: {
    fontSize: 13,
    marginTop: 2,
  },
  recentItemDate: {
    fontSize: 14,
  },
  emptyStats: {
    alignItems: "center",
    padding: 40,
  },
  emptyStatsText: {
    fontSize: 16,
    marginTop: 16,
    textAlign: "center",
  },
  logoutButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    height: 50,
    borderRadius: 8,
    marginTop: "auto",
    borderWidth: 1,
    borderColor: "#ef4444",
  },
  logoutIcon: {
    marginRight: 8,
  },
  logoutButtonText: {
    color: "#ef4444",
    fontSize: 16,
    fontWeight: "600",
  },
  text: {
    fontSize: 16,
  },
});

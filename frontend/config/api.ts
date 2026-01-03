import { Platform } from "react-native";

// Determine the correct base URL based on platform and environment
function getApiBaseUrl(): string {
    if (__DEV__) {
        // Development mode
        if (Platform.OS === "android") {
            // Android emulator uses 10.0.2.2 to access host machine's localhost
            return "http://10.0.2.2:8000";
        } else if (Platform.OS === "ios") {
            // Physical iOS device needs computer's IP address
            return "http://192.168.0.112:8000";
        } else {
            // Web or other platforms
            return "http://localhost:8000";
        }
    } else {
        // Production mode - update with your production API URL
        return "https://your-production-api.com";
    }
}

export const API_BASE_URL = getApiBaseUrl();

export const API_ENDPOINTS = {
    AUTH: {
        REGISTER: "/api/auth/register",
        LOGIN: "/api/auth/login",
        LOGOUT: "/api/auth/logout",
        REFRESH: "/api/auth/refresh",
        ME: "/api/auth/me",
        FORGOT_PASSWORD: "/api/auth/forgot-password",
        RESET_PASSWORD: "/api/auth/reset-password",
        CHANGE_PASSWORD: "/api/auth/change-password",
        DELETE_ACCOUNT: "/api/auth/account",
    },
    MAP: {
        SUMMARY: "/api/v1/map/summary",
        CELLS: "/api/v1/map/cells",
        POLYGONS: "/api/v1/map/polygons",
        POLYGONS_COUNTRIES: "/api/v1/map/polygons/countries",
        POLYGONS_STATES: "/api/v1/map/polygons/states",
    },
    LOCATION: {
        INGEST: "/api/v1/location/ingest",
        INGEST_SIMPLE: "/api/v1/location/ingest/simple",
    },
    STATS: {
        OVERVIEW: "/api/v1/stats/overview",
        COUNTRIES: "/api/v1/stats/countries",
        REGIONS: "/api/v1/stats/regions",
    },
    ACHIEVEMENTS: {
        LIST: "/api/v1/achievements",
        UNLOCKED: "/api/v1/achievements/unlocked",
    },
} as const;





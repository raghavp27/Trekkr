import * as SecureStore from 'expo-secure-store';

const STORAGE_KEYS = {
    ACCESS_TOKEN: 'access_token',
    REFRESH_TOKEN: 'refresh_token',
    USER: 'user',
    LOCATION_TRACKING_ENABLED: 'location_tracking_enabled',
} as const;

export const tokenStorage = {
    async getAccessToken(): Promise<string | null> {
        try {
            return await SecureStore.getItemAsync(STORAGE_KEYS.ACCESS_TOKEN);
        } catch (error) {
            return null;
        }
    },

    async getRefreshToken(): Promise<string | null> {
        try {
            return await SecureStore.getItemAsync(STORAGE_KEYS.REFRESH_TOKEN);
        } catch (error) {
            return null;
        }
    },

    async setTokens(accessToken: string, refreshToken: string): Promise<void> {
        await Promise.all([
            SecureStore.setItemAsync(STORAGE_KEYS.ACCESS_TOKEN, accessToken),
            SecureStore.setItemAsync(STORAGE_KEYS.REFRESH_TOKEN, refreshToken),
        ]);
    },

    async clearTokens(): Promise<void> {
        await Promise.all([
            SecureStore.deleteItemAsync(STORAGE_KEYS.ACCESS_TOKEN),
            SecureStore.deleteItemAsync(STORAGE_KEYS.REFRESH_TOKEN),
            SecureStore.deleteItemAsync(STORAGE_KEYS.USER),
        ]);
    },
};

export const userStorage = {
    async getUser(): Promise<any | null> {
        try {
            const userJson = await SecureStore.getItemAsync(STORAGE_KEYS.USER);
            return userJson ? JSON.parse(userJson) : null;
        } catch (error) {
            return null;
        }
    },

    async setUser(user: any): Promise<void> {
        await SecureStore.setItemAsync(STORAGE_KEYS.USER, JSON.stringify(user));
    },

    async clearUser(): Promise<void> {
        await SecureStore.deleteItemAsync(STORAGE_KEYS.USER);
    },
};

export const locationPreferencesStorage = {
    async isLocationTrackingEnabled(): Promise<boolean> {
        try {
            const value = await SecureStore.getItemAsync(STORAGE_KEYS.LOCATION_TRACKING_ENABLED);
            return value === 'true';
        } catch {
            return false;
        }
    },

    async setLocationTrackingEnabled(enabled: boolean): Promise<void> {
        await SecureStore.setItemAsync(
            STORAGE_KEYS.LOCATION_TRACKING_ENABLED,
            enabled ? 'true' : 'false'
        );
    },
};





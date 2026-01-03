import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { UserResponse } from '@/services/api';
import * as api from '@/services/api';
import { tokenStorage, userStorage } from '@/services/storage';

interface AuthContextType {
    user: UserResponse | null;
    isLoading: boolean;
    isAuthenticated: boolean;
    login: (username: string, password: string) => Promise<void>;
    register: (email: string, username: string, password: string) => Promise<void>;
    logout: () => Promise<void>;
    refreshAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<UserResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        initializeAuth();
    }, []);

    async function initializeAuth() {
        try {
            const accessToken = await tokenStorage.getAccessToken();
            if (accessToken) {
                try {
                    const userData = await api.getCurrentUser(accessToken);
                    setUser(userData);
                    await userStorage.setUser(userData);
                } catch (error) {
                    await tryRefreshToken();
                }
            }
        } catch (error) {
            console.error('Error initializing auth:', error);
        } finally {
            setIsLoading(false);
        }
    }

    async function tryRefreshToken() {
        try {
            const refreshToken = await tokenStorage.getRefreshToken();
            if (refreshToken) {
                const tokens = await api.refreshToken(refreshToken);
                await tokenStorage.setTokens(tokens.access_token, tokens.refresh_token);
                const userData = await api.getCurrentUser(tokens.access_token);
                setUser(userData);
                await userStorage.setUser(userData);
            }
        } catch (error) {
            await tokenStorage.clearTokens();
            await userStorage.clearUser();
            setUser(null);
        }
    }

    async function login(username: string, password: string) {
        const tokens = await api.login({ username, password });
        await tokenStorage.setTokens(tokens.access_token, tokens.refresh_token);
        const userData = await api.getCurrentUser(tokens.access_token);
        setUser(userData);
        await userStorage.setUser(userData);
    }

    async function register(email: string, username: string, password: string) {
        const tokens = await api.register({ email, username, password });
        await tokenStorage.setTokens(tokens.access_token, tokens.refresh_token);
        const userData = await api.getCurrentUser(tokens.access_token);
        setUser(userData);
        await userStorage.setUser(userData);
    }

    async function logout() {
        try {
            const accessToken = await tokenStorage.getAccessToken();
            if (accessToken) {
                await api.logout(accessToken);
            }
        } catch (error) {
            // Continue with logout even if API call fails
        } finally {
            await tokenStorage.clearTokens();
            await userStorage.clearUser();
            setUser(null);
        }
    }

    async function refreshAuth() {
        await tryRefreshToken();
    }

    const value: AuthContextType = {
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        register,
        logout,
        refreshAuth,
    };

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}





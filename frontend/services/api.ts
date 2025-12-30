import { API_BASE_URL, API_ENDPOINTS } from '@/config/api';

export interface TokenResponse {
    access_token: string;
    refresh_token: string;
    token_type: string;
}

export interface UserResponse {
    id: number;
    email: string;
    username: string;
    created_at: string;
}

export interface RegisterData {
    email: string;
    username: string;
    password: string;
}

export interface LoginData {
    username: string;
    password: string;
}

export interface ApiError {
    detail: string;
}

async function apiRequest<T>(
    endpoint: string,
    options: RequestInit = {}
): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;

    const response = await fetch(url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
    });

    if (!response.ok) {
        const error: ApiError = await response.json().catch(() => ({
            detail: `HTTP ${response.status}: ${response.statusText}`,
        }));
        throw new Error(error.detail || 'An error occurred');
    }

    return response.json();
}

export async function authenticatedRequest<T>(
    endpoint: string,
    accessToken: string,
    options: RequestInit = {}
): Promise<T> {
    return apiRequest<T>(endpoint, {
        ...options,
        headers: {
            Authorization: `Bearer ${accessToken}`,
            ...options.headers,
        },
    });
}

export async function register(data: RegisterData): Promise<TokenResponse> {
    return apiRequest<TokenResponse>(API_ENDPOINTS.AUTH.REGISTER, {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function login(data: LoginData): Promise<TokenResponse> {
    const formData = new URLSearchParams();
    formData.append('username', data.username);
    formData.append('password', data.password);

    const url = `${API_BASE_URL}${API_ENDPOINTS.AUTH.LOGIN}`;

    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString(),
    });

    if (!response.ok) {
        const error: ApiError = await response.json().catch(() => ({
            detail: `HTTP ${response.status}: ${response.statusText}`,
        }));
        throw new Error(error.detail || 'Invalid credentials');
    }

    return response.json();
}

export async function logout(accessToken: string): Promise<{ message: string }> {
    return authenticatedRequest<{ message: string }>(
        API_ENDPOINTS.AUTH.LOGOUT,
        accessToken,
        {
            method: 'POST',
        }
    );
}

export async function refreshToken(
    refreshToken: string
): Promise<TokenResponse> {
    return apiRequest<TokenResponse>(API_ENDPOINTS.AUTH.REFRESH, {
        method: 'POST',
        body: JSON.stringify({ refresh_token: refreshToken }),
    });
}

export async function getCurrentUser(
    accessToken: string
): Promise<UserResponse> {
    return authenticatedRequest<UserResponse>(
        API_ENDPOINTS.AUTH.ME,
        accessToken,
        {
            method: 'GET',
        }
    );
}

// Map API Types
export interface BoundingBox {
    min_lng: number;
    min_lat: number;
    max_lng: number;
    max_lat: number;
}

export interface MapCellsResponse {
    res6: string[];
    res8: string[];
}

export interface CountryInfo {
    code: string;
    name: string;
}

export interface RegionInfo {
    code: string;
    name: string;
}

export interface MapSummaryResponse {
    countries: CountryInfo[];
    regions: RegionInfo[];
}

// Map API Functions
export async function getMapSummary(
    accessToken: string
): Promise<MapSummaryResponse> {
    return authenticatedRequest<MapSummaryResponse>(
        API_ENDPOINTS.MAP.SUMMARY,
        accessToken,
        {
            method: 'GET',
        }
    );
}

export async function getMapCells(
    accessToken: string,
    bbox: BoundingBox
): Promise<MapCellsResponse> {
    const params = new URLSearchParams({
        min_lng: bbox.min_lng.toString(),
        min_lat: bbox.min_lat.toString(),
        max_lng: bbox.max_lng.toString(),
        max_lat: bbox.max_lat.toString(),
    });

    return authenticatedRequest<MapCellsResponse>(
        `${API_ENDPOINTS.MAP.CELLS}?${params.toString()}`,
        accessToken,
        {
            method: 'GET',
        }
    );
}


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
    detail?: string;
    error?: string;
    message?: string;
}

export interface ForgotPasswordData {
    email: string;
}

export interface ResetPasswordData {
    token: string;
    new_password: string;
}

export interface MessageResponse {
    message: string;
}

export interface ChangePasswordData {
    current_password: string;
    new_password: string;
}

export interface DeleteAccountData {
    password: string;
    confirmation: string;
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
        // Handle different error formats from backend
        const errorMessage = error.detail || error.message || error.error || `HTTP ${response.status}: ${response.statusText}`;
        throw new Error(typeof errorMessage === 'string' ? errorMessage : JSON.stringify(errorMessage));
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

export async function forgotPassword(
    data: ForgotPasswordData
): Promise<MessageResponse> {
    return apiRequest<MessageResponse>(API_ENDPOINTS.AUTH.FORGOT_PASSWORD, {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function resetPassword(
    data: ResetPasswordData
): Promise<MessageResponse> {
    return apiRequest<MessageResponse>(API_ENDPOINTS.AUTH.RESET_PASSWORD, {
        method: 'POST',
        body: JSON.stringify(data),
    });
}

export async function changePassword(
    accessToken: string,
    data: ChangePasswordData
): Promise<MessageResponse> {
    return authenticatedRequest<MessageResponse>(
        API_ENDPOINTS.AUTH.CHANGE_PASSWORD,
        accessToken,
        {
            method: 'POST',
            body: JSON.stringify(data),
        }
    );
}

export async function deleteAccount(
    accessToken: string,
    data: DeleteAccountData
): Promise<void> {
    return authenticatedRequest<void>(
        API_ENDPOINTS.AUTH.DELETE_ACCOUNT,
        accessToken,
        {
            method: 'DELETE',
            body: JSON.stringify(data),
        }
    );
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

// GeoJSON Types for polygon endpoint
export interface GeoJSONPolygonGeometry {
    type: 'Polygon';
    coordinates: number[][][];
}

export interface GeoJSONMultiPolygonGeometry {
    type: 'MultiPolygon';
    coordinates: number[][][][];
}

// Properties for H3 cell polygons
export interface H3CellProperties {
    h3_index: string;
    resolution: number;
}

// Properties for country/state region polygons
export interface RegionPolygonProperties {
    id: number;
    code: string | null;
    name: string;
    type: 'country' | 'state';
}

export interface GeoJSONFeature {
    type: 'Feature';
    properties: H3CellProperties | RegionPolygonProperties;
    geometry: GeoJSONPolygonGeometry | GeoJSONMultiPolygonGeometry;
}

export interface MapPolygonsResponse {
    type: 'FeatureCollection';
    features: GeoJSONFeature[];
}

export async function getMapPolygons(
    accessToken: string,
    bbox: BoundingBox,
    zoom?: number
): Promise<MapPolygonsResponse> {
    const params = new URLSearchParams({
        min_lng: bbox.min_lng.toString(),
        min_lat: bbox.min_lat.toString(),
        max_lng: bbox.max_lng.toString(),
        max_lat: bbox.max_lat.toString(),
    });

    if (zoom !== undefined) {
        params.append('zoom', zoom.toString());
    }

    return authenticatedRequest<MapPolygonsResponse>(
        `${API_ENDPOINTS.MAP.POLYGONS}?${params.toString()}`,
        accessToken,
        {
            method: 'GET',
        }
    );
}

export async function getCountryPolygons(
    accessToken: string,
    bbox: BoundingBox
): Promise<MapPolygonsResponse> {
    const params = new URLSearchParams({
        min_lng: bbox.min_lng.toString(),
        min_lat: bbox.min_lat.toString(),
        max_lng: bbox.max_lng.toString(),
        max_lat: bbox.max_lat.toString(),
    });

    return authenticatedRequest<MapPolygonsResponse>(
        `${API_ENDPOINTS.MAP.POLYGONS_COUNTRIES}?${params.toString()}`,
        accessToken,
        {
            method: 'GET',
        }
    );
}

export async function getStatePolygons(
    accessToken: string,
    bbox: BoundingBox
): Promise<MapPolygonsResponse> {
    const params = new URLSearchParams({
        min_lng: bbox.min_lng.toString(),
        min_lat: bbox.min_lat.toString(),
        max_lng: bbox.max_lng.toString(),
        max_lat: bbox.max_lat.toString(),
    });

    return authenticatedRequest<MapPolygonsResponse>(
        `${API_ENDPOINTS.MAP.POLYGONS_STATES}?${params.toString()}`,
        accessToken,
        {
            method: 'GET',
        }
    );
}

// Location Ingestion Types
export interface LocationIngestRequest {
    latitude: number;
    longitude: number;
    timestamp?: string;
    device_uuid?: string;
    device_name?: string;
    platform?: string;
}

export interface CountryDiscovery {
    id: number;
    name: string;
    iso2: string;
}

export interface StateDiscovery {
    id: number;
    name: string;
    code?: string;
}

export interface DiscoveriesResponse {
    new_country?: CountryDiscovery;
    new_state?: StateDiscovery;
    new_cells_res6: string[];
    new_cells_res8: string[];
}

export interface RevisitsResponse {
    cells_res6: string[];
    cells_res8: string[];
}

export interface VisitCountsResponse {
    res6_visit_count: number;
    res8_visit_count: number;
}

export interface AchievementUnlocked {
    id: number;
    key: string;
    name: string;
    description: string;
    icon: string;
    unlocked_at: string;
}

export interface LocationIngestResponse {
    discoveries: DiscoveriesResponse;
    revisits: RevisitsResponse;
    visit_counts: VisitCountsResponse;
    achievements_unlocked: AchievementUnlocked[];
}

export async function ingestLocation(
    accessToken: string,
    data: LocationIngestRequest
): Promise<LocationIngestResponse> {
    return authenticatedRequest<LocationIngestResponse>(
        API_ENDPOINTS.LOCATION.INGEST_SIMPLE,
        accessToken,
        {
            method: 'POST',
            body: JSON.stringify(data),
        }
    );
}

// Stats Types
export interface StatsUserInfo {
    id: number;
    username: string;
    created_at: string;
}

export interface StatsData {
    countries_visited: number;
    regions_visited: number;
    cells_visited_res6: number;
    cells_visited_res8: number;
    total_visit_count: number;
    first_visit_at: string | null;
    last_visit_at: string | null;
}

export interface RecentCountry {
    code: string;
    name: string;
    visited_at: string;
}

export interface RecentRegion {
    code: string;
    name: string;
    country_name: string;
    visited_at: string;
}

export interface StatsOverviewResponse {
    user: StatsUserInfo;
    stats: StatsData;
    recent_countries: RecentCountry[];
    recent_regions: RecentRegion[];
}

export async function getStatsOverview(
    accessToken: string
): Promise<StatsOverviewResponse> {
    return authenticatedRequest<StatsOverviewResponse>(
        API_ENDPOINTS.STATS.OVERVIEW,
        accessToken,
        {
            method: 'GET',
        }
    );
}

// Achievements Types
export interface Achievement {
    code: string;
    name: string;
    description: string | null;
    unlocked: boolean;
    unlocked_at: string | null;
}

export interface AchievementsListResponse {
    achievements: Achievement[];
    total: number;
    unlocked_count: number;
}

export async function getAchievements(
    accessToken: string
): Promise<AchievementsListResponse> {
    return authenticatedRequest<AchievementsListResponse>(
        API_ENDPOINTS.ACHIEVEMENTS.LIST,
        accessToken,
        {
            method: 'GET',
        }
    );
}





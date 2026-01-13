import * as Location from 'expo-location';
import * as TaskManager from 'expo-task-manager';
import { Platform } from 'react-native';
import { ingestLocation, LocationIngestResponse } from './api';
import { tokenStorage } from './storage';

const LOCATION_TASK_NAME = 'trekkr-background-location';

// Minimum distance in meters before sending update (H3 res-8 cells are ~460m edge)
const MIN_DISTANCE_METERS = 200;

// Minimum time between updates in milliseconds
const MIN_TIME_MS = 30000; // 30 seconds

export interface LocationTrackingCallbacks {
    onLocationUpdate?: (response: LocationIngestResponse) => void;
    onError?: (error: Error) => void;
    onNewDiscovery?: (response: LocationIngestResponse) => void;
}

let callbacks: LocationTrackingCallbacks = {};

// Define the background task
TaskManager.defineTask(LOCATION_TASK_NAME, async ({ data, error }) => {
    if (error) {
        console.error('[LocationTracking] Background task error:', error);
        callbacks.onError?.(new Error(error.message));
        return;
    }

    if (data) {
        const { locations } = data as { locations: Location.LocationObject[] };
        if (locations && locations.length > 0) {
            const location = locations[locations.length - 1]; // Use most recent
            await processLocationUpdate(location);
        }
    }
});

async function processLocationUpdate(location: Location.LocationObject): Promise<void> {
    try {
        const accessToken = await tokenStorage.getAccessToken();
        if (!accessToken) {
            console.log('[LocationTracking] No access token, skipping update. Please log in first.');
            callbacks.onError?.(new Error('Not logged in. Please log in to track your location.'));
            return;
        }

        console.log('[LocationTracking] Sending location:', {
            latitude: location.coords.latitude,
            longitude: location.coords.longitude,
        });

        const response = await ingestLocation(accessToken, {
            latitude: location.coords.latitude,
            longitude: location.coords.longitude,
            timestamp: new Date(location.timestamp).toISOString(),
            platform: Platform.OS,
        });

        console.log('[LocationTracking] Location processed successfully');
        callbacks.onLocationUpdate?.(response);

        // Check for new discoveries
        if (
            response.discoveries.new_country ||
            response.discoveries.new_state ||
            response.discoveries.new_cells_res6.length > 0 ||
            response.discoveries.new_cells_res8.length > 0
        ) {
            callbacks.onNewDiscovery?.(response);
        }
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        console.error('[LocationTracking] Error processing location:', errorMessage);
        callbacks.onError?.(new Error(errorMessage));
    }
}

export async function requestLocationPermissions(): Promise<{
    foreground: boolean;
    background: boolean;
}> {
    // Request foreground permission first
    const { status: foregroundStatus } = await Location.requestForegroundPermissionsAsync();
    const foregroundGranted = foregroundStatus === 'granted';

    if (!foregroundGranted) {
        return { foreground: false, background: false };
    }

    // Request background permission
    const { status: backgroundStatus } = await Location.requestBackgroundPermissionsAsync();
    const backgroundGranted = backgroundStatus === 'granted';

    return { foreground: foregroundGranted, background: backgroundGranted };
}

export async function startLocationTracking(
    newCallbacks?: LocationTrackingCallbacks
): Promise<boolean> {
    if (newCallbacks) {
        callbacks = { ...callbacks, ...newCallbacks };
    }

    const permissions = await requestLocationPermissions();
    if (!permissions.foreground) {
        console.log('[LocationTracking] Foreground permission denied');
        return false;
    }

    // Check if already tracking
    const isTracking = await Location.hasStartedLocationUpdatesAsync(LOCATION_TASK_NAME);
    if (isTracking) {
        console.log('[LocationTracking] Already tracking');
        return true;
    }

    try {
        await startNativeLocationUpdates();

        console.log('[LocationTracking] Started background tracking');
        return true;
    } catch (error) {
        console.error('[LocationTracking] Failed to start tracking:', error);
        return false;
    }
}

async function startNativeLocationUpdates(): Promise<void> {
    await Location.startLocationUpdatesAsync(LOCATION_TASK_NAME, {
        accuracy: Location.Accuracy.High,
        distanceInterval: MIN_DISTANCE_METERS,
        timeInterval: MIN_TIME_MS,
        // Android-only foreground notification while tracking in background
        foregroundService: {
            notificationTitle: 'Trekkr',
            notificationBody: 'Tracking your exploration',
            notificationColor: '#10b981',
        },
        pausesUpdatesAutomatically: false,
        activityType: Location.ActivityType.Fitness,
        showsBackgroundLocationIndicator: true,
    });
}

/**
 * Best-effort resume without prompting for permissions.
 * Useful on cold start: only starts if the user already granted permissions.
 */
export async function resumeLocationTrackingIfPossible(
    newCallbacks?: LocationTrackingCallbacks
): Promise<boolean> {
    if (newCallbacks) {
        callbacks = { ...callbacks, ...newCallbacks };
    }

    const isTracking = await Location.hasStartedLocationUpdatesAsync(LOCATION_TASK_NAME);
    if (isTracking) {
        return true;
    }

    const foreground = await Location.getForegroundPermissionsAsync();
    if (foreground.status !== 'granted') {
        return false;
    }

    // Background permission may not be granted yet; if it's not, do not prompt on startup.
    const background = await Location.getBackgroundPermissionsAsync();
    if (background.status !== 'granted') {
        return false;
    }

    try {
        await startNativeLocationUpdates();
        console.log('[LocationTracking] Resumed background tracking (no prompt)');
        return true;
    } catch (error) {
        console.error('[LocationTracking] Failed to resume tracking:', error);
        return false;
    }
}

export async function stopLocationTracking(): Promise<void> {
    try {
        const isTracking = await Location.hasStartedLocationUpdatesAsync(LOCATION_TASK_NAME);
        if (isTracking) {
            await Location.stopLocationUpdatesAsync(LOCATION_TASK_NAME);
            console.log('[LocationTracking] Stopped tracking');
        }
    } catch (error) {
        console.error('[LocationTracking] Error stopping tracking:', error);
    }
}

export async function isTrackingLocation(): Promise<boolean> {
    try {
        return await Location.hasStartedLocationUpdatesAsync(LOCATION_TASK_NAME);
    } catch {
        return false;
    }
}

export function setLocationCallbacks(newCallbacks: LocationTrackingCallbacks): void {
    callbacks = { ...callbacks, ...newCallbacks };
}

// For immediate location update (foreground)
export async function sendCurrentLocation(): Promise<LocationIngestResponse | null> {
    try {
        const accessToken = await tokenStorage.getAccessToken();
        if (!accessToken) {
            console.log('[LocationTracking] No access token - user needs to log in');
            return null;
        }

        console.log('[LocationTracking] Getting current position...');
        const location = await Location.getCurrentPositionAsync({
            accuracy: Location.Accuracy.High,
        });

        console.log('[LocationTracking] Sending current location:', {
            latitude: location.coords.latitude,
            longitude: location.coords.longitude,
        });

        const response = await ingestLocation(accessToken, {
            latitude: location.coords.latitude,
            longitude: location.coords.longitude,
            timestamp: new Date(location.timestamp).toISOString(),
            platform: Platform.OS,
        });

        console.log('[LocationTracking] Current location sent successfully');
        return response;
    } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        console.error('[LocationTracking] Error sending current location:', errorMessage);
        return null;
    }
}

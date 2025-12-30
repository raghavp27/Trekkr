import { useEffect, useState, useCallback, useRef } from "react";
import { View, StyleSheet, ActivityIndicator, Text, Alert } from "react-native";
import * as Location from "expo-location";
import Mapbox, { MapView, Camera, LocationPuck } from "@rnmapbox/maps";
import { MAPBOX_ACCESS_TOKEN } from "@/config/mapbox";
// TODO: Re-enable after fixing h3-js encoding issue
// import { FogOfWarLayer } from "@/components/map/FogOfWarLayer";
import { getMapCells, BoundingBox } from "@/services/api";
import { tokenStorage } from "@/services/storage";

// Initialize Mapbox with access token
Mapbox.setAccessToken(MAPBOX_ACCESS_TOKEN);

interface UserCoordinates {
    latitude: number;
    longitude: number;
}

interface MapBounds {
    ne: [number, number]; // [lng, lat]
    sw: [number, number]; // [lng, lat]
}

const ZOOM_THRESHOLD = 8; // Show res8 cells at zoom >= 8, otherwise res6
const DEBOUNCE_MS = 300;
const MIN_ZOOM_FOR_CELLS = 4; // Don't fetch cells when zoomed out too far

export default function MapScreen() {
    const [isLoading, setIsLoading] = useState(true);
    const [locationPermission, setLocationPermission] = useState<boolean | null>(null);
    const [userLocation, setUserLocation] = useState<UserCoordinates | null>(null);
    const [revealedCells, setRevealedCells] = useState<string[]>([]);

    const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
        requestLocationPermission();
    }, []);

    const requestLocationPermission = async () => {
        try {
            const { status } = await Location.requestForegroundPermissionsAsync();
            const granted = status === "granted";
            setLocationPermission(granted);

            if (granted) {
                // Get initial location
                const location = await Location.getCurrentPositionAsync({
                    accuracy: Location.Accuracy.Balanced,
                });
                setUserLocation({
                    latitude: location.coords.latitude,
                    longitude: location.coords.longitude,
                });
            } else {
                Alert.alert(
                    "Location Permission Required",
                    "Trekkr needs location access to track your explorations and unlock areas on the map.",
                    [{ text: "OK" }]
                );
            }
        } catch (error) {
            console.error("Error requesting location permission:", error);
        } finally {
            setIsLoading(false);
        }
    };

    const fetchCellsForViewport = useCallback(async (bounds: MapBounds, zoom: number) => {
        // Skip fetching when zoomed out too far (viewport too large)
        if (zoom < MIN_ZOOM_FOR_CELLS) {
            setRevealedCells([]);
            return;
        }

        try {
            const accessToken = await tokenStorage.getAccessToken();
            if (!accessToken) {
                return;
            }

            const bbox: BoundingBox = {
                min_lng: bounds.sw[0],
                min_lat: bounds.sw[1],
                max_lng: bounds.ne[0],
                max_lat: bounds.ne[1],
            };

            const response = await getMapCells(accessToken, bbox);

            // Use res8 at high zoom, res6 at low zoom
            const cells = zoom >= ZOOM_THRESHOLD
                ? [...response.res6, ...response.res8]
                : response.res6;

            setRevealedCells(cells);
        } catch (error) {
            // Silently fail - fog of war is optional, map still works without it
            // This can fail if backend is not running or user has no visited cells
        }
    }, []);

    const handleCameraChanged = useCallback((state: { properties: { bounds: MapBounds; zoom: number } }) => {
        const { bounds, zoom } = state.properties;

        // Debounce API calls
        if (debounceTimerRef.current) {
            clearTimeout(debounceTimerRef.current);
        }

        debounceTimerRef.current = setTimeout(() => {
            fetchCellsForViewport(bounds, zoom);
        }, DEBOUNCE_MS);
    }, [fetchCellsForViewport]);

    // Cleanup debounce timer on unmount
    useEffect(() => {
        return () => {
            if (debounceTimerRef.current) {
                clearTimeout(debounceTimerRef.current);
            }
        };
    }, []);

    if (isLoading) {
        return (
            <View style={styles.centered}>
                <ActivityIndicator size="large" color="#10b981" />
                <Text style={styles.loadingText}>Loading map...</Text>
            </View>
        );
    }

    if (locationPermission === false) {
        return (
            <View style={styles.centered}>
                <Text style={styles.errorText}>Location permission denied</Text>
                <Text style={styles.subText}>
                    Enable location access in your device settings to use Trekkr
                </Text>
            </View>
        );
    }

    // Default to a world view if no user location
    const initialCoordinates = userLocation || { latitude: 20, longitude: 0 };
    const initialZoom = userLocation ? 12 : 2;

    return (
        <View style={styles.container}>
            <MapView
                style={styles.map}
                styleURL="mapbox://styles/mapbox/streets-v12"
                logoEnabled={false}
                attributionEnabled={true}
                attributionPosition={{ bottom: 8, right: 8 }}
                scaleBarEnabled={false}
                onCameraChanged={handleCameraChanged}
            >
                <Camera
                    zoomLevel={initialZoom}
                    centerCoordinate={[initialCoordinates.longitude, initialCoordinates.latitude]}
                    animationMode="flyTo"
                    animationDuration={1000}
                />

                {/* TODO: Re-enable after fixing h3-js encoding issue */}
                {/* <FogOfWarLayer revealedCells={revealedCells} /> */}

                {locationPermission && (
                    <LocationPuck
                        puckBearing="heading"
                        puckBearingEnabled={true}
                        pulsing={{ isEnabled: true, color: "#10b981", radius: 50 }}
                    />
                )}
            </MapView>
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    map: {
        flex: 1,
    },
    centered: {
        flex: 1,
        justifyContent: "center",
        alignItems: "center",
        backgroundColor: "#f5f5f5",
        padding: 20,
    },
    loadingText: {
        marginTop: 12,
        fontSize: 16,
        color: "#666",
    },
    errorText: {
        fontSize: 18,
        fontWeight: "600",
        color: "#ef4444",
        textAlign: "center",
    },
    subText: {
        marginTop: 8,
        fontSize: 14,
        color: "#666",
        textAlign: "center",
    },
});

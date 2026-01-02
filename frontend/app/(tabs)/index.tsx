import { useEffect, useState, useCallback, useRef } from "react";
import {
  View,
  StyleSheet,
  ActivityIndicator,
  Text,
  Alert,
  TouchableOpacity,
} from "react-native";
import * as Location from "expo-location";
import Mapbox, { MapView, Camera, LocationPuck } from "@rnmapbox/maps";
import { MAPBOX_ACCESS_TOKEN } from "@/config/mapbox";
import { FogOfWarLayer } from "@/components/map/FogOfWarLayer";
import {
  getMapPolygons,
  BoundingBox,
  MapPolygonsResponse,
  LocationIngestResponse,
} from "@/services/api";
import { tokenStorage } from "@/services/storage";
import {
  startLocationTracking,
  stopLocationTracking,
  isTrackingLocation,
  sendCurrentLocation,
  setLocationCallbacks,
} from "@/services/locationTracking";

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

const MIN_ZOOM_FOR_CELLS = 4; // Don't fetch when zoomed out too far
const DEBOUNCE_MS = 300;

// Sample test polygons with REAL H3 hexagon boundaries (resolution 8)
const SAMPLE_TEST_POLYGONS: MapPolygonsResponse = {
  type: "FeatureCollection",
  features: [
    // San Francisco - Union Square area (2 adjacent cells)
    {
      type: "Feature",
      properties: { h3_index: "88283082abfffff", resolution: 8 },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [-122.40340120235787, 37.779452885625275],
            [-122.39892632184691, 37.7829958219344],
            [-122.40037367895451, 37.78768773552642],
            [-122.40629625534781, 37.78883652694053],
            [-122.41077092287513, 37.785293473597285],
            [-122.40932322704121, 37.780601745884],
            [-122.40340120235787, 37.779452885625275],
          ],
        ],
      },
    },
    {
      type: "Feature",
      properties: { h3_index: "88283082a3fffff", resolution: 8 },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [-122.40037367895451, 37.78768773552642],
            [-122.39589825306314, 37.791230482989974],
            [-122.39734561646776, 37.79592213887593],
            [-122.40326874464051, 37.79707086149342],
            [-122.40774395758072, 37.793527997011616],
            [-122.40629625534781, 37.78883652694053],
            [-122.40037367895451, 37.78768773552642],
          ],
        ],
      },
    },
    // New York - Times Square area
    {
      type: "Feature",
      properties: { h3_index: "882a100d67fffff", resolution: 8 },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [-73.97969221725369, 40.7597814890051],
            [-73.98607291660541, 40.758727820035865],
            [-73.98803851785813, 40.754267907355896],
            [-73.98362433001691, 40.750861995011526],
            [-73.9772446567056, 40.75191544407061],
            [-73.97527814530736, 40.756375025354224],
            [-73.97969221725369, 40.7597814890051],
          ],
        ],
      },
    },
    // London - Westminster area
    {
      type: "Feature",
      properties: { h3_index: "88194ad14dfffff", resolution: 8 },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [-0.12484220854869736, 51.50434723964876],
            [-0.1315499392731809, 51.503153268658835],
            [-0.13277352092265374, 51.49867829011818],
            [-0.12729015362639665, 51.4953975497755],
            [-0.120583489575958, 51.4965915617412],
            [-0.11935912625927361, 51.50106627305865],
            [-0.12484220854869736, 51.50434723964876],
          ],
        ],
      },
    },
    // Tokyo - Shibuya area
    {
      type: "Feature",
      properties: { h3_index: "882f5aad93fffff", resolution: 8 },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [139.70614881968785, 35.65576149337553],
            [139.7064339406477, 35.66054853704088],
            [139.70190086584216, 35.66324552958082],
            [139.69708319460725, 35.661155364323456],
            [139.69679870461465, 35.656368574244986],
            [139.70133125491571, 35.65367169582615],
            [139.70614881968785, 35.65576149337553],
          ],
        ],
      },
    },
    // Paris - Eiffel Tower area
    {
      type: "Feature",
      properties: { h3_index: "881fb46741fffff", resolution: 8 },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [2.2997860644041204, 48.862036759119015],
            [2.293468413661573, 48.860887731207065],
            [2.2921452511979563, 48.85638078974249],
            [2.2971390910176894, 48.853023175125735],
            [2.303455759409226, 48.854172288661985],
            [2.3047795702317737, 48.85867893118178],
            [2.2997860644041204, 48.862036759119015],
          ],
        ],
      },
    },
  ],
};

// Set to true to use sample data instead of fetching from backend
const USE_SAMPLE_DATA = false;

export default function MapScreen() {
  const [isLoading, setIsLoading] = useState(true);
  const [locationPermission, setLocationPermission] = useState<boolean | null>(
    null
  );
  const [userLocation, setUserLocation] = useState<UserCoordinates | null>(
    null
  );
  // Cache both resolutions for instant switching
  const [polygonsRes6, setPolygonsRes6] = useState<MapPolygonsResponse | null>(
    null
  );
  const [polygonsRes8, setPolygonsRes8] = useState<MapPolygonsResponse | null>(
    USE_SAMPLE_DATA ? SAMPLE_TEST_POLYGONS : null
  );
  const [currentZoom, setCurrentZoom] = useState(14);
  const [isTracking, setIsTracking] = useState(false);
  const [lastDiscovery, setLastDiscovery] = useState<string | null>(null);

  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const currentBoundsRef = useRef<MapBounds | null>(null);
  const currentZoomRef = useRef<number>(14);
  const cameraRef = useRef<Camera>(null);

  // Select which polygons to display based on zoom level
  const revealedPolygons = currentZoom < 10 ? polygonsRes6 : polygonsRes8;

  const fetchPolygonsForViewport = useCallback(
    async (bounds: MapBounds, zoom: number) => {
      // Skip fetching when using sample data
      if (USE_SAMPLE_DATA) {
        return;
      }

      // Skip fetching when zoomed out too far
      if (zoom < MIN_ZOOM_FOR_CELLS) {
        setPolygonsRes6(null);
        setPolygonsRes8(null);
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

        // Fetch both resolutions in parallel for instant switching
        const [res6Response, res8Response] = await Promise.all([
          getMapPolygons(accessToken, bbox, 5), // Force res-6
          getMapPolygons(accessToken, bbox, 15), // Force res-8
        ]);

        setPolygonsRes6(res6Response);
        setPolygonsRes8(res8Response);
      } catch {
        // Silently fail - fog of war is optional, map still works without it
      }
    },
    []
  );

  const handleLocationUpdate = useCallback(
    (response: LocationIngestResponse) => {
      // Refresh polygons when we get a location update
      if (!USE_SAMPLE_DATA && currentBoundsRef.current) {
        fetchPolygonsForViewport(
          currentBoundsRef.current,
          currentZoomRef.current
        );
      }
    },
    [fetchPolygonsForViewport]
  );

  const handleNewDiscovery = useCallback((response: LocationIngestResponse) => {
    // Show discovery notification
    let message = "";
    if (response.discoveries.new_country) {
      message = `New country: ${response.discoveries.new_country.name}!`;
    } else if (response.discoveries.new_state) {
      message = `New region: ${response.discoveries.new_state.name}!`;
    } else if (response.discoveries.new_cells_res8.length > 0) {
      message = `Explored ${response.discoveries.new_cells_res8.length} new area(s)!`;
    }

    if (message) {
      setLastDiscovery(message);
      setTimeout(() => setLastDiscovery(null), 3000);
    }
  }, []);

  const initializeTracking = useCallback(async () => {
    // Check if already tracking
    const tracking = await isTrackingLocation();
    setIsTracking(tracking);

    // Set up callbacks for location updates
    setLocationCallbacks({
      onLocationUpdate: handleLocationUpdate,
      onNewDiscovery: handleNewDiscovery,
      onError: (error) => console.error("[MapScreen] Location error:", error),
    });
  }, [handleLocationUpdate, handleNewDiscovery]);

  const zoomToCurrentLocation = async () => {
    try {
      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });

      setUserLocation({
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
      });

      cameraRef.current?.setCamera({
        centerCoordinate: [location.coords.longitude, location.coords.latitude],
        zoomLevel: 14,
        animationDuration: 1000,
        animationMode: "flyTo",
      });
    } catch (err) {
      console.error("Error getting current location:", err);
    }
  };

  const toggleTracking = async () => {
    if (isTracking) {
      await stopLocationTracking();
      setIsTracking(false);
    } else {
      const success = await startLocationTracking({
        onLocationUpdate: handleLocationUpdate,
        onNewDiscovery: handleNewDiscovery,
      });
      setIsTracking(success);

      if (success) {
        // Send immediate location update
        const response = await sendCurrentLocation();
        if (response) {
          handleLocationUpdate(response);
          if (
            response.discoveries.new_country ||
            response.discoveries.new_state ||
            response.discoveries.new_cells_res8.length > 0
          ) {
            handleNewDiscovery(response);
          }
        }
      }
    }
  };

  useEffect(() => {
    requestLocationPermission();
    initializeTracking();
  }, [initializeTracking]);

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
    } catch (err) {
      console.error("Error requesting location permission:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCameraChanged = useCallback(
    (state: { properties: { bounds: MapBounds; zoom: number } }) => {
      const { bounds, zoom } = state.properties;

      // Store current bounds and zoom for refresh after location updates
      currentBoundsRef.current = bounds;
      currentZoomRef.current = zoom;

      // Update zoom state immediately for instant resolution switching
      setCurrentZoom(zoom);

      // Debounce API calls (only fetches when viewport changes significantly)
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }

      debounceTimerRef.current = setTimeout(() => {
        fetchPolygonsForViewport(bounds, zoom);
      }, DEBOUNCE_MS);
    },
    [fetchPolygonsForViewport]
  );

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

  // When using sample data, start at San Francisco to see test polygons
  // Otherwise use user location or world view
  const initialCoordinates = USE_SAMPLE_DATA
    ? { latitude: 37.787, longitude: -122.408 }
    : userLocation || { latitude: 20, longitude: 0 };
  const initialZoom = USE_SAMPLE_DATA ? 15 : userLocation ? 14 : 2;

  return (
    <View style={styles.container}>
      <MapView
        style={styles.map}
        styleURL="mapbox://styles/mapbox/streets-v12"
        logoEnabled={true}
        logoPosition={{ bottom: 16, left: 8 }}
        attributionEnabled={true}
        attributionPosition={{ bottom: 15, left: 85 }}
        scaleBarEnabled={false}
        onCameraChanged={handleCameraChanged}
      >
        <Camera
          ref={cameraRef}
          zoomLevel={initialZoom}
          centerCoordinate={[
            initialCoordinates.longitude,
            initialCoordinates.latitude,
          ]}
          animationMode="flyTo"
          animationDuration={1000}
        />

        <FogOfWarLayer revealedPolygons={revealedPolygons} />

        {locationPermission && (
          <LocationPuck
            puckBearing="heading"
            puckBearingEnabled={true}
            pulsing={{ isEnabled: true, color: "#10b981", radius: 50 }}
          />
        )}
      </MapView>

      {/* My Location button */}
      <TouchableOpacity
        style={styles.locationButton}
        onPress={zoomToCurrentLocation}
      >
        <Text style={styles.locationButtonIcon}>📍</Text>
      </TouchableOpacity>

      {/* Tracking toggle button */}
      <TouchableOpacity
        style={[
          styles.trackingButton,
          isTracking && styles.trackingButtonActive,
        ]}
        onPress={toggleTracking}
      >
        <Text style={styles.trackingButtonText}>
          {isTracking ? "Tracking" : "Start Tracking"}
        </Text>
      </TouchableOpacity>

      {/* Discovery notification */}
      {lastDiscovery && (
        <View style={styles.discoveryNotification}>
          <Text style={styles.discoveryText}>{lastDiscovery}</Text>
        </View>
      )}
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
  locationButton: {
    position: "absolute",
    bottom: 170,
    right: 16,
    backgroundColor: "#fff",
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: "center",
    alignItems: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
    elevation: 5,
  },
  locationButtonIcon: {
    fontSize: 22,
  },
  trackingButton: {
    position: "absolute",
    bottom: 100,
    right: 16,
    backgroundColor: "#333",
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 25,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
    elevation: 5,
  },
  trackingButtonActive: {
    backgroundColor: "#10b981",
  },
  trackingButtonText: {
    color: "#fff",
    fontSize: 14,
    fontWeight: "600",
  },
  discoveryNotification: {
    position: "absolute",
    top: 60,
    left: 16,
    right: 16,
    backgroundColor: "#10b981",
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderRadius: 12,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
    elevation: 5,
  },
  discoveryText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
    textAlign: "center",
  },
});

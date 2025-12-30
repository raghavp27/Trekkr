import { cellToBoundary } from 'h3-js';

export interface GeoJSONPolygon {
    type: 'Polygon';
    coordinates: number[][][];
}

export interface GeoJSONFeature {
    type: 'Feature';
    properties: { h3Index: string };
    geometry: GeoJSONPolygon;
}

export interface GeoJSONFeatureCollection {
    type: 'FeatureCollection';
    features: GeoJSONFeature[];
}

/**
 * Convert an H3 cell index to a GeoJSON Polygon geometry.
 * h3-js returns coordinates as [lat, lng], but GeoJSON/Mapbox expects [lng, lat].
 */
export function h3CellToPolygon(h3Index: string): GeoJSONPolygon {
    const boundary = cellToBoundary(h3Index);
    // Convert from [lat, lng] to [lng, lat] for GeoJSON
    const coordinates = boundary.map(([lat, lng]) => [lng, lat]);
    // Close the polygon by repeating the first coordinate
    coordinates.push(coordinates[0]);

    return {
        type: 'Polygon',
        coordinates: [coordinates],
    };
}

/**
 * Convert an array of H3 cell indexes to a GeoJSON FeatureCollection.
 */
export function h3CellsToFeatureCollection(h3Indexes: string[]): GeoJSONFeatureCollection {
    const features: GeoJSONFeature[] = h3Indexes.map((h3Index) => ({
        type: 'Feature',
        properties: { h3Index },
        geometry: h3CellToPolygon(h3Index),
    }));

    return {
        type: 'FeatureCollection',
        features,
    };
}

/**
 * Create a fog-of-war polygon that covers the entire world with holes
 * cut out for revealed H3 cells.
 *
 * The polygon uses the "inverted mask" technique:
 * - Outer ring covers the entire world
 * - Inner rings (holes) represent revealed cells
 */
export function createFogPolygon(revealedCells: string[]): GeoJSONFeature {
    // World bounds (outer ring) - must be counter-clockwise for GeoJSON
    // Using ±180 longitude and ±85 latitude (Web Mercator limits)
    const worldBounds: number[][] = [
        [-180, -85],
        [180, -85],
        [180, 85],
        [-180, 85],
        [-180, -85], // Close the ring
    ];

    // Convert each revealed cell to a hole (inner ring)
    // Inner rings should be clockwise (opposite of outer ring)
    const holes: number[][][] = revealedCells.map((h3Index) => {
        const boundary = cellToBoundary(h3Index);
        // Convert from [lat, lng] to [lng, lat] and reverse for clockwise winding
        const coords = boundary.map(([lat, lng]) => [lng, lat]);
        coords.push(coords[0]); // Close the ring
        return coords.reverse(); // Clockwise for holes
    });

    return {
        type: 'Feature',
        properties: { h3Index: 'fog' },
        geometry: {
            type: 'Polygon',
            coordinates: [worldBounds, ...holes],
        },
    };
}

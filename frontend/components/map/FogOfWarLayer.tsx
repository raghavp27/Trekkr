import React, { useMemo } from 'react';
import { ShapeSource, FillLayer } from '@rnmapbox/maps';
import { MapPolygonsResponse } from '@/services/api';

interface FogOfWarLayerProps {
    revealedPolygons: MapPolygonsResponse | null;
}

/**
 * FogOfWarLayer renders a dark overlay covering the entire world,
 * with polygon "holes" cut out for revealed areas.
 */
export function FogOfWarLayer({ revealedPolygons }: FogOfWarLayerProps) {
    // Create the fog polygon with holes for revealed areas
    const fogGeoJSON = useMemo(() => {
        // World bounds - clockwise for outer ring in Mapbox
        const worldBounds: number[][] = [
            [-180, 85],
            [180, 85],
            [180, -85],
            [-180, -85],
            [-180, 85],
        ];

        // Extract holes from revealed polygons (counter-clockwise)
        const holes: number[][][] = [];

        if (revealedPolygons?.features) {
            for (const feature of revealedPolygons.features) {
                if (feature.geometry?.coordinates?.[0]) {
                    // Keep coordinates as-is (should be counter-clockwise for holes)
                    holes.push(feature.geometry.coordinates[0]);
                }
            }
        }

        return {
            type: 'FeatureCollection' as const,
            features: [{
                type: 'Feature' as const,
                properties: {},
                geometry: {
                    type: 'Polygon' as const,
                    coordinates: [worldBounds, ...holes],
                },
            }],
        };
    }, [revealedPolygons]);

    // Also render revealed areas with a subtle highlight
    const revealedGeoJSON = useMemo(() => {
        if (!revealedPolygons?.features?.length) {
            return null;
        }
        return revealedPolygons;
    }, [revealedPolygons]);

    return (
        <>
            <ShapeSource id="fog-of-war-source" shape={fogGeoJSON}>
                <FillLayer
                    id="fog-of-war-layer"
                    style={{
                        fillColor: 'rgba(0, 0, 0, 0.85)',
                        fillAntialias: true,
                    }}
                />
            </ShapeSource>

            {revealedGeoJSON && (
                <ShapeSource id="revealed-areas-source" shape={revealedGeoJSON}>
                    <FillLayer
                        id="revealed-areas-layer"
                        style={{
                            fillColor: 'rgba(16, 185, 129, 0.2)',
                            fillOutlineColor: 'rgba(16, 185, 129, 0.6)',
                        }}
                    />
                </ShapeSource>
            )}
        </>
    );
}

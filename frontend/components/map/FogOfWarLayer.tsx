import React, { useMemo } from 'react';
import { ShapeSource, FillLayer } from '@rnmapbox/maps';
import { createFogPolygon } from '@/utils/h3';

interface FogOfWarLayerProps {
    revealedCells: string[];
}

/**
 * FogOfWarLayer renders a dark overlay covering the entire world,
 * with "holes" cut out for revealed H3 cells.
 *
 * Uses the inverted polygon technique where:
 * - Outer ring covers world bounds
 * - Inner rings (holes) show revealed areas
 */
export function FogOfWarLayer({ revealedCells }: FogOfWarLayerProps) {
    // Memoize the GeoJSON to avoid recalculating on every render
    const fogGeoJSON = useMemo(() => {
        const fogFeature = createFogPolygon(revealedCells);
        return {
            type: 'FeatureCollection' as const,
            features: [fogFeature],
        };
    }, [revealedCells]);

    return (
        <ShapeSource id="fog-of-war-source" shape={fogGeoJSON}>
            <FillLayer
                id="fog-of-war-layer"
                style={{
                    fillColor: 'rgba(0, 0, 0, 0.9)',
                    fillAntialias: true,
                }}
            />
        </ShapeSource>
    );
}

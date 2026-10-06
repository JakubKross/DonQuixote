import { LngLatBounds, Map as MapLibreMap, setWorkerUrl } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";

import { screeningLayerUrl } from "../api/client";

// maplibre-gl's own automatic worker resolution (`new Worker(new URL(...,
// import.meta.url))`) does not reliably survive bundling: confirmed broken
// in the production `vite build` output (no worker chunk emitted at all,
// map rendered blank with a "Worker failed to load" console error). A
// Vite `?url` import for just the worker file isn't enough either — that
// worker file itself does `import ... from "./maplibre-gl-shared.mjs"`, a
// *second* file it expects to sit right next to it, which `?url` does not
// also copy. The `postinstall` script in package.json copies both files
// verbatim into public/maplibre-gl/ (Vite serves public/ as static files,
// unprocessed, at the same relative layout), and this points maplibre-gl
// at that copy via its own documented `setWorkerUrl` escape hatch —
// sidestepping bundler worker-detection entirely.
setWorkerUrl(`${import.meta.env.BASE_URL}maplibre-gl/maplibre-gl-worker.mjs`);

const DEMO_STYLE = "https://demotiles.maplibre.org/style.json";

// GeoJSON coordinate arrays nest arbitrarily deeply depending on geometry
// type (Polygon vs MultiPolygon, ...) — walking them generically needs `any`.
function extendBounds(bounds: LngLatBounds, coordinates: any): void {
  if (typeof coordinates[0] === "number") {
    bounds.extend(coordinates as [number, number]);
    return;
  }
  for (const nested of coordinates) {
    extendBounds(bounds, nested);
  }
}

function boundsOf(featureCollections: GeoJSON.FeatureCollection[]): LngLatBounds | null {
  const bounds = new LngLatBounds();
  let hasPoints = false;
  for (const collection of featureCollections) {
    for (const feature of collection.features) {
      if (!feature.geometry || !("coordinates" in feature.geometry)) continue;
      extendBounds(bounds, feature.geometry.coordinates);
      hasPoints = true;
    }
  }
  return hasPoints ? bounds : null;
}

export default function ScreeningMap({ screeningId }: { screeningId: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const map = new MapLibreMap({
      container: containerRef.current,
      style: DEMO_STYLE,
      center: [19.1, 52.1], // Poland, as a sane fallback before layers load
      zoom: 5,
    });

    let cancelled = false;

    map.on("load", () => {
      void (async () => {
        const [available, excluded] = await Promise.all([
          fetch(screeningLayerUrl(screeningId, "available")).then((r) => r.json()),
          fetch(screeningLayerUrl(screeningId, "excluded")).then((r) => r.json()),
        ]);
        if (cancelled) return;

        map.addSource("available", { type: "geojson", data: available });
        map.addLayer({
          id: "available-fill",
          type: "fill",
          source: "available",
          paint: { "fill-color": "#2e7d32", "fill-opacity": 0.4 },
        });
        map.addLayer({
          id: "available-outline",
          type: "line",
          source: "available",
          paint: { "line-color": "#1b5e20", "line-width": 2 },
        });

        map.addSource("excluded", { type: "geojson", data: excluded });
        map.addLayer({
          id: "excluded-fill",
          type: "fill",
          source: "excluded",
          paint: { "fill-color": "#c62828", "fill-opacity": 0.4 },
        });
        map.addLayer({
          id: "excluded-outline",
          type: "line",
          source: "excluded",
          paint: { "line-color": "#8e0000", "line-width": 2 },
        });

        const bounds = boundsOf([available, excluded]);
        if (bounds) {
          map.fitBounds(bounds, { padding: 32, maxZoom: 17, duration: 0 });
        }
      })();
    });

    return () => {
      cancelled = true;
      map.remove();
    };
  }, [screeningId]);

  return <div ref={containerRef} className="screening-map" />;
}

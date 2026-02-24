/**
 * Custom React Flow edge for pipeline graph visualization.
 *
 * Edge states (from design doc):
 *   Not yet reached: thin, dashed, dim gray
 *   Traversed:       solid, slightly brighter
 *
 * Uses ELK's computed edge geometry (sections with bend points) when available.
 * This ensures back-edges (loops, retries) route AROUND intermediate nodes
 * instead of going straight through them.  Falls back to React Flow's
 * getSmoothStepPath() when ELK sections are not available.
 */

import {
  BaseEdge,
  getSmoothStepPath,
  type EdgeProps,
} from "@xyflow/react";

/** A 2D point from ELK's layout output. */
interface ElkPoint {
  x: number;
  y: number;
}

/** One routed section of an ELK edge (start → bends → end). */
interface ElkSection {
  startPoint: ElkPoint;
  endPoint: ElkPoint;
  bendPoints?: ElkPoint[];
}

/**
 * Convert ELK edge sections into an SVG path string.
 *
 * ELK computes orthogonal routes with right-angle bends that avoid nodes.
 * We add small quadratic-bezier corners at each bend point so the path
 * looks polished instead of having sharp 90° turns.
 */
function elkSectionsToPath(sections: ElkSection[], cornerRadius = 8): string {
  if (!sections.length) return "";

  const section = sections[0]; // ELK typically produces one section per edge
  const points: ElkPoint[] = [
    section.startPoint,
    ...(section.bendPoints ?? []),
    section.endPoint,
  ];

  if (points.length < 2) return "";

  let d = `M ${points[0].x} ${points[0].y}`;

  for (let i = 1; i < points.length - 1; i++) {
    const prev = points[i - 1];
    const curr = points[i];
    const next = points[i + 1];

    // Direction vectors for the two segments meeting at this bend
    const dx1 = curr.x - prev.x;
    const dy1 = curr.y - prev.y;
    const dx2 = next.x - curr.x;
    const dy2 = next.y - curr.y;

    const len1 = Math.sqrt(dx1 * dx1 + dy1 * dy1);
    const len2 = Math.sqrt(dx2 * dx2 + dy2 * dy2);

    if (len1 === 0 || len2 === 0) {
      // Degenerate segment — just line to this point
      d += ` L ${curr.x} ${curr.y}`;
      continue;
    }

    // Clamp radius so it doesn't exceed half the segment length
    const r = Math.min(cornerRadius, len1 / 2, len2 / 2);

    // Point just before the bend (on the incoming segment)
    const bx1 = curr.x - (dx1 / len1) * r;
    const by1 = curr.y - (dy1 / len1) * r;

    // Point just after the bend (on the outgoing segment)
    const bx2 = curr.x + (dx2 / len2) * r;
    const by2 = curr.y + (dy2 / len2) * r;

    // Line to the start of the curve, then a smooth quadratic corner
    d += ` L ${bx1} ${by1}`;
    d += ` Q ${curr.x} ${curr.y} ${bx2} ${by2}`;
  }

  // Final segment to the end point
  d += ` L ${points[points.length - 1].x} ${points[points.length - 1].y}`;
  return d;
}

/**
 * Compute label position at the midpoint of the ELK path.
 */
function elkSectionsLabelPosition(sections: ElkSection[]): { x: number; y: number } {
  if (!sections.length) return { x: 0, y: 0 };

  const section = sections[0];
  const points: ElkPoint[] = [
    section.startPoint,
    ...(section.bendPoints ?? []),
    section.endPoint,
  ];

  // Place label at the midpoint of the middle segment
  const midIdx = Math.floor(points.length / 2);
  const p1 = points[Math.max(midIdx - 1, 0)];
  const p2 = points[midIdx];

  return {
    x: (p1.x + p2.x) / 2,
    y: (p1.y + p2.y) / 2,
  };
}

export default function PipelineEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  label,
  data,
  markerEnd,
}: EdgeProps) {
  const traversed = (data as Record<string, unknown>)?.traversed === true;
  const elkSections = (data as Record<string, unknown>)?.elkSections as ElkSection[] | undefined;

  // Prefer ELK's routed path (respects bend points around nodes).
  // Fall back to React Flow's getSmoothStepPath for edges without ELK data.
  let edgePath: string;
  let labelX: number;
  let labelY: number;

  if (elkSections && elkSections.length > 0) {
    edgePath = elkSectionsToPath(elkSections);
    const labelPos = elkSectionsLabelPosition(elkSections);
    labelX = labelPos.x;
    labelY = labelPos.y;
  } else {
    [edgePath, labelX, labelY] = getSmoothStepPath({
      sourceX,
      sourceY,
      targetX,
      targetY,
      sourcePosition,
      targetPosition,
    });
  }

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke: traversed ? "var(--text-secondary)" : "var(--text-tertiary)",
          strokeWidth: traversed ? 2 : 1,
          strokeDasharray: traversed ? "none" : "6 4",
          transition: "stroke var(--transition-normal), stroke-width var(--transition-normal)",
        }}
      />
      {label && (
        <text
          x={labelX}
          y={labelY}
          style={{
            fontSize: "10px",
            fill: "var(--text-tertiary)",
            fontFamily: "var(--font-mono)",
          }}
          textAnchor="middle"
          dominantBaseline="central"
        >
          {String(label)}
        </text>
      )}
    </>
  );
}

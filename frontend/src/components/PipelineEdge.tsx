/**
 * Custom React Flow edge for pipeline graph visualization.
 *
 * Edge states (from design doc):
 *   Not yet reached: thin, dashed, dim gray
 *   Traversed:       solid, slightly brighter
 */

import {
  BaseEdge,
  getSmoothStepPath,
  type EdgeProps,
} from "@xyflow/react";

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

  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });

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

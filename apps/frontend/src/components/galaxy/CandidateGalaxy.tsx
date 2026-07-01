/**
 * CandidateGalaxy — 3D semantic visualization of the ranked candidate pool.
 *
 * The JD sits at the origin (JDCore). Each candidate is a node in 3-space;
 * proximity to the core indicates higher fusion score. Thin gold
 * constellation trails connect the core to each node, opacity-weighted
 * by rank. This is the explainability surface — hover any node to see its
 * feature-contributions breakdown.
 */
import { useRef, useMemo, useCallback } from "react";
import { Canvas, useThree, type ThreeEvent } from "@react-three/fiber";
import { OrbitControls, Stars, Float, Html, Line } from "@react-three/drei";
import * as THREE from "three";
import { useAppSelector, useAppDispatch } from "../../store/hooks";
import { selectNode } from "../../store/slices/galaxySlice";
import { selectCandidate } from "../../store/slices/shortlistSlice";
import type { GalaxyNode } from "@polyhire/shared-types";

export function CandidateGalaxy() {
  const nodes = useAppSelector((s) => s.galaxy.nodes);
  const weights = useAppSelector((s) => s.galaxy.weights);
  const selectedId = useAppSelector((s) => s.galaxy.selectedNodeId);
  const isVisible = useAppSelector((s) => s.galaxy.isVisible);
  const candidates = useAppSelector((s) => s.shortlist.candidates);
  const dispatch = useAppDispatch();

  const handleClick = useCallback(
    (nodeId: string) => {
      dispatch(selectNode(nodeId));
      dispatch(selectCandidate(nodeId));
    },
    [dispatch],
  );

  if (!isVisible || nodes.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="text-center">
          <div className="mb-4 text-5xl">🌌</div>
          <p className="font-display text-lg text-primary/40">
            Submit a JD to generate the Candidate Galaxy
          </p>
          <p className="mt-1 text-xs font-mono text-primary/25">
            Candidates will cluster by semantic + behavioral fit
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex-1 h-full w-full">
      <Canvas
        camera={{ position: [0, 2, 8], fov: 55, near: 0.1, far: 100 }}
        gl={{ antialias: true, alpha: true }}
        style={{ background: "transparent" }}
      >
        <ambientLight intensity={0.15} />
        <pointLight position={[0, 0, 0]} intensity={1.5} color="#E8A33D" distance={30} decay={2} />
        <pointLight position={[5, 5, -5]} intensity={0.4} color="#4FD1C5" distance={40} decay={2} />

        <GalaxyScene
          nodes={nodes}
          selectedId={selectedId}
          candidates={candidates}
          onClick={handleClick}
        />

        <Stars
          radius={40}
          depth={60}
          count={2000}
          factor={3}
          saturation={0}
          fade
          speed={0.5}
        />

        <OrbitControls
          enablePan={false}
          minDistance={3}
          maxDistance={20}
          autoRotate
          autoRotateSpeed={0.3}
          enableDamping
          dampingFactor={0.05}
        />
      </Canvas>

      {/* Weight legend overlay */}
      <GalaxyLegend weights={weights} nodeCount={nodes.length} />
    </div>
  );
}

// ----- Internal scene graph -----

interface GalaxySceneProps {
  nodes: GalaxyNode[];
  selectedId: string | null;
  candidates: Array<{ candidate_id: string; score: number; explanation: string }>;
  onClick: (nodeId: string) => void;
}

function GalaxyScene({ nodes, selectedId, candidates, onClick }: GalaxySceneProps) {
  const { viewport } = useThree();
  const candidateMap = useMemo(
    () => new Map(candidates.map((c) => [c.candidate_id, c])),
    [candidates],
  );

  // Recalculate spread dynamically based on full viewport dimensions on mount/resize
  const spreadX = useMemo(() => Math.max(1, viewport.width / 12), [viewport.width]);
  const spreadY = useMemo(() => Math.max(1, viewport.height / 10), [viewport.height]);

  return (
    <group>
      {/* JD core at the origin */}
      <JDCore />

      {/* Connection trails */}
      {nodes.slice(0, 40).map((node) => (
        <ConstellationTrail
          key={`trail-${node.candidateId}`}
          from={[0, 0, 0]}
          to={[node.x * spreadX, node.y * spreadY, node.z * spreadX]}
          opacity={Math.max(0.05, node.score * 0.6)}
          isSelected={node.candidateId === selectedId}
        />
      ))}

      {/* Candidate nodes */}
      {nodes.map((node) => {
        const candidate = candidateMap.get(node.candidateId);
        
        // Spread the coordinates across the new canvas size
        const spreadNode = {
          ...node,
          x: node.x * spreadX,
          y: node.y * spreadY,
          z: node.z * spreadX
        };
        
        return (
          <CandidateNode
            key={node.candidateId}
            node={spreadNode}
            isSelected={node.candidateId === selectedId}
            explanation={candidate?.explanation ?? ""}
            onClick={() => onClick(node.candidateId)}
          />
        );
      })}
    </group>
  );
}

// ----- JD Core -----

export function JDCore() {
  return (
    <Float speed={1.5} rotationIntensity={0.3} floatIntensity={0.4}>
      <mesh position={[0, 0, 0]}>
        <sphereGeometry args={[0.25, 32, 32]} />
        <meshStandardMaterial
          color="#E8A33D"
          emissive="#E8A33D"
          emissiveIntensity={0.8}
          transparent
          opacity={0.9}
        />
      </mesh>
      {/* Glow ring */}
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.45, 0.015, 16, 64]} />
        <meshBasicMaterial color="#E8A33D" transparent opacity={0.3} />
      </mesh>
    </Float>
  );
}

// ----- Candidate Node -----

interface CandidateNodeProps {
  node: GalaxyNode;
  isSelected: boolean;
  explanation: string;
  onClick: () => void;
}

export function CandidateNode({ node, isSelected, explanation, onClick }: CandidateNodeProps) {
  const meshRef = useRef<THREE.Mesh>(null);

  const color = useMemo(() => {
    if (node.isNearMiss) return "#F5F1E8"; // white for near-miss
    if (node.score > 0.8) return "#E8A33D"; // gold for top candidates
    if (node.score > 0.5) return "#4FD1C5"; // teal for mid
    return "#F5F1E8"; // white for lower
  }, [node.score, node.isNearMiss]);

  const size = useMemo(() => {
    if (isSelected) return 0.12;
    if (node.score > 0.8) return 0.09;
    if (node.score > 0.5) return 0.06;
    return 0.04;
  }, [node.score, isSelected]);

  return (
    <Float speed={0.5 + Math.random()} rotationIntensity={0.1} floatIntensity={0.2}>
      <mesh
        ref={meshRef}
        position={[node.x, node.y, node.z]}
        onClick={(e: ThreeEvent<MouseEvent>) => {
          e.stopPropagation();
          onClick();
        }}
      >
        <sphereGeometry args={[size, 16, 16]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={isSelected ? 0.6 : 0.2}
          transparent
          opacity={isSelected ? 1 : 0.8}
        />
        {isSelected && (
          <Html
            position={[0, size + 0.15, 0]}
            center
            distanceFactor={8}
            style={{ pointerEvents: "none" }}
          >
            <div className="panel w-56 px-3 py-2 text-[11px] shadow-lg">
              <div className="mb-1 font-mono text-starlight">#{node.rank}</div>
              <div className="text-primary/80 leading-snug">{explanation}</div>
              <div className="mt-1 font-mono text-primary/40">
                score: {node.score.toFixed(3)}
              </div>
            </div>
          </Html>
        )}
      </mesh>
    </Float>
  );
}

// ----- Constellation Trail -----

interface TrailProps {
  from: [number, number, number];
  to: [number, number, number];
  opacity: number;
  isSelected: boolean;
}

export function ConstellationTrail({ from, to, opacity, isSelected }: TrailProps) {
  const points = useMemo(() => {
    const pts: Array<[number, number, number]> = [];
    const segments = 20;
    for (let i = 0; i <= segments; i++) {
      const t = i / segments;
      // Slight curve via quadratic bezier with a control point offset.
      const mid = [0.5 * (from[0] + to[0]), 0.5 * (from[1] + to[1]) + 0.3, 0.5 * (from[2] + to[2])];
      const x = (1 - t) * (1 - t) * from[0] + 2 * (1 - t) * t * mid[0] + t * t * to[0];
      const y = (1 - t) * (1 - t) * from[1] + 2 * (1 - t) * t * mid[1] + t * t * to[1];
      const z = (1 - t) * (1 - t) * from[2] + 2 * (1 - t) * t * mid[2] + t * t * to[2];
      pts.push([x, y, z]);
    }
    return pts;
  }, [from, to]);

  // Use drei's <Line> — it internally builds the geometry + material and
  // sidesteps the R3F `<line>` vs SVG `<line>` JSX intrinsic collision.
  return (
    <Line
      points={points}
      color={isSelected ? "#E8A33D" : "#2A2F4D"}
      transparent
      opacity={isSelected ? Math.min(opacity * 1.5, 1) : opacity}
      lineWidth={isSelected ? 2 : 1}
    />
  );
}

// ----- Legend overlay -----

function GalaxyLegend({ weights, nodeCount }: { weights: Record<string, number>; nodeCount: number }) {
  return (
    <div className="pointer-events-none absolute bottom-4 left-4">
      <div className="panel px-4 py-3 text-[10px] font-mono">
        <div className="mb-1 text-primary/50">{nodeCount} candidates</div>
        <div className="space-y-0.5 text-primary/40">
          <div className="flex items-center gap-2">
            <span className="inline-block h-2 w-2 rounded-full bg-starlight" />
            <span>Score &gt; 0.8</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-block h-2 w-2 rounded-full bg-trust" />
            <span>Score 0.5–0.8</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-block h-2 w-2 rounded-full bg-primary/60" />
            <span>Score &lt; 0.5 / near-miss</span>
          </div>
        </div>
      </div>
    </div>
  );
}

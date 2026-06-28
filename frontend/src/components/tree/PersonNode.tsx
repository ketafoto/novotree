import { memo, useState, useCallback } from 'react';
import { Handle, Position } from '@xyflow/react';
import { CheckCircle2 } from 'lucide-react';
import type { TreeNode } from '../../types/models';
import { MaleSilhouette } from './MaleSilhouette';
import { FemaleSilhouette } from './FemaleSilhouette';
import { PersonTooltip } from './PersonTooltip';
import { PhotoCarousel } from './PhotoCarousel';
import { useIsMobileViewport } from '../../hooks/useIsMobileViewport';

interface PersonNodeData extends TreeNode {
  isFocus: boolean;
  carouselIntervalMs?: number;
  isFullTree?: boolean;
  // Privacy-request selection mode (PRIVACY_DESIGN.md 3.9). selectMode hints
  // "click to check"; isSelected draws the checked ring + badge.
  selectMode?: boolean;
  isSelected?: boolean;
}

/**
 * Custom React Flow node for rendering a person in the family tree.
 * Shows a rectangular (slightly rounded) portrait, name, and birth/death years.
 * When hovered, cycles through all photos with a blur cross-fade transition.
 */
export const PersonNode = memo(function PersonNode({
  data,
}: {
  data: PersonNodeData;
}) {
  const [showTooltip, setShowTooltip] = useState(false);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [isHovering, setIsHovering] = useState(false);
  const isMobileViewport = useIsMobileViewport();

  const handleMouseEnter = useCallback(
    (e: React.MouseEvent) => {
      if (isMobileViewport) return;
      setTooltipPos({ x: e.clientX, y: e.clientY });
      setShowTooltip(true);
      setIsHovering(true);
    },
    [isMobileViewport],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (isMobileViewport) return;
      setTooltipPos({ x: e.clientX, y: e.clientY });
    },
    [isMobileViewport],
  );

  const handleMouseLeave = useCallback(() => {
    if (isMobileViewport) return;
    setShowTooltip(false);
    setIsHovering(false);
  }, [isMobileViewport]);

  const formatYear = (
    exactDate?: string,
    approxDate?: string,
  ): string => {
    if (exactDate) {
      return exactDate.substring(0, 4);
    }
    if (approxDate) {
      const parts = approxDate.split(/\s+/);
      for (const part of parts.reverse()) {
        if (/^\d{4}$/.test(part)) return `~${part}`;
      }
      return approxDate;
    }
    return '?';
  };

  const birthYear = formatYear(data.birth_date, data.birth_date_approx);
  const deathYear = data.death_date || data.death_date_approx
    ? formatYear(data.death_date, data.death_date_approx)
    : null;

  const lifespan = deathYear ? `${birthYear} – ${deathYear}` : birthYear !== '?' ? `b. ${birthYear}` : '';

  // Selected (privacy-request 3.9) wins the ring so a checked person reads as
  // checked even when they are also the focus; emerald is distinct from the
  // amber focus ring.
  const borderColor = data.isSelected
    ? 'ring-emerald-500 ring-4'
    : data.isFocus
      ? 'ring-amber-400 ring-4'
      : 'ring-gray-300 ring-2';

  const hasPhotos = data.photos && data.photos.length > 0;

  return (
    <>
      <Handle type="target" position={Position.Top} className="!bg-transparent !border-0 !w-0 !h-0" />
      <Handle type="source" position={Position.Bottom} className="!bg-transparent !border-0 !w-0 !h-0" />

      <div
        className="flex flex-col items-center gap-1 cursor-pointer select-none group"
        style={{ width: 140 }}
        onMouseEnter={handleMouseEnter}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        {/* Portrait */}
        <div
          className={`relative w-[88px] h-[110px] rounded-xl overflow-hidden ring ${borderColor} ${
            data.isFocus && !data.isSelected ? 'shadow-lg shadow-amber-200' : ''
          } bg-white transition-shadow group-hover:shadow-md`}
        >
          {/* Check badge -- only when checked in selection mode. */}
          {data.isSelected && (
            <span className="absolute top-1 right-1 z-10 rounded-full bg-white/90">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            </span>
          )}
          {hasPhotos ? (
            <PhotoCarousel
              photos={data.photos}
              alt={data.display_name}
              isHovering={isHovering}
              intervalMs={data.carouselIntervalMs}
            />
          ) : data.photo_url ? (
            <img
              src={data.photo_url}
              alt={data.display_name}
              className="w-full h-full object-cover"
              loading="lazy"
            />
          ) : data.sex_code === 'F' ? (
            <FemaleSilhouette className="w-full h-full" />
          ) : (
            <MaleSilhouette className="w-full h-full" />
          )}
        </div>

        {/* Name */}
        <div className="text-center leading-tight max-w-[140px]">
          <p className="text-xs font-semibold text-gray-800 truncate" title={data.display_name}>
            {data.display_name}
          </p>
          {lifespan && (
            <p className="text-[10px] text-gray-500">{lifespan}</p>
          )}
        </div>
      </div>

      {showTooltip && (
        <PersonTooltip
          data={data}
          position={tooltipPos}
          isFullTree={data.isFullTree}
        />
      )}
    </>
  );
});

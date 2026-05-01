import { useState, useRef, useCallback, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ReactFlowProvider } from '@xyflow/react';
import { X, Download, GitBranch, UserPlus, Menu } from 'lucide-react';

import { treeApi } from '../../api/tree';
import { individualsApi } from '../../api/individuals';
import { Spinner } from '../../components/common/Spinner';
import { TreeCanvas } from '../../components/tree/TreeCanvas';
import { DepthSlider } from '../../components/tree/DepthSlider';
import { TreeLegend } from '../../components/tree/TreeLegend';
import { ExportControls } from '../../components/tree/ExportControls';
import { ContributeDialog } from '../../components/common/ContributeDialog';
import { MobilePersonSheet } from '../../components/tree/MobilePersonSheet';
import { useAuth } from '../../contexts/AuthContext';
import { isPublicApp } from '../../config/appMode';
import { formatIndividualName, getLatestName } from '../../utils/nameUtils';
import { useIsMobileViewport } from '../../hooks/useIsMobileViewport';

/**
 * Main tree visualization page.
 * Shows a family tree centered on an individual with depth controls,
 * export functionality, and a legend.
 */
export function TreePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isViewer, editor, viewerOwnerId } = useAuth();
  const individualId = Number(id);
  const isMobileViewport = useIsMobileViewport();

  const [ancestorDepth, setAncestorDepth] = useState(1);
  const [descendantDepth, setDescendantDepth] = useState(1);
  const [photoIntervalSec, setPhotoIntervalSec] = useState(3);
  const [showExport, setShowExport] = useState(false);
  const [showContribute, setShowContribute] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [mobileSheetPersonId, setMobileSheetPersonId] = useState<number | null>(null);
  const viewportRef = useRef<HTMLDivElement | null>(null);

  const ownerOwnerId = editor?.owner_id ?? viewerOwnerId ?? '';

  // Reset depths when navigating to a different person's tree
  useEffect(() => {
    setAncestorDepth(1);
    setDescendantDepth(1);
    setMobileSheetPersonId(null);
  }, [individualId]);

  // Fetch focus individual info (for the header)
  const { data: individual } = useQuery({
    queryKey: ['individuals', id],
    queryFn: () => individualsApi.get(individualId),
    enabled: !!id,
  });

  // Fetch tree data
  const { data: treeData, isLoading, isError } = useQuery({
    queryKey: ['tree', individualId, { ancestor_depth: ancestorDepth, descendant_depth: descendantDepth }],
    queryFn: () =>
      treeApi.getTree(individualId, {
        ancestor_depth: ancestorDepth,
        descendant_depth: descendantDepth,
      }),
    enabled: !!id,
  });

  // Close handler: go back to previous page
  const handleClose = useCallback(() => {
    // Try to go back in history; if there's no history, go to the individual detail page
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate(isPublicApp ? '/tree' : `/individuals/${id}`);
    }
  }, [navigate, id]);

  // Single-click on desktop: re-center tree on that person.
  // On mobile: open the bottom sheet instead (tap fights with hover/double-tap).
  const handlePersonClick = useCallback(
    (clickedId: number) => {
      if (isMobileViewport) {
        setMobileSheetPersonId(clickedId);
        return;
      }
      if (clickedId !== individualId) {
        navigate(`/individuals/${clickedId}/tree`, { replace: true });
      }
    },
    [navigate, individualId, isMobileViewport],
  );

  // Double-click any person: open their detail page (desktop only — touch
  // double-tap is unreliable, mobile uses the sheet's "View profile" button).
  const handlePersonDoubleClick = useCallback(
    (clickedId: number) => {
      if (isMobileViewport) return;
      navigate(`/individuals/${clickedId}`);
    },
    [navigate, isMobileViewport],
  );

  // Export helpers
  const getExportElement = useCallback(() => {
    if (!viewportRef.current) return null;
    // Find the React Flow viewport element inside our container
    return viewportRef.current.querySelector('.react-flow__viewport') as HTMLElement | null;
  }, []);

  const displayName = individual
    ? formatIndividualName(getLatestName(individual.names))
    : 'Individual';

  // Find the tapped person's tree-node data for the mobile sheet
  const mobileSheetNode = mobileSheetPersonId !== null && treeData
    ? treeData.nodes.find((n) => n.id === mobileSheetPersonId) ?? null
    : null;

  const handleMobileSheetRecenter = useCallback(() => {
    if (mobileSheetPersonId === null) return;
    setMobileSheetPersonId(null);
    setMobileMenuOpen(false);
    if (mobileSheetPersonId !== individualId) {
      navigate(`/individuals/${mobileSheetPersonId}/tree`, { replace: true });
    }
  }, [mobileSheetPersonId, individualId, navigate]);

  const handleMobileSheetViewProfile = useCallback(() => {
    if (mobileSheetPersonId === null) return;
    setMobileSheetPersonId(null);
    setMobileMenuOpen(false);
    navigate(`/individuals/${mobileSheetPersonId}`);
  }, [mobileSheetPersonId, navigate]);

  return (
    <div className="fixed inset-0 z-50 bg-slate-50 flex flex-col">
      {/* Header toolbar */}
      <div className="flex items-center justify-between px-4 py-2 bg-white border-b border-gray-200 shadow-sm">
        <div className="flex items-center gap-3 min-w-0">
          <GitBranch className="w-5 h-5 text-emerald-600 flex-shrink-0" />
          <div className="min-w-0">
            <h1 className="text-sm font-semibold text-gray-900 truncate">
              Family Tree: {displayName}
            </h1>
            {individual?.gedcom_id && (
              <p className="text-[10px] text-gray-400 truncate">{individual.gedcom_id}</p>
            )}
          </div>
        </div>

        {/* Desktop toolbar — full controls inline */}
        <div className="hidden md:flex items-center gap-2">
          {/* Depth sliders */}
          {treeData && (
            <DepthSlider
              ancestorDepth={ancestorDepth}
              descendantDepth={descendantDepth}
              maxAncestorDepth={treeData.max_ancestor_depth}
              maxDescendantDepth={treeData.max_descendant_depth}
              onAncestorDepthChange={setAncestorDepth}
              onDescendantDepthChange={setDescendantDepth}
            />
          )}

          <div className="flex items-center gap-2 px-2 py-1 bg-slate-100 rounded-lg border border-slate-200">
            <label htmlFor="photo-interval-slider" className="text-[11px] text-slate-600 whitespace-nowrap">
              Photo {photoIntervalSec}s
            </label>
            <input
              id="photo-interval-slider"
              type="range"
              min={1}
              max={10}
              step={1}
              value={photoIntervalSec}
              onChange={(e) => setPhotoIntervalSec(Number(e.target.value))}
              className="w-20 accent-emerald-600"
              title="Photo carousel interval (1-10 seconds)"
            />
          </div>

          {/* Contribute button — visible to viewers (share token) only */}
          {isViewer && ownerOwnerId && (
            <button
              onClick={() => setShowContribute(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700 transition-colors"
              title="Sign up as a contributor to this tree"
            >
              <UserPlus className="w-3.5 h-3.5" />
              Wanna contribute to this tree? 🌿
            </button>
          )}

          {/* Export button */}
          <button
            onClick={() => setShowExport(!showExport)}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            title="Export as image"
          >
            <Download className="w-4 h-4 text-gray-600" />
          </button>

          {/* Close button */}
          <button
            onClick={handleClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            title="Close tree view"
          >
            <X className="w-5 h-5 text-gray-600" />
          </button>
        </div>

        {/* Mobile toolbar — hamburger + close only */}
        <div className="flex md:hidden items-center gap-1 flex-shrink-0">
          <button
            onClick={() => setMobileMenuOpen((open) => !open)}
            className="p-2 hover:bg-gray-100 rounded-lg"
            aria-label="Toggle tree controls"
            aria-expanded={mobileMenuOpen}
          >
            <Menu className="w-5 h-5 text-gray-600" />
          </button>
          <button
            onClick={handleClose}
            className="p-2 hover:bg-gray-100 rounded-lg"
            aria-label="Close tree view"
          >
            <X className="w-5 h-5 text-gray-600" />
          </button>
        </div>
      </div>

      {/* Mobile drawer — full controls stacked when hamburger is open */}
      {isMobileViewport && mobileMenuOpen && (
        <div className="md:hidden bg-white border-b border-gray-200 shadow-sm px-4 py-3 space-y-3">
          {treeData && (
            <DepthSlider
              ancestorDepth={ancestorDepth}
              descendantDepth={descendantDepth}
              maxAncestorDepth={treeData.max_ancestor_depth}
              maxDescendantDepth={treeData.max_descendant_depth}
              onAncestorDepthChange={setAncestorDepth}
              onDescendantDepthChange={setDescendantDepth}
            />
          )}

          <div className="flex items-center gap-2 px-2 py-2 bg-slate-100 rounded-lg border border-slate-200">
            <label htmlFor="photo-interval-slider-mobile" className="text-xs text-slate-600 whitespace-nowrap">
              Photo {photoIntervalSec}s
            </label>
            <input
              id="photo-interval-slider-mobile"
              type="range"
              min={1}
              max={10}
              step={1}
              value={photoIntervalSec}
              onChange={(e) => setPhotoIntervalSec(Number(e.target.value))}
              className="flex-1 accent-emerald-600"
              title="Photo carousel interval (1-10 seconds)"
            />
          </div>

          {isViewer && ownerOwnerId && (
            <button
              onClick={() => {
                setShowContribute(true);
                setMobileMenuOpen(false);
              }}
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg active:bg-blue-700"
            >
              <UserPlus className="w-4 h-4" />
              Contribute to this tree 🌿
            </button>
          )}

          <button
            onClick={() => {
              setShowExport(true);
              setMobileMenuOpen(false);
            }}
            className="w-full flex items-center justify-center gap-2 py-2.5 bg-white text-gray-700 text-sm font-medium rounded-lg border border-gray-300 active:bg-gray-50"
          >
            <Download className="w-4 h-4" />
            Export as image
          </button>
        </div>
      )}

      {/* Main canvas area */}
      <div className="flex-1 relative overflow-hidden">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-10">
            <div className="flex flex-col items-center gap-2">
              <Spinner size="lg" />
              <p className="text-sm text-gray-500">Loading family tree...</p>
            </div>
          </div>
        )}

        {isError && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <p className="text-gray-600 mb-2">Failed to load family tree</p>
              <button
                onClick={handleClose}
                className="text-emerald-600 hover:underline text-sm"
              >
                Go back
              </button>
            </div>
          </div>
        )}

        {treeData && (
          <ReactFlowProvider key={individualId}>
            <TreeCanvas
              data={treeData}
              photoIntervalMs={photoIntervalSec * 1000}
              viewportRef={viewportRef}
              onPersonClick={handlePersonClick}
              onPersonDoubleClick={handlePersonDoubleClick}
            />
          </ReactFlowProvider>
        )}

        {/* Legend - bottom right */}
        <div className="absolute bottom-4 right-4 z-10">
          <TreeLegend />
        </div>

        {/* Export panel - top right */}
        {showExport && (
          <div className="absolute top-4 right-4 z-10">
            <ExportControls
              getElement={getExportElement}
              onClose={() => setShowExport(false)}
            />
          </div>
        )}
      </div>

      {showContribute && (
        <ContributeDialog
          ownerOwnerId={ownerOwnerId}
          onClose={() => setShowContribute(false)}
        />
      )}

      {mobileSheetNode && (
        <MobilePersonSheet
          data={mobileSheetNode}
          isFocus={mobileSheetNode.id === individualId}
          recenterLabel="Center tree on this person"
          onRecenter={handleMobileSheetRecenter}
          onViewProfile={handleMobileSheetViewProfile}
          onClose={() => setMobileSheetPersonId(null)}
        />
      )}
    </div>
  );
}

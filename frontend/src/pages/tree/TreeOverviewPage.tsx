import { useState, useRef, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ReactFlowProvider } from '@xyflow/react';
import { X, Download, GitBranch, UserPlus, Menu } from 'lucide-react';

import { treeApi } from '../../api/tree';
import { Spinner } from '../../components/common/Spinner';
import { TreeCanvas } from '../../components/tree/TreeCanvas';
import { TreeLegend } from '../../components/tree/TreeLegend';
import { ExportControls } from '../../components/tree/ExportControls';
import { ContributeDialog } from '../../components/common/ContributeDialog';
import { MobilePersonSheet } from '../../components/tree/MobilePersonSheet';
import { PrivacyLinks } from '../../components/layout/PrivacyLinks';
import { isLocalApp } from '../../config/appMode';
import { useAuth } from '../../contexts/AuthContext';
import { useIsMobileViewport } from '../../hooks/useIsMobileViewport';

/**
 * Full tree overview page.
 * Shows every individual in the database — even disconnected sub-trees —
 * laid out side by side.
 */
export function TreeOverviewPage() {
  const navigate = useNavigate();
  const { isViewer, editor, viewerOwnerId } = useAuth();
  const isMobileViewport = useIsMobileViewport();
  const [photoIntervalSec, setPhotoIntervalSec] = useState(3);
  const [showExport, setShowExport] = useState(false);
  const [showContribute, setShowContribute] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [mobileSheetPersonId, setMobileSheetPersonId] = useState<number | null>(null);
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const clickTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // For authenticated editors, owner_id comes from the session; for viewers, from the share token
  const ownerOwnerId = editor?.owner_id ?? viewerOwnerId ?? '';

  const { data: treeData, isLoading, isError } = useQuery({
    queryKey: ['tree', 'full'],
    queryFn: () => treeApi.getFullTree(),
  });

  const handleClose = useCallback(() => {
    if (window.history.length > 1) {
      navigate(-1);
    } else {
      navigate('/');
    }
  }, [navigate]);

  const handlePersonClick = useCallback(
    (clickedId: number) => {
      if (isMobileViewport) {
        setMobileSheetPersonId(clickedId);
        return;
      }
      if (clickTimerRef.current) clearTimeout(clickTimerRef.current);
      clickTimerRef.current = setTimeout(() => {
        navigate(`/individuals/${clickedId}/tree`);
      }, 250);
    },
    [navigate, isMobileViewport],
  );

  const handlePersonDoubleClick = useCallback(
    (clickedId: number) => {
      if (isMobileViewport) return;
      if (clickTimerRef.current) {
        clearTimeout(clickTimerRef.current);
        clickTimerRef.current = null;
      }
      navigate(`/individuals/${clickedId}`);
    },
    [navigate, isMobileViewport],
  );

  useEffect(() => () => {
    if (clickTimerRef.current) clearTimeout(clickTimerRef.current);
  }, []);

  const getExportElement = useCallback(() => {
    if (!viewportRef.current) return null;
    return viewportRef.current.querySelector('.react-flow__viewport') as HTMLElement | null;
  }, []);

  const mobileSheetNode = mobileSheetPersonId !== null && treeData
    ? treeData.nodes.find((n) => n.id === mobileSheetPersonId) ?? null
    : null;

  const handleMobileSheetRecenter = useCallback(() => {
    if (mobileSheetPersonId === null) return;
    const targetId = mobileSheetPersonId;
    setMobileSheetPersonId(null);
    setMobileMenuOpen(false);
    navigate(`/individuals/${targetId}/tree`);
  }, [mobileSheetPersonId, navigate]);

  const handleMobileSheetViewProfile = useCallback(() => {
    if (mobileSheetPersonId === null) return;
    const targetId = mobileSheetPersonId;
    setMobileSheetPersonId(null);
    setMobileMenuOpen(false);
    navigate(`/individuals/${targetId}`);
  }, [mobileSheetPersonId, navigate]);

  return (
    <div className="fixed inset-0 z-50 bg-slate-50 flex flex-col">
      <div className="flex items-center justify-between px-4 py-2 bg-white border-b border-gray-200 shadow-sm">
        <div className="flex items-center gap-3 min-w-0">
          <GitBranch className="w-5 h-5 text-emerald-600 flex-shrink-0" />
          <h1 className="text-sm font-semibold text-gray-900 truncate">
            Full Family Tree
          </h1>
        </div>

        {/* Desktop toolbar */}
        <div className="hidden md:flex items-center gap-2">
          <div className="flex items-center gap-2 px-2 py-1 bg-slate-100 rounded-lg border border-slate-200">
            <label htmlFor="photo-interval-overview-slider" className="text-[11px] text-slate-600 whitespace-nowrap">
              Photo {photoIntervalSec}s
            </label>
            <input
              id="photo-interval-overview-slider"
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

          {/* Privacy links — see TreePage for rationale (fullscreen overlay
              hides the global PrivacyFooter; critical path for viewers). */}
          {!isLocalApp && (
            <PrivacyLinks className="text-[11px] text-gray-500 px-2" />
          )}

          <button
            onClick={() => setShowExport(!showExport)}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            title="Export as image"
          >
            <Download className="w-4 h-4 text-gray-600" />
          </button>

          <button
            onClick={handleClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            title="Close tree view"
          >
            <X className="w-5 h-5 text-gray-600" />
          </button>
        </div>

        {/* Mobile toolbar */}
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

      {/* Mobile drawer */}
      {isMobileViewport && mobileMenuOpen && (
        <div className="md:hidden bg-white border-b border-gray-200 shadow-sm px-4 py-3 space-y-3">
          <div className="flex items-center gap-2 px-2 py-2 bg-slate-100 rounded-lg border border-slate-200">
            <label htmlFor="photo-interval-overview-slider-mobile" className="text-xs text-slate-600 whitespace-nowrap">
              Photo {photoIntervalSec}s
            </label>
            <input
              id="photo-interval-overview-slider-mobile"
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

          {!isLocalApp && (
            <div className="flex items-center justify-center pt-1 text-xs text-gray-500">
              <PrivacyLinks />
            </div>
          )}
        </div>
      )}

      <div className="flex-1 relative overflow-hidden">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-10">
            <div className="flex flex-col items-center gap-2">
              <Spinner size="lg" />
              <p className="text-sm text-gray-500">Loading full tree...</p>
            </div>
          </div>
        )}

        {isError && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <p className="text-gray-600 mb-2">Failed to load full tree</p>
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
          <ReactFlowProvider>
            <TreeCanvas
              data={treeData}
              photoIntervalMs={photoIntervalSec * 1000}
              viewportRef={viewportRef}
              onPersonClick={handlePersonClick}
              onPersonDoubleClick={handlePersonDoubleClick}
              isFullTree
            />
          </ReactFlowProvider>
        )}

        <div className="absolute bottom-4 right-4 z-10">
          <TreeLegend />
        </div>

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
          isFocus={false}
          recenterLabel="View this person's tree"
          onRecenter={handleMobileSheetRecenter}
          onViewProfile={handleMobileSheetViewProfile}
          onClose={() => setMobileSheetPersonId(null)}
        />
      )}
    </div>
  );
}

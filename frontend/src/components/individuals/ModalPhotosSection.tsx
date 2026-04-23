import { useRef, useState } from 'react';
import { Camera, Edit2, Film, Music, Plus, Star, Trash2 } from 'lucide-react';
import { Button } from '../common/Button';
import { Modal } from '../common/Modal';
import { mediaApi } from '../../api/media';
import type { Media } from '../../types/models';

const PHOTO = 'photo';
const AUDIO = 'audio';
const VIDEO = 'video';

interface ModalPhotosSectionProps {
  open: boolean;
  onClose: () => void;
  media: Media[];
  photoCacheBust: number;
  onAddPhoto: () => void;
  onAddAudio: () => void;
  onAddVideo: () => void;
  onEditPhoto: (item: Media) => void;
  onSetDefault: (id: number) => void;
  onDelete: (id: number) => void;
  readOnly?: boolean;
}

export function ModalPhotosSection({
  open,
  onClose,
  media,
  photoCacheBust,
  onAddPhoto,
  onAddAudio,
  onAddVideo,
  onEditPhoto,
  onSetDefault,
  onDelete,
  readOnly = false,
}: ModalPhotosSectionProps) {
  const photos = media.filter((m) => m.media_type_code === PHOTO);
  const audioItems = media.filter((m) => m.media_type_code === AUDIO);
  const videoItems = media.filter((m) => m.media_type_code === VIDEO);

  const [fabOpen, setFabOpen] = useState(false);
  const fabCloseTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onFabEnter = () => {
    if (fabCloseTimer.current) clearTimeout(fabCloseTimer.current);
    setFabOpen(true);
  };
  const onFabLeave = () => {
    fabCloseTimer.current = setTimeout(() => setFabOpen(false), 80);
  };

  return (
    <Modal open={open} onClose={onClose} title="Media" wide>
      <div className="space-y-5">

        {media.length === 0 && (
          <p className="text-center text-gray-500 text-sm py-6">No media yet</p>
        )}

        {/* Photos */}
        {photos.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Photos</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {photos.map((item) => (
                <div key={item.id} className="group relative">
                  <div
                    className={`w-full aspect-[4/5] bg-gray-100 rounded-lg overflow-hidden ring-2 ${
                      item.is_default ? 'ring-amber-400' : 'ring-transparent'
                    }`}
                  >
                    <img
                      src={mediaApi.getFileUrl(item.id, { v: photoCacheBust })}
                      alt={`Age ${item.age_on_photo ?? '?'}`}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                  </div>
                  <span className="absolute bottom-1 left-1 bg-black/60 text-white text-[10px] px-1.5 py-0.5 rounded">
                    age {item.age_on_photo ?? '?'}
                  </span>
                  {item.is_default && (
                    <Star className="absolute top-1 right-1 w-4 h-4 text-amber-400 fill-amber-400" />
                  )}
                  {!readOnly && (
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors rounded-lg flex items-center justify-center gap-1 opacity-0 group-hover:opacity-100">
                      <button
                        type="button"
                        onClick={() => onEditPhoto(item)}
                        className="p-1.5 bg-white/90 rounded-full hover:bg-white"
                        title="Edit crop"
                      >
                        <Edit2 className="w-3.5 h-3.5 text-emerald-600" />
                      </button>
                      {!item.is_default && (
                        <button
                          type="button"
                          onClick={() => onSetDefault(item.id)}
                          className="p-1.5 bg-white/90 rounded-full hover:bg-white"
                          title="Set as default"
                        >
                          <Star className="w-3.5 h-3.5 text-amber-500" />
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => window.confirm('Delete this photo?') && onDelete(item.id)}
                        className="p-1.5 bg-white/90 rounded-full hover:bg-white"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5 text-red-500" />
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Audio */}
        {audioItems.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Audio</p>
            <div className="space-y-2">
              {audioItems.map((item) => (
                <div key={item.id} className="flex items-start gap-3 p-3 border border-gray-200 rounded-lg">
                  <Music className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    {item.description && (
                      <p className="text-sm text-gray-700 mb-1 truncate">{item.description}</p>
                    )}
                    <audio controls src={mediaApi.getFileUrl(item.id)} className="w-full" />
                  </div>
                  {!readOnly && (
                    <button
                      type="button"
                      onClick={() => window.confirm('Delete this audio?') && onDelete(item.id)}
                      className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded flex-shrink-0"
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Video */}
        {videoItems.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Video</p>
            <div className="space-y-3">
              {videoItems.map((item) => (
                <div key={item.id} className="border border-gray-200 rounded-lg overflow-hidden">
                  <video controls src={mediaApi.getFileUrl(item.id)} className="w-full max-h-64" />
                  <div className="flex items-center justify-between px-3 py-2">
                    <p className="text-sm text-gray-600 truncate">
                      {item.description || 'Video'}
                    </p>
                    {!readOnly && (
                      <button
                        type="button"
                        onClick={() => window.confirm('Delete this video?') && onDelete(item.id)}
                        className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded flex-shrink-0 ml-2"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Sticky footer: Close left, speed-dial FAB right */}
        <div className="sticky bottom-0 -mx-6 px-6 pb-1 pt-8 bg-gradient-to-t from-white from-60% to-transparent flex items-end justify-between">
          <Button type="button" variant="secondary" onClick={onClose}>Close</Button>

          {!readOnly && (
            <div className="relative">
              {/* Speed-dial options — fan upward, bridged by shared enter/leave handlers */}
              <div
                onMouseEnter={onFabEnter}
                onMouseLeave={onFabLeave}
                className={`absolute bottom-full right-0 mb-3 flex flex-col items-end gap-2
                            transition-all duration-150
                            ${fabOpen ? 'opacity-100 pointer-events-auto translate-y-0' : 'opacity-0 pointer-events-none translate-y-1'}`}
              >
                <button
                  type="button"
                  onClick={onAddVideo}
                  className="flex items-center gap-2 bg-white shadow-md border border-gray-200 rounded-full pl-3 pr-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 whitespace-nowrap"
                >
                  <Film className="w-4 h-4 text-purple-500" />
                  Add Video
                </button>
                <button
                  type="button"
                  onClick={onAddAudio}
                  className="flex items-center gap-2 bg-white shadow-md border border-gray-200 rounded-full pl-3 pr-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 whitespace-nowrap"
                >
                  <Music className="w-4 h-4 text-blue-500" />
                  Add Audio
                </button>
                <button
                  type="button"
                  onClick={onAddPhoto}
                  className="flex items-center gap-2 bg-white shadow-md border border-gray-200 rounded-full pl-3 pr-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 whitespace-nowrap"
                >
                  <Camera className="w-4 h-4 text-emerald-500" />
                  Add Photo
                </button>
              </div>

              {/* FAB trigger */}
              <button
                type="button"
                title="Add media"
                onMouseEnter={onFabEnter}
                onMouseLeave={onFabLeave}
                className="w-12 h-12 bg-emerald-500 hover:bg-emerald-600 text-white rounded-full shadow-lg flex items-center justify-center transition-colors"
              >
                <Plus className={`w-6 h-6 transition-transform duration-200 ${fabOpen ? 'rotate-45' : ''}`} />
              </button>
            </div>
          )}
        </div>

      </div>
    </Modal>
  );
}

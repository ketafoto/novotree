import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  Trash2,
  Calendar,
  Download,
  MapPin,
  Heart,
  Image,
  GitBranch,
  Star,
  Music,
  Film,
  Info,
} from 'lucide-react';
import { individualsApi } from '../../api/individuals';
import { familiesApi } from '../../api/families';
import { eventsApi } from '../../api/events';
import { typesApi } from '../../api/types';
import { mediaApi } from '../../api/media';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { Spinner } from '../../components/common/Spinner';
import { TranslateButton } from '../../components/common/TranslateButton';
import { PhotoUploadDialog } from '../../components/photo/PhotoUploadDialog';
import { EventFormDialog } from '../../components/events/EventFormDialog';
import { ModalBasicInfo } from '../../components/individuals/ModalBasicInfo';
import { ModalNames } from '../../components/individuals/ModalNames';
import { ModalBirth } from '../../components/individuals/ModalBirth';
import { ModalDeath } from '../../components/individuals/ModalDeath';
import { ModalNotes } from '../../components/individuals/ModalNotes';
import { ModalEventsSection } from '../../components/individuals/ModalEventsSection';
import { ModalPhotosSection } from '../../components/individuals/ModalPhotosSection';
import { ModalFamiliesSection } from '../../components/individuals/ModalFamiliesSection';
import toast from 'react-hot-toast';
import { apiErrorMessage } from '../../utils/apiError';
import { formatIndividualName, getLatestName } from '../../utils/nameUtils';
import { sortEventsChronologically } from '../../utils/eventSort';
import { saveBlob } from '../../utils/saveBlob';
import { useAuth } from '../../contexts/AuthContext';
import { useSensitiveView } from '../../contexts/SensitiveViewContext';
import { SensitiveInfo } from '../../components/common/SensitiveInfo';
import { SensitiveCheckbox } from '../../components/common/SensitiveCheckbox';
import { SensitiveViewToggle } from '../../components/common/SensitiveViewToggle';
import { eventIsSensitive, individualIsMinor, minorDataExplanation } from '../../constants/sensitiveData';
import { usePrivacyConfig } from '../../hooks/usePrivacyConfig';
import type { Event, Media } from '../../types/models';

type SectionModal = 'basic' | 'names' | 'birth' | 'death' | 'notes' | 'events' | 'photos' | 'families' | null;

interface IndividualDetailPageProps {
  readOnly?: boolean;
}

export function IndividualDetailPage({ readOnly = false }: IndividualDetailPageProps) {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isOwner } = useAuth();

  const { data: individual, isLoading, isError, error } = useQuery({
    queryKey: ['individuals', id],
    queryFn: () => individualsApi.get(Number(id)),
    enabled: !!id,
  });

  const { data: families } = useQuery({
    queryKey: ['families'],
    queryFn: () => familiesApi.list(),
  });

  const { data: events } = useQuery({
    queryKey: ['events', { individual_id: Number(id) }],
    queryFn: () => eventsApi.list({ individual_id: Number(id) }),
    enabled: !!id,
  });

  const { data: eventTypes } = useQuery({
    queryKey: ['types', 'events'],
    queryFn: typesApi.getEventTypes,
  });
  const eventTypeLabel = (code: string) =>
    eventTypes?.find((t) => t.code === code)?.description ?? code;

  const { data: media } = useQuery({
    queryKey: ['media', { individual_id: Number(id) }],
    queryFn: () => mediaApi.list({ individual_id: Number(id) }),
    enabled: !!id,
  });

  const { config: privacyConfig } = usePrivacyConfig();
  const childThreshold = privacyConfig?.child_age_threshold_years ?? 16;
  // GDPR Art. 8: a living minor needs the Owner's parental-consent confirmation
  // before their photos can be uploaded. The server is the real gate (media.py);
  // this drives the in-dialog checkbox and the detail-page consent control.
  //
  const isMinor = individual ? individualIsMinor(individual, childThreshold) : false;
  const needsParentalConsent = isMinor && !individual?.parental_consent;

  const [showPhotoDialog, setShowPhotoDialog] = useState(false);
  const [editingPhoto, setEditingPhoto] = useState<Media | null>(null);
  const [newPhotoSrc, setNewPhotoSrc] = useState<string | null>(null);
  const [photoCacheBust, setPhotoCacheBust] = useState(() => Date.now());
  const addPhotoInputRef = useRef<HTMLInputElement>(null);
  const addAudioInputRef = useRef<HTMLInputElement>(null);
  const addVideoInputRef = useRef<HTMLInputElement>(null);

  const [eventDialogOpen, setEventDialogOpen] = useState(false);
  const [eventToEdit, setEventToEdit] = useState<Event | null>(null);
  const [sectionModal, setSectionModal] = useState<SectionModal>(null);

  // Owner-only, per-session shoulder-surfing guard (not access control, not
  // persisted). Default off: sensitive events/notes/photos are collapsed until
  // the Owner reveals them. Viewers (readOnly) never get this toggle.
  const { showSensitive, setShowSensitive } = useSensitiveView();

  useEffect(() => {
    return () => {
      if (newPhotoSrc) URL.revokeObjectURL(newPhotoSrc);
    };
  }, [newPhotoSrc]);

  const handleStartAddPhoto = () => {
    if (addPhotoInputRef.current) {
      addPhotoInputRef.current.value = '';
      addPhotoInputRef.current.click();
    }
  };

  const handleStartAddAudio = () => {
    if (addAudioInputRef.current) {
      addAudioInputRef.current.value = '';
      addAudioInputRef.current.click();
    }
  };

  const handleStartAddVideo = () => {
    if (addVideoInputRef.current) {
      addVideoInputRef.current.value = '';
      addVideoInputRef.current.click();
    }
  };

  const handleMediaFileSelected = (type: 'audio' | 'video') => (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    uploadMediaFileMutation.mutate({ file, type });
  };

  const handleAddPhotoFileSelected = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const objectUrl = URL.createObjectURL(file);
    setNewPhotoSrc((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return objectUrl;
    });
    setEditingPhoto(null);
    setSectionModal(null);
    setShowPhotoDialog(true);
  };

  const deleteMutation = useMutation({
    mutationFn: individualsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['individuals'] });
      toast.success('Individual deleted');
      if (window.history.length > 1) navigate(-1);
      else navigate('/individuals');
    },
    onError: (err) => {
      toast.error(apiErrorMessage(err, 'Failed to delete individual'));
    },
  });

  const setSensitiveMutation = useMutation({
    mutationFn: (value: boolean) => individualsApi.update(Number(id), { is_sensitive: value }),
    onSuccess: (_, value) => {
      queryClient.invalidateQueries({ queryKey: ['individuals', id] });
      queryClient.invalidateQueries({ queryKey: ['individuals'] });
      // The tree payloads embed each person's sensitivity flags, so they must
      // refetch too or the tree view shows a stale sensitive/not-sensitive state.
      queryClient.invalidateQueries({ queryKey: ['tree'] });
      toast.success(value ? 'Marked person sensitive' : 'Unmarked person');
    },
    onError: (err) => toast.error(apiErrorMessage(err, 'Failed to update sensitivity')),
  });

  const setParentalConsentMutation = useMutation({
    mutationFn: (value: boolean) => individualsApi.update(Number(id), { parental_consent: value }),
    onSuccess: (_, value) => {
      queryClient.invalidateQueries({ queryKey: ['individuals', id] });
      queryClient.invalidateQueries({ queryKey: ['individuals'] });
      queryClient.invalidateQueries({ queryKey: ['tree'] });
      toast.success(value ? 'Recorded parental consent' : 'Cleared parental consent');
    },
    onError: (err) => toast.error(apiErrorMessage(err, 'Failed to update parental consent')),
  });

  const deleteMediaMutation = useMutation({
    mutationFn: mediaApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['media', { individual_id: Number(id) }] });
      toast.success('Media deleted');
    },
    onError: (err) => toast.error(apiErrorMessage(err, 'Failed to delete media')),
  });

  const uploadMediaFileMutation = useMutation({
    mutationFn: ({ file, type }: { file: File; type: 'audio' | 'video' }) =>
      mediaApi.uploadMediaFile(file, Number(id), type),
    onSuccess: (_, { type }) => {
      queryClient.invalidateQueries({ queryKey: ['media', { individual_id: Number(id) }] });
      toast.success(`${type.charAt(0).toUpperCase() + type.slice(1)} uploaded`);
    },
    onError: (err) => toast.error(apiErrorMessage(err, 'Failed to upload media')),
  });

  const deleteEventMutation = useMutation({
    mutationFn: eventsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['events', { individual_id: Number(id) }] });
      toast.success('Event deleted');
    },
    onError: (err) => toast.error(apiErrorMessage(err, 'Failed to delete event')),
  });

  const setDefaultMutation = useMutation({
    mutationFn: mediaApi.setDefault,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['media', { individual_id: Number(id) }] });
      toast.success('Default photo updated');
    },
    onError: (err) => toast.error(apiErrorMessage(err, 'Failed to set default')),
  });

  const handlePhotoUpload = async ({
    blob,
    age,
    isDefault,
    sourceMediaId,
  }: {
    blob?: Blob;
    age: number;
    isDefault: boolean;
    sourceMediaId?: number;
  }) => {
    if (sourceMediaId && blob) {
      await mediaApi.recropPhoto({
        media_id: sourceMediaId,
        file: blob,
        age_on_photo: age,
        is_default: isDefault,
      });
      toast.success('Photo updated');
    } else if (sourceMediaId) {
      await mediaApi.update(sourceMediaId, {
        age_on_photo: age,
        is_default: isDefault,
      });
      toast.success('Photo updated');
    } else if (blob) {
      await mediaApi.uploadPhoto({
        file: blob,
        individual_id: Number(id),
        age_on_photo: age,
        is_default: isDefault,
      });
      toast.success('Photo uploaded');
    }
    queryClient.invalidateQueries({ queryKey: ['media', { individual_id: Number(id) }] });
    setPhotoCacheBust(Date.now());
    setEditingPhoto(null);
    setNewPhotoSrc((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
    setShowPhotoDialog(false);
  };

  const handleDelete = () => {
    const displayName = formatIndividualName(getLatestName(individual?.names ?? []));

    if (window.confirm(`Are you sure you want to delete "${displayName}"?`)) {
      deleteMutation.mutate(Number(id));
    }
  };

  const handleDataExport = async () => {
    try {
      const response = await individualsApi.dataExport(Number(id));
      const contentDisposition = response.headers['content-disposition'];
      let extractedFileName = `individual-${id}-data-export.json`;
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="?(.+?)"?$/);
        if (match) extractedFileName = match[1];
      }
      const blob = new Blob([response.data], { type: 'application/json' });
      await saveBlob(blob, extractedFileName);
    } catch (error) {
      toast.error(apiErrorMessage(error, 'Failed to export individual data'));
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" />
      </div>
    );
  }

  if (isError || !individual) {
    const is401 = (error as { response?: { status?: number } })?.response?.status === 401;
    return (
      <div className="text-center py-12">
        {(!readOnly || !is401) && (
          <p className="text-gray-600">
            {is401 ? 'Session expired — please log in again' : 'Individual not found'}
          </p>
        )}
        <Link to={readOnly ? '/tree' : '/individuals'} className="text-emerald-600 hover:underline">
          {readOnly ? 'Back to tree' : 'Back to list'}
        </Link>
      </div>
    );
  }

  const primaryName = getLatestName(individual.names);
  const displayName = formatIndividualName(primaryName);

  // The toggle is an Owner-only local guard; it never applies to viewers
  // (readOnly), whose payload is already filtered server-side per share token.
  const ownerCanToggle = !readOnly && isOwner;
  const hideSensitive = ownerCanToggle && !showSensitive;
  const notesAreSensitive = !!individual.notes_sensitive;
  const visibleEvents = (events ?? []).filter((ev) => !(hideSensitive && eventIsSensitive(ev)));
  const hiddenEventCount = (events?.length ?? 0) - visibleEvents.length;

  const cardDoubleClick = (section: SectionModal) => (!readOnly ? { onDoubleClick: () => setSectionModal(section) } : {});

  // Find families where this individual is a member
  const relatedFamilies = (families || []).filter((family) =>
    family.members.some((m) => m.individual_id === Number(id)) ||
    family.children.some((c) => c.child_id === Number(id))
  );
  const TYPE_ORDER: Record<string, number> = { photo: 0, audio: 1, video: 2 };
  const hiddenMediaCount = (media || []).filter((m) => hideSensitive && m.is_sensitive).length;
  const sortedAllMedia = [...(media || [])]
    .filter((m) => !(hideSensitive && m.is_sensitive))
    .sort((a, b) => {
    const ta = TYPE_ORDER[a.media_type_code ?? ''] ?? 3;
    const tb = TYPE_ORDER[b.media_type_code ?? ''] ?? 3;
    if (ta !== tb) return ta - tb;
    if (a.media_type_code === 'photo' && b.media_type_code === 'photo') {
      const ageA = a.age_on_photo ?? Number.POSITIVE_INFINITY;
      const ageB = b.age_on_photo ?? Number.POSITIVE_INFINITY;
      if (ageA !== ageB) return ageA - ageB;
    }
    return a.id - b.id;
  });
  const photoMedia = sortedAllMedia.filter((m) => m.media_type_code === 'photo');
  const audioCount = sortedAllMedia.filter((m) => m.media_type_code === 'audio').length;
  const videoCount = sortedAllMedia.filter((m) => m.media_type_code === 'video').length;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => window.history.length > 1 ? navigate(-1) : navigate(readOnly ? '/tree' : '/individuals')}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-gray-600" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{displayName}</h1>
            <p className="text-gray-600 mt-1">{individual.gedcom_id}</p>
            {individual.created_by && (
              <p className="text-xs text-gray-400 mt-0.5">Added by {individual.created_by_display_name || individual.created_by}</p>
            )}
            {/* Sensitive-view state lives next to the title (not in the action
                row) — it is a view setting, not a record action. */}
            {ownerCanToggle && (
              <div className="mt-2">
                <SensitiveViewToggle shown={showSensitive} onToggle={setShowSensitive} />
              </div>
            )}
          </div>
        </div>
        {/* Header actions: navigation + record actions only. */}
        <div className="flex items-center gap-2">
          <Link to={`/individuals/${id}/tree`}>
            <Button variant="secondary">
              <GitBranch className="w-4 h-4 mr-2" />
              View Tree
            </Button>
          </Link>
          {!readOnly && isOwner && (
            <Button
              variant="secondary"
              onClick={handleDataExport}
              title="Download a JSON file with every field, event, media reference, and contributor attribution for this person (right-of-access export)"
            >
              <Download className="w-4 h-4 mr-2" />
              Export data
            </Button>
          )}
          {!readOnly && (
            <Button variant="danger" onClick={handleDelete}>
              <Trash2 className="w-4 h-4 mr-2" />
              Delete
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Info */}
        <div className="lg:col-span-2 space-y-6">
          {/* Basic Info */}
          <Card title="Basic Information" {...cardDoubleClick('basic')}>
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <dt className="text-sm font-medium text-gray-500">Sex</dt>
                <dd className="mt-1 text-gray-900">{individual.sex_code || '-'}</dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">GEDCOM ID</dt>
                <dd className="mt-1 text-gray-900">{individual.gedcom_id || '-'}</dd>
              </div>
            </dl>
            {/* Whole-person sensitivity flag lives where the person's facts live,
                not in the page action row. Persists immediately on toggle. */}
            {!readOnly && isOwner && (
              <div className="mt-4">
                <SensitiveCheckbox
                  checked={!!individual.is_sensitive}
                  onChange={(c) => setSensitiveMutation.mutate(c)}
                  label="Mark this whole person sensitive (hide from share links)"
                />
              </div>
            )}
            {/* Parental consent (GDPR Art. 8): only relevant for a living minor.
                Persists immediately; clears the photo-upload gate when ticked. */}
            {!readOnly && isOwner && isMinor && (
              <div className="mt-3 flex gap-3 p-3 rounded-lg border border-sky-200 bg-sky-50">
                <Info className="w-5 h-5 flex-shrink-0 mt-0.5 text-sky-600" aria-hidden />
                <div className="space-y-1">
                  <label className="flex items-center gap-2 text-sm font-semibold text-sky-900">
                    <input
                      type="checkbox"
                      checked={!!individual.parental_consent}
                      onChange={(e) => setParentalConsentMutation.mutate(e.target.checked)}
                    />
                    I have parental consent to store this minor's data
                  </label>
                  <p className="text-xs text-sky-800">{minorDataExplanation(childThreshold)}</p>
                </div>
              </div>
            )}
          </Card>

          {/* Birth & Death on same row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <Card title="Birth" {...cardDoubleClick('birth')}>
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">
                  <Calendar className="w-5 h-5 text-emerald-600" />
                </div>
                <div>
                  <p className="font-medium text-gray-900">
                    {individual.birth_date || individual.birth_date_approx || 'No date recorded'}
                  </p>
                  {individual.birth_place ? (
                    <p className="text-gray-600 flex items-center gap-1 mt-1">
                      <MapPin className="w-4 h-4" />
                      {individual.birth_place}
                    </p>
                  ) : (
                    <p className="text-gray-500 text-sm mt-1">No place recorded</p>
                  )}
                </div>
              </div>
            </Card>
            <Card title="Death" {...cardDoubleClick('death')}>
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
                  <Calendar className="w-5 h-5 text-gray-600" />
                </div>
                <div>
                  <p className="font-medium text-gray-900">
                    {individual.death_date || individual.death_date_approx || 'No date recorded'}
                  </p>
                  {individual.death_place ? (
                    <p className="text-gray-600 flex items-center gap-1 mt-1">
                      <MapPin className="w-4 h-4" />
                      {individual.death_place}
                    </p>
                  ) : (
                    <p className="text-gray-500 text-sm mt-1">No place recorded</p>
                  )}
                </div>
              </div>
            </Card>
          </div>

          {/* Events */}
          <Card title="Events" {...cardDoubleClick('events')}>
            {(events?.length || 0) === 0 ? (
              <p className="text-gray-500 text-center py-4">No events recorded</p>
            ) : visibleEvents.length === 0 ? (
              <p className="text-gray-500 text-center py-4">
                {hiddenEventCount} sensitive event{hiddenEventCount === 1 ? '' : 's'} hidden — use "Show sensitive" to reveal.
              </p>
            ) : (
              <div className="divide-y divide-gray-100">
                {hiddenEventCount > 0 && (
                  <p className="text-xs text-gray-400 pb-2">
                    {hiddenEventCount} sensitive event{hiddenEventCount === 1 ? '' : 's'} hidden — use "Show sensitive" to reveal.
                  </p>
                )}
                {sortEventsChronologically(visibleEvents).map((ev) => (
                  <div key={ev.id} className="py-3 flex items-start gap-4">
                    <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
                      <Calendar className="w-4 h-4 text-blue-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-900">{eventTypeLabel(ev.event_type_code)}</p>
                      <p className="text-sm text-gray-600">
                        {ev.event_date || ev.event_date_approx}
                        {ev.event_place && ` • ${ev.event_place}`}
                      </p>
                      {ev.description && (
                        <p className="text-sm text-gray-500 mt-1">{ev.description}</p>
                      )}
                      {ev.created_by && (
                        <p className="text-xs text-gray-400 mt-0.5">Added by {ev.created_by_display_name || ev.created_by}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Notes */}
          <Card
            title="Notes"
            actions={individual.notes && !(hideSensitive && notesAreSensitive) ? <TranslateButton getText={individual.notes} /> : undefined}
            {...cardDoubleClick('notes')}
          >
            {hideSensitive && notesAreSensitive ? (
              <p className="text-gray-500 text-sm flex items-center gap-1">
                Sensitive notes hidden — use "Show sensitive" to reveal. <SensitiveInfo />
              </p>
            ) : individual.notes ? (
              <p className="text-gray-700 whitespace-pre-wrap">{individual.notes}</p>
            ) : (
              <p className="text-gray-500 text-sm">No notes recorded</p>
            )}
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Names */}
          <Card title="Names" {...cardDoubleClick('names')}>
            {individual.names.length === 0 ? (
              <p className="text-gray-500 text-sm">No names recorded</p>
            ) : (
              <ul className="space-y-2">
                {individual.names.map((name, index) => (
                  <li key={name.id ?? index} className="text-gray-700">
                    {`${name.prefix || ''} ${name.given_name || ''} ${name.family_name || ''} ${name.suffix || ''}`.trim() || '—'}
                    {name.name_type && (
                      <span className="text-gray-500 text-sm ml-2">({name.name_type})</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {/* Families */}
          <Card title="Families" {...cardDoubleClick('families')}>
            {relatedFamilies.length === 0 ? (
              <p className="text-gray-500 text-center py-4">No family connections</p>
            ) : (
              <ul className="space-y-3">
                {relatedFamilies.map((family) => {
                  const isChild = family.children.some((c) => c.child_id === Number(id));
                  const member = family.members.find((m) => m.individual_id === Number(id));
                  const role = isChild ? 'Child' : member?.role || 'Member';
                  return (
                    <li key={family.id}>
                      <Link
                        to={`/families/${family.id}`}
                        className="flex items-center gap-3 p-2 -mx-2 rounded-lg hover:bg-gray-50 transition-colors"
                      >
                        <div className="w-8 h-8 bg-rose-100 rounded-lg flex items-center justify-center">
                          <Heart className="w-4 h-4 text-rose-600" />
                        </div>
                        <div>
                          <p className="font-medium text-gray-900">{family.gedcom_id}</p>
                          <p className="text-sm text-gray-500">{role}</p>
                        </div>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </Card>

          {/* Media */}
          <Card title="Media" {...cardDoubleClick('photos')}>
            {hiddenMediaCount > 0 && (
              <p className="text-xs text-gray-400 mb-2">
                {hiddenMediaCount} sensitive item{hiddenMediaCount === 1 ? '' : 's'} hidden — use "Show sensitive" to reveal.
              </p>
            )}
            {sortedAllMedia.length === 0 ? (
              <div className="text-center py-4">
                <Image className="w-12 h-12 mx-auto text-gray-300 mb-2" />
                <p className="text-gray-500 text-sm">No media yet</p>
              </div>
            ) : (
              <>
                {photoMedia.length > 0 && (
                  <div className="grid grid-cols-2 gap-2">
                    {photoMedia.map((item) => (
                      <div key={item.id} className="relative">
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
                        {item.created_by && (
                          <span className="absolute top-1 left-1 max-w-[calc(100%-0.5rem)] truncate bg-black/60 text-white text-[10px] px-1.5 py-0.5 rounded">
                            Added by {item.created_by_display_name || item.created_by}
                          </span>
                        )}
                        {item.is_default && (
                          <Star className="absolute top-1 right-1 w-4 h-4 text-amber-400 fill-amber-400" />
                        )}
                      </div>
                    ))}
                  </div>
                )}
                {(audioCount > 0 || videoCount > 0) && (
                  <div className="mt-2 space-y-0.5 text-xs text-gray-500">
                    {audioCount > 0 && (
                      <p className="flex items-center gap-1">
                        <Music className="w-3 h-3" />{audioCount} audio
                      </p>
                    )}
                    {videoCount > 0 && (
                      <p className="flex items-center gap-1">
                        <Film className="w-3 h-3" />{videoCount} video
                      </p>
                    )}
                  </div>
                )}
              </>
            )}
          </Card>
        </div>
      </div>

      {/* Photo upload dialog */}
      {!readOnly && showPhotoDialog && (
        <PhotoUploadDialog
          individualId={Number(id)}
          sourceMediaId={editingPhoto?.id}
          initialImageSrc={
            editingPhoto
              ? mediaApi.getFileUrl(editingPhoto.id, { v: photoCacheBust })
              : newPhotoSrc ?? undefined
          }
          initialAge={editingPhoto?.age_on_photo}
          initialIsDefault={editingPhoto?.is_default}
          requiresConsent={needsParentalConsent}
          consentExplanation={minorDataExplanation(childThreshold)}
          onParentalConsent={(granted) => setParentalConsentMutation.mutate(granted)}
          onUpload={handlePhotoUpload}
          onClose={() => {
            setShowPhotoDialog(false);
            setEditingPhoto(null);
            setNewPhotoSrc((prev) => {
              if (prev) URL.revokeObjectURL(prev);
              return null;
            });
          }}
        />
      )}

      {/* Event add/edit dialog */}
      {!readOnly && (
        <EventFormDialog
          open={eventDialogOpen}
          onClose={() => {
            setEventDialogOpen(false);
            setEventToEdit(null);
          }}
          individualId={id ? Number(id) : undefined}
          event={eventToEdit}
        />
      )}

      {/* Section modals (double-click on card) */}
      {!readOnly && individual && (
        <>
          <ModalBasicInfo
            open={sectionModal === 'basic'}
            onClose={() => setSectionModal(null)}
            individual={individual}
          />
          <ModalNames
            open={sectionModal === 'names'}
            onClose={() => setSectionModal(null)}
            individual={individual}
          />
          <ModalBirth
            open={sectionModal === 'birth'}
            onClose={() => setSectionModal(null)}
            individual={individual}
          />
          <ModalDeath
            open={sectionModal === 'death'}
            onClose={() => setSectionModal(null)}
            individual={individual}
          />
          <ModalNotes
            open={sectionModal === 'notes'}
            onClose={() => setSectionModal(null)}
            individual={individual}
          />
          <ModalEventsSection
            open={sectionModal === 'events'}
            onClose={() => setSectionModal(null)}
            events={events ?? []}
            onAddEvent={() => {
              setEventToEdit(null);
              setEventDialogOpen(true);
            }}
            onEditEvent={(ev) => {
              setEventToEdit(ev);
              setEventDialogOpen(true);
            }}
            onDeleteEvent={(ev) => deleteEventMutation.mutate(ev.id)}
          />
          <ModalPhotosSection
            open={sectionModal === 'photos'}
            onClose={() => setSectionModal(null)}
            media={sortedAllMedia}
            photoCacheBust={photoCacheBust}
            onAddPhoto={handleStartAddPhoto}
            onAddAudio={handleStartAddAudio}
            onAddVideo={handleStartAddVideo}
            onEditPhoto={(item) => {
              setEditingPhoto(item);
              setNewPhotoSrc((prev) => {
                if (prev) URL.revokeObjectURL(prev);
                return null;
              });
              setSectionModal(null);
              setShowPhotoDialog(true);
            }}
            onSetDefault={(mediaId) => setDefaultMutation.mutate(mediaId)}
            onDelete={(mediaId) => deleteMediaMutation.mutate(mediaId)}
          />
          <ModalFamiliesSection
            open={sectionModal === 'families'}
            onClose={() => setSectionModal(null)}
            families={relatedFamilies.map((family) => {
              const isChild = family.children.some((c) => c.child_id === Number(id));
              const member = family.members.find((m) => m.individual_id === Number(id));
              return {
                id: family.id,
                gedcom_id: family.gedcom_id,
                role: isChild ? 'Child' : member?.role || 'Member',
              };
            })}
          />
        </>
      )}

      <input
        ref={addPhotoInputRef}
        type="file"
        accept=".jpg,.jpeg,.png,.webp,.heic,.heif"
        onChange={handleAddPhotoFileSelected}
        className="hidden"
      />
      <input
        ref={addAudioInputRef}
        type="file"
        accept="audio/*"
        onChange={handleMediaFileSelected('audio')}
        className="hidden"
      />
      <input
        ref={addVideoInputRef}
        type="file"
        accept="video/*"
        onChange={handleMediaFileSelected('video')}
        className="hidden"
      />
    </div>
  );
}


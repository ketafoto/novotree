import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { Plus, Search, Edit2, Trash2, Save, X, User, GitBranch, Users, AlertTriangle } from 'lucide-react';
import { individualsApi } from '../../api/individuals';
import { typesApi } from '../../api/types';
import { useAuth } from '../../contexts/AuthContext';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { Modal } from '../../components/common/Modal';
import { Input } from '../../components/common/Input';
import { Spinner } from '../../components/common/Spinner';
import toast from 'react-hot-toast';
import { apiErrorMessage } from '../../utils/apiError';
import type { Individual } from '../../types/models';
import { getLatestName, formatIndividualName } from '../../utils/nameUtils';

const RESET_CONFIRM_PHRASE = 'RESET';

export function IndividualsListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isOwner } = useAuth();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editData, setEditData] = useState<Partial<Individual>>({});
  const [resetModalOpen, setResetModalOpen] = useState(false);
  const [resetConfirmText, setResetConfirmText] = useState('');

  const { data: individuals, isLoading } = useQuery({
    queryKey: ['individuals'],
    queryFn: () => individualsApi.list(),
  });

  const { data: sexTypes } = useQuery({
    queryKey: ['types', 'sex'],
    queryFn: typesApi.getSexTypes,
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Individual> }) =>
      individualsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['individuals'] });
      setEditingId(null);
      toast.success('Individual updated');
    },
    onError: (err) => {
      toast.error(apiErrorMessage(err, 'Failed to update individual'));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: individualsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['individuals'] });
      toast.success('Individual deleted');
    },
    onError: (err) => {
      toast.error(apiErrorMessage(err, 'Failed to delete individual'));
    },
  });

  const deleteSelectedMutation = useMutation({
    mutationFn: async (ids: number[]) => {
      await Promise.all(ids.map((id) => individualsApi.delete(id)));
      return ids.length;
    },
    onSuccess: (count) => {
      queryClient.invalidateQueries({ queryKey: ['individuals'] });
      queryClient.invalidateQueries({ queryKey: ['families'] });
      setSelectedIds(new Set());
      toast.success(`Deleted ${count} individual${count === 1 ? '' : 's'}`);
    },
    onError: (err) => {
      toast.error(apiErrorMessage(err, 'Failed to delete selected individuals'));
    },
  });

  const deleteAllMutation = useMutation({
    mutationFn: individualsApi.deleteAll,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['individuals'] });
      queryClient.invalidateQueries({ queryKey: ['families'] });
      queryClient.invalidateQueries({ queryKey: ['events'] });
      queryClient.invalidateQueries({ queryKey: ['media'] });
      setSelectedIds(new Set());
      setResetModalOpen(false);
      setResetConfirmText('');
      const d = result.deleted;
      toast.success(
        `Tree reset: ${d.individuals} individuals, ${d.families} families, ${d.events} events, ${d.media} media removed`
      );
    },
    onError: (err) => {
      toast.error(apiErrorMessage(err, 'Failed to reset tree'));
    },
  });

  const filteredIndividuals = useMemo(() => {
    if (!individuals) return [];
    if (!searchQuery) return individuals;
    const query = searchQuery.toLowerCase();
    return individuals.filter((ind) => {
      const fullName = formatIndividualName(getLatestName(ind.names), '').toLowerCase();
      return (
        fullName.includes(query) ||
        ind.gedcom_id?.toLowerCase().includes(query) ||
        ind.birth_place?.toLowerCase().includes(query) ||
        ind.death_place?.toLowerCase().includes(query)
      );
    });
  }, [individuals, searchQuery]);

  const handleSelectAll = () => {
    if (selectedIds.size === filteredIndividuals.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredIndividuals.map((i) => i.id)));
    }
  };

  const handleSelect = (id: number) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const toDateInputValue = (v: string | undefined): string => {
    if (!v) return '';
    const s = String(v);
    if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 10);
    return s;
  };

  const handleEdit = (individual: Individual) => {
    setEditData({
      sex_code: individual.sex_code ?? '',
      birth_date: toDateInputValue(individual.birth_date),
      birth_date_approx: individual.birth_date_approx ?? '',
      birth_place: individual.birth_place ?? '',
      death_date: toDateInputValue(individual.death_date),
      death_date_approx: individual.death_date_approx ?? '',
      death_place: individual.death_place ?? '',
    });
    setEditingId(individual.id);
  };

  const handleSave = () => {
    if (!editingId) return;
    const payload: Partial<Individual> = {
      ...editData,
      birth_date: editData.birth_date || undefined,
      death_date: editData.death_date || undefined,
    };
    updateMutation.mutate({ id: editingId, data: payload });
  };

  const handleCancel = () => {
    setEditingId(null);
    setEditData({});
  };

  const handleCreateFamily = () => {
    navigate(`/families/new?members=${Array.from(selectedIds).join(',')}`);
  };

  const handleDeleteSelected = () => {
    const count = selectedIds.size;
    if (count === 0) return;
    if (window.confirm(`Delete ${count} selected individual${count === 1 ? '' : 's'}? Related family memberships, events, and media will also be removed.`)) {
      deleteSelectedMutation.mutate(Array.from(selectedIds));
    }
  };

  const resetConfirmed = resetConfirmText.trim() === RESET_CONFIRM_PHRASE;
  const totalIndividuals = individuals?.length || 0;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Individuals</h1>
          <p className="text-gray-600 mt-1">
            {individuals?.length || 0} individuals in your database
          </p>
        </div>
        <Link to="/individuals/new">
          <Button>
            <Plus className="w-4 h-4 mr-2" />
            Add Individual
          </Button>
        </Link>
      </div>

      {/* Toolbar */}
      <Card>
        <div className="space-y-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search by name, GEDCOM ID, or place..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            />
          </div>
          <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-gray-100">
            <span className="text-sm text-gray-600">
              {selectedIds.size > 0
                ? `${selectedIds.size} selected`
                : 'Select individuals to enable bulk actions'}
            </span>
            <div className="flex-1" />
            <Button
              variant={selectedIds.size === 0 ? 'secondary' : 'primary'}
              onClick={handleCreateFamily}
              disabled={selectedIds.size === 0}
              title={selectedIds.size === 0 ? 'Select individuals first' : 'Create a family from the selected individuals'}
            >
              <Users className="w-4 h-4 mr-2" />
              Create Family
            </Button>
            <Button
              variant={selectedIds.size === 0 ? 'secondary' : 'danger'}
              onClick={handleDeleteSelected}
              disabled={selectedIds.size === 0 || deleteSelectedMutation.isPending}
              isLoading={deleteSelectedMutation.isPending}
              title={selectedIds.size === 0 ? 'Select individuals first' : 'Delete selected individuals'}
            >
              <Trash2 className="w-4 h-4 mr-2" />
              Delete Selected
            </Button>
            {isOwner && (
              <Button
                variant="secondary"
                onClick={() => setResetModalOpen(true)}
                disabled={totalIndividuals === 0}
                className="text-red-600 border-red-300 hover:bg-red-50"
                title={totalIndividuals === 0 ? 'Tree is already empty' : 'Delete all individuals and related data'}
              >
                <AlertTriangle className="w-4 h-4 mr-2" />
                Delete All…
              </Button>
            )}
          </div>
        </div>
      </Card>

      {/* Table */}
      <Card>
        {filteredIndividuals.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <User className="w-16 h-16 mx-auto mb-4 text-gray-300" />
            {searchQuery ? (
              <>
                <p className="text-lg font-medium">No individuals found</p>
                <p className="text-sm">Try adjusting your search query</p>
              </>
            ) : (
              <>
                <p className="text-lg font-medium">No individuals yet</p>
                <p className="text-sm mb-4">Start building your family tree</p>
                <Link to="/individuals/new">
                  <Button>
                    <Plus className="w-4 h-4 mr-2" />
                    Add First Individual
                  </Button>
                </Link>
              </>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50">
                  <th className="py-3 px-2 text-left">
                    <input
                      type="checkbox"
                      checked={selectedIds.size === filteredIndividuals.length && filteredIndividuals.length > 0}
                      onChange={handleSelectAll}
                      className="rounded border-gray-300 text-emerald-600 focus:ring-emerald-500"
                    />
                  </th>
                  <th className="py-3 px-2 text-left font-semibold text-gray-600">ID</th>
                  <th className="py-3 px-2 text-left font-semibold text-gray-600">Given Name</th>
                  <th className="py-3 px-2 text-left font-semibold text-gray-600">Family Name</th>
                  <th className="py-3 px-2 text-left font-semibold text-gray-600">Sex</th>
                  <th className="py-3 px-2 text-left font-semibold text-gray-600">Birth Date</th>
                  <th className="py-3 px-2 text-left font-semibold text-gray-600">Birth Place</th>
                  <th className="py-3 px-2 text-left font-semibold text-gray-600">Death Date</th>
                  <th className="py-3 px-2 text-left font-semibold text-gray-600">Death Place</th>
                  <th className="py-3 px-2 text-left font-semibold text-gray-600">Added by</th>
                  <th className="py-3 px-2 text-right font-semibold text-gray-600">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredIndividuals.map((individual) => {
                  const isEditing = editingId === individual.id;
                  const name = getLatestName(individual.names);
                  const displayName = formatIndividualName(name);

                  return (
                    <tr
                      key={individual.id}
                      className={`hover:bg-gray-50 ${isEditing ? 'bg-emerald-50' : ''}`}
                      onDoubleClick={() => !isEditing && navigate(`/individuals/${individual.id}`)}
                      title={isEditing ? undefined : 'Double-click to open detail & edit'}
                    >
                      <td className="py-2 px-2">
                        <input
                          type="checkbox"
                          checked={selectedIds.has(individual.id)}
                          onChange={() => handleSelect(individual.id)}
                          className="rounded border-gray-300 text-emerald-600 focus:ring-emerald-500"
                        />
                      </td>
                      <td className="py-2 px-2 text-gray-500 font-mono text-xs">
                        {individual.gedcom_id}
                      </td>
                      <td className="py-2 px-2">{name?.given_name || '-'}</td>
                      <td className="py-2 px-2">{name?.family_name || '-'}</td>
                      <td className="py-2 px-2">
                        {isEditing ? (
                          <select
                            value={editData.sex_code ?? ''}
                            onChange={(e) =>
                              setEditData({ ...editData, sex_code: e.target.value })
                            }
                            className="w-full px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500"
                          >
                            <option value="">-</option>
                            <option value="M">M</option>
                            <option value="F">F</option>
                            {sexTypes?.filter((t) => t.code !== 'M' && t.code !== 'F').map((t) => (
                              <option key={t.code} value={t.code}>
                                {t.code}
                              </option>
                            ))}
                          </select>
                        ) : (
                          individual.sex_code || '-'
                        )}
                      </td>
                      <td className="py-2 px-2">
                        {isEditing ? (
                          <input
                            type="date"
                            value={editData.birth_date || ''}
                            onChange={(e) =>
                              setEditData({ ...editData, birth_date: e.target.value })
                            }
                            className="w-full px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500"
                          />
                        ) : (
                          individual.birth_date || individual.birth_date_approx || '-'
                        )}
                      </td>
                      <td className="py-2 px-2">
                        {isEditing ? (
                          <input
                            type="text"
                            value={editData.birth_place || ''}
                            onChange={(e) =>
                              setEditData({ ...editData, birth_place: e.target.value })
                            }
                            className="w-full px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500"
                          />
                        ) : (
                          individual.birth_place || '-'
                        )}
                      </td>
                      <td className="py-2 px-2">
                        {isEditing ? (
                          <input
                            type="date"
                            value={editData.death_date || ''}
                            onChange={(e) =>
                              setEditData({ ...editData, death_date: e.target.value })
                            }
                            className="w-full px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500"
                          />
                        ) : (
                          individual.death_date || individual.death_date_approx || '-'
                        )}
                      </td>
                      <td className="py-2 px-2">
                        {isEditing ? (
                          <input
                            type="text"
                            value={editData.death_place || ''}
                            onChange={(e) =>
                              setEditData({ ...editData, death_place: e.target.value })
                            }
                            className="w-full px-2 py-1 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500"
                          />
                        ) : (
                          individual.death_place || '-'
                        )}
                      </td>
                      <td className="py-2 px-2 text-xs text-gray-400">
                        {individual.created_by_display_name || individual.created_by || '—'}
                      </td>
                      <td className="py-2 px-2 text-right">
                        {isEditing ? (
                          <div className="flex items-center justify-end gap-1">
                            <button
                              onClick={handleSave}
                              className="p-1.5 text-emerald-600 hover:bg-emerald-100 rounded transition-colors"
                            >
                              <Save className="w-4 h-4" />
                            </button>
                            <button
                              onClick={handleCancel}
                              className="p-1.5 text-gray-400 hover:bg-gray-100 rounded transition-colors"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center justify-end gap-1">
                            <button
                              onClick={() => navigate(`/individuals/${individual.id}/tree`)}
                              className="p-1.5 text-gray-400 hover:text-amber-600 hover:bg-amber-50 rounded transition-colors"
                              title="View Family Tree"
                            >
                              <GitBranch className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleEdit(individual)}
                              className="p-1.5 text-gray-400 hover:text-emerald-600 hover:bg-emerald-50 rounded transition-colors"
                              title="Click for quick edit"
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => {
                                if (window.confirm(`Are you sure you want to delete "${displayName}"?`)) {
                                  deleteMutation.mutate(individual.id);
                                }
                              }}
                              className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <p className="text-sm text-gray-500">
        Showing {filteredIndividuals.length} of {individuals?.length || 0} individuals
      </p>

      <Modal
        open={resetModalOpen}
        onClose={() => {
          if (deleteAllMutation.isPending) return;
          setResetModalOpen(false);
          setResetConfirmText('');
        }}
        title="Delete all individuals and reset tree"
      >
        <div className="space-y-4">
          <div className="flex gap-3 p-4 bg-red-50 border border-red-200 rounded-lg">
            <AlertTriangle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
            <div className="text-sm text-red-800">
              <p className="font-semibold mb-1">This action cannot be undone.</p>
              <p>
                All <strong>{totalIndividuals}</strong> individuals in your tree will be permanently
                deleted, along with all related families, events, and media files. Helper and lookup
                tables (e.g. event types, name types) will be preserved.
              </p>
            </div>
          </div>

          <div>
            <Input
              label={`Type ${RESET_CONFIRM_PHRASE} to confirm`}
              value={resetConfirmText}
              onChange={(e) => setResetConfirmText(e.target.value)}
              placeholder={RESET_CONFIRM_PHRASE}
              autoFocus
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="secondary"
              onClick={() => {
                setResetModalOpen(false);
                setResetConfirmText('');
              }}
              disabled={deleteAllMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={() => deleteAllMutation.mutate()}
              disabled={!resetConfirmed || deleteAllMutation.isPending}
              isLoading={deleteAllMutation.isPending}
            >
              <Trash2 className="w-4 h-4 mr-2" />
              Permanently delete all data
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

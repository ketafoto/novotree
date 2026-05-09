import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { familiesApi } from '../../api/families';
import { typesApi } from '../../api/types';
import { Button } from '../common/Button';
import { Modal } from '../common/Modal';
import toast from 'react-hot-toast';
import { apiErrorMessage } from '../../utils/apiError';
import { FamilyTypeInfoButton } from './familyTypeInfo';
import type { Family } from '../../types/models';

interface ModalFamilyTypeProps {
  open: boolean;
  onClose: () => void;
  family: Family;
  onSaved?: () => void;
}

type FormData = { family_type?: string };

export function ModalFamilyType({ open, onClose, family, onSaved }: ModalFamilyTypeProps) {
  const queryClient = useQueryClient();
  const { data: familyTypes } = useQuery({
    queryKey: ['types', 'family-types'],
    queryFn: typesApi.getFamilyTypes,
  });
  const { register, handleSubmit, reset, formState: { isSubmitting } } = useForm<FormData>({
    defaultValues: { family_type: '' },
  });

  useEffect(() => {
    if (open && family) {
      reset({ family_type: family.family_type || '' });
    }
  }, [open, family, reset]);

  const updateMutation = useMutation({
    mutationFn: (data: FormData) =>
      familiesApi.update(family.id, { family_type: data.family_type?.trim() || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['families'] });
      toast.success('Family type updated');
      onClose();
      onSaved?.();
    },
    onError: (err) => toast.error(apiErrorMessage(err, 'Failed to update')),
  });

  // Preserve any pre-existing custom value (e.g. set via GEDCOM import) so the
  // dropdown doesn't silently lose it when the user opens the modal.
  const currentValue = family.family_type || '';
  const knownCodes = new Set((familyTypes || []).map((t) => t.code));
  const showLegacyOption = currentValue && !knownCodes.has(currentValue);

  return (
    <Modal open={open} onClose={onClose} title="Family Type">
      <form onSubmit={handleSubmit((data) => updateMutation.mutate(data))} className="space-y-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <label htmlFor="family_type" className="block text-sm font-medium text-gray-700">
              Family Type
            </label>
            <FamilyTypeInfoButton />
          </div>
          <select
            id="family_type"
            {...register('family_type')}
            className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
          >
            {showLegacyOption && (
              <option value={currentValue}>{currentValue} (custom)</option>
            )}
            {familyTypes?.map((opt) => (
              <option key={opt.code} value={opt.code}>
                {opt.description}
              </option>
            ))}
          </select>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" isLoading={isSubmitting}>Save</Button>
        </div>
      </form>
    </Modal>
  );
}

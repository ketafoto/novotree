import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { individualsApi } from '../../api/individuals';
import { Button } from '../common/Button';
import { Modal } from '../common/Modal';
import { TranslateButton } from '../common/TranslateButton';
import { SensitiveCheckbox } from '../common/SensitiveCheckbox';
import toast from 'react-hot-toast';
import { apiErrorMessage } from '../../utils/apiError';
import type { Individual } from '../../types/models';

interface ModalNotesProps {
  open: boolean;
  onClose: () => void;
  individual: Individual;
  onSaved?: () => void;
}

type FormData = { notes?: string; notes_sensitive?: boolean };

export function ModalNotes({ open, onClose, individual, onSaved }: ModalNotesProps) {
  const queryClient = useQueryClient();
  const { register, handleSubmit, reset, watch, setValue, getValues, formState: { isSubmitting } } = useForm<FormData>({
    defaultValues: { notes: '', notes_sensitive: false },
  });

  useEffect(() => {
    if (open && individual) {
      reset({ notes: individual.notes || '', notes_sensitive: !!individual.notes_sensitive });
    }
  }, [open, individual, reset]);

  const updateMutation = useMutation({
    mutationFn: (data: FormData) =>
      individualsApi.update(individual.id, {
        notes: data.notes?.trim() || undefined,
        notes_sensitive: !!data.notes_sensitive,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['individuals'] });
      // notes_sensitive feeds the tree payload's per-node flag — refetch the tree too.
      queryClient.invalidateQueries({ queryKey: ['tree'] });
      toast.success('Notes updated');
      onClose();
      onSaved?.();
    },
    onError: (err) => toast.error(apiErrorMessage(err, 'Failed to update')),
  });

  return (
    <Modal open={open} onClose={onClose} title="Notes">
      <form onSubmit={handleSubmit((data) => updateMutation.mutate(data))} className="space-y-4">
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <label className="block text-sm font-medium text-gray-700">Notes</label>
            <TranslateButton getText={() => getValues('notes')} />
          </div>
          <textarea
            {...register('notes')}
            rows={6}
            className="block w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
            placeholder="Additional notes..."
          />
        </div>
        <SensitiveCheckbox
          checked={!!watch('notes_sensitive')}
          onChange={(c) => setValue('notes_sensitive', c)}
          label="Mark these notes sensitive"
        />
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" isLoading={isSubmitting}>Save</Button>
        </div>
      </form>
    </Modal>
  );
}

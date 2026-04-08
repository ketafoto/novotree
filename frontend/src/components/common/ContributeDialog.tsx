import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { X, Send, CheckCircle } from 'lucide-react';
import { useState } from 'react';
import { usersApi } from '../../api/auth';
import { Input } from './Input';
import { Button } from './Button';
import toast from 'react-hot-toast';

const schema = z.object({
  display_name: z.string().min(1, 'Name is required'),
  email: z.string().email('Invalid email').optional().or(z.literal('')),
  message: z.string().max(500, 'Message too long').optional(),
});

type FormData = z.infer<typeof schema>;

interface ContributeDialogProps {
  ownerOwnerId: string;
  onClose: () => void;
}

export function ContributeDialog({ ownerOwnerId, onClose }: ContributeDialogProps) {
  const [submitted, setSubmitted] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    try {
      await usersApi.submitContributeRequest({
        owner_id: ownerOwnerId,
        display_name: data.display_name,
        email: data.email || undefined,
        message: data.message || undefined,
      });
      setSubmitted(true);
    } catch {
      toast.error('Failed to send request — please try again');
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 z-40"
        onClick={onClose}
        aria-hidden
      />

      {/* Dialog */}
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="contribute-dialog-title"
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
      >
        <div className="bg-white rounded-xl shadow-xl w-full max-w-sm">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
            <h2 id="contribute-dialog-title" className="text-base font-semibold text-gray-900">
              Request contributor access
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 p-1 rounded"
              aria-label="Close"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body */}
          <div className="px-6 py-5">
            {submitted ? (
              <div className="text-center py-4">
                <CheckCircle className="w-12 h-12 text-emerald-500 mx-auto mb-3" />
                <p className="font-medium text-gray-900">Request sent!</p>
                <p className="text-sm text-gray-500 mt-1">
                  The tree owner will review your request and reach out if approved.
                </p>
                <Button className="mt-5 w-full" variant="secondary" onClick={onClose}>
                  Close
                </Button>
              </div>
            ) : (
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                <p className="text-sm text-gray-600">
                  Send a request to become a contributor to this family tree.
                </p>

                <Input
                  label="Your name"
                  autoFocus
                  {...register('display_name')}
                  error={errors.display_name?.message}
                />

                <Input
                  label="Email (optional)"
                  type="email"
                  autoComplete="email"
                  {...register('email')}
                  error={errors.email?.message}
                  helperText="So the owner can contact you"
                />

                <div className="space-y-1">
                  <label className="block text-sm font-medium text-gray-700">
                    Message (optional)
                  </label>
                  <textarea
                    rows={3}
                    {...register('message')}
                    placeholder="Why would you like access?"
                    className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 resize-none"
                  />
                  {errors.message && (
                    <p className="text-sm text-red-600">{errors.message.message}</p>
                  )}
                </div>

                <div className="flex gap-3 pt-1">
                  <Button
                    type="button"
                    variant="secondary"
                    className="flex-1"
                    onClick={onClose}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    className="flex-1"
                    isLoading={isSubmitting}
                  >
                    <Send className="w-4 h-4 mr-2" />
                    Send request
                  </Button>
                </div>
              </form>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

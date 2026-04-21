import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { X, Eye, EyeOff, TreeDeciduous, Mail } from 'lucide-react';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { authApi, usersApi } from '../../api/auth';
import { Input } from './Input';
import { Button } from './Button';
import { passwordSchema, PASSWORD_HINT } from '../../utils/passwordValidation';
import toast from 'react-hot-toast';

const schema = z
  .object({
    display_name: z.string().min(1, 'Name is required'),
    email: z.string().email('Invalid email'),
    password: passwordSchema,
    confirm_password: z.string().min(1, 'Please confirm your password'),
    message: z.string().max(500, 'Message too long').optional(),
  })
  .refine((d) => d.password === d.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });

type FormData = z.infer<typeof schema>;

interface ContributeDialogProps {
  ownerOwnerId: string;
  onClose: () => void;
}

export function ContributeDialog({ ownerOwnerId, onClose }: ContributeDialogProps) {
  const [submittedEmail, setSubmittedEmail] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [resending, setResending] = useState(false);

  const { data: ownerInfo } = useQuery({
    queryKey: ['owner-info', ownerOwnerId],
    queryFn: () => usersApi.getOwnerInfo(ownerOwnerId),
    enabled: !!ownerOwnerId,
  });

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema), mode: 'onChange' });

  const onSubmit = async (data: FormData) => {
    try {
      await authApi.contributorSignup({
        display_name: data.display_name,
        email: data.email,
        password: data.password,
        owner_id: ownerOwnerId,
        message: data.message || undefined,
      });
      setSubmittedEmail(data.email);
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? 'Signup failed — please try again';
      toast.error(msg);
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
        <div className="bg-white rounded-xl shadow-xl w-full max-w-sm max-h-[90vh] overflow-y-auto">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
            <div className="flex items-center gap-2">
              <TreeDeciduous className="w-5 h-5 text-emerald-600" />
              <h2 id="contribute-dialog-title" className="text-base font-semibold text-gray-900">
                Become a contributor
              </h2>
            </div>
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
            {submittedEmail ? (
              <div className="text-center py-4">
                <div className="inline-flex items-center justify-center w-14 h-14 bg-emerald-600 rounded-xl mb-4">
                  <Mail className="w-8 h-8 text-white" />
                </div>
                <h3 className="text-lg font-bold text-gray-900 mb-2">Check your email</h3>
                <p className="text-gray-600 mb-1 text-sm">We sent a verification link to</p>
                <p className="font-medium text-gray-900 mb-4 text-sm">{submittedEmail}</p>
                <p className="text-sm text-gray-500 mb-6">
                  After verifying your email, the tree owner will review and approve your request before you can log in.
                </p>
                <Button className="w-full mb-3" variant="secondary" onClick={onClose}>
                  Close
                </Button>
                <button
                  onClick={async () => {
                    setResending(true);
                    try {
                      await authApi.resendContributorVerification(submittedEmail);
                      toast.success('Verification email resent');
                    } catch {
                      toast.error('Failed to resend — please try again');
                    } finally {
                      setResending(false);
                    }
                  }}
                  disabled={resending}
                  className="text-sm text-emerald-600 hover:underline disabled:opacity-50"
                >
                  {resending ? 'Sending…' : "Didn't receive it? Resend email"}
                </button>
              </div>
            ) : (
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                <p className="text-sm text-gray-600">
                  Create a contributor account to add and edit data in this family tree.
                </p>

                {/* Read-only owner name */}
                <div className="space-y-1">
                  <label className="block text-sm font-medium text-gray-700">
                    Tree owner
                  </label>
                  <div className="px-3 py-2 border border-gray-200 rounded-lg bg-gray-50 text-sm text-gray-600 select-none">
                    {ownerInfo?.display_name ?? ownerOwnerId}
                  </div>
                </div>

                <Input
                  label="Your name"
                  autoFocus
                  autoComplete="name"
                  {...register('display_name')}
                  error={errors.display_name?.message}
                />

                <Input
                  label="Email"
                  type="email"
                  autoComplete="email"
                  required
                  {...register('email')}
                  error={errors.email?.message}
                  helperText="Used to log in and for notifications"
                />

                <div className="relative">
                  <Input
                    label="Password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    required
                    {...register('password')}
                    error={errors.password?.message}
                    helperText={PASSWORD_HINT}
                    suppressError
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-8 text-gray-400 hover:text-gray-600"
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>

                <div className="relative">
                  <Input
                    label="Confirm Password"
                    type={showConfirm ? 'text' : 'password'}
                    autoComplete="new-password"
                    required
                    {...register('confirm_password')}
                    error={errors.confirm_password?.message}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirm(!showConfirm)}
                    className="absolute right-3 top-8 text-gray-400 hover:text-gray-600"
                    tabIndex={-1}
                  >
                    {showConfirm ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>

                <div className="space-y-1">
                  <label className="block text-sm font-medium text-gray-700">
                    Message to owner <span className="font-normal text-gray-400">(optional)</span>
                  </label>
                  <textarea
                    rows={2}
                    {...register('message')}
                    placeholder="Why would you like to contribute?"
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
                    Request access
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

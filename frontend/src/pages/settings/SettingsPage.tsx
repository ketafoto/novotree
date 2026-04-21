import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff, Key, User } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { authApi } from '../../api/auth';
import { Button } from '../../components/common/Button';
import { Input } from '../../components/common/Input';
import { Card } from '../../components/common/Card';
import { passwordSchema, PASSWORD_HINT } from '../../utils/passwordValidation';
import toast from 'react-hot-toast';
import { apiErrorMessage } from '../../utils/apiError';

const profileSchema = z.object({
  display_name: z.string().min(1, 'Display name is required'),
});

const changePasswordSchema = z
  .object({
    currentPassword: z.string().min(1, 'Current password is required'),
    newPassword: passwordSchema,
    confirmPassword: z.string(),
  })
  .refine((data) => data.newPassword === data.confirmPassword, {
    message: "Passwords don't match",
    path: ['confirmPassword'],
  });

type ProfileFormData = z.infer<typeof profileSchema>;
type ChangePasswordFormData = z.infer<typeof changePasswordSchema>;

export function SettingsPage() {
  const { editor, refresh } = useAuth();
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const {
    register: registerProfile,
    handleSubmit: handleProfileSubmit,
    formState: { errors: profileErrors, isSubmitting: profileSubmitting },
  } = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: { display_name: editor?.display_name ?? '' },
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ChangePasswordFormData>({
    resolver: zodResolver(changePasswordSchema),
  });

  const onProfileSubmit = async (data: ProfileFormData) => {
    try {
      await authApi.updateProfile(data.display_name);
      await refresh();
      toast.success('Profile updated');
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Failed to update profile'));
    }
  };

  const onSubmit = async (data: ChangePasswordFormData) => {
    try {
      await authApi.changePassword({
        current_password: data.currentPassword,
        new_password: data.newPassword,
      });
      toast.success('Password changed successfully');
      reset();
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Failed to change password. Please check your current password.'));
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-600 mt-1">Manage your account settings</p>
      </div>

      {/* Profile */}
      <Card title="Profile">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center shrink-0">
            <User className="w-8 h-8 text-emerald-600" />
          </div>
          <div>
            <p className="text-lg font-semibold text-gray-900">
              {editor?.display_name || editor?.editor_id || 'Dev User'}
            </p>
            <p className="text-sm text-gray-500 capitalize">{editor?.role ?? 'owner'}</p>
            <p className="text-gray-600">{editor?.email || 'No email set'}</p>
            {editor?.created_at && (
              <p className="text-sm text-gray-400">
                Member since {new Date(editor.created_at).toLocaleDateString()}
              </p>
            )}
          </div>
        </div>
        <form onSubmit={handleProfileSubmit(onProfileSubmit)} className="space-y-4">
          <Input
            label="Display Name"
            {...registerProfile('display_name')}
            error={profileErrors.display_name?.message}
          />
          <Button type="submit" isLoading={profileSubmitting}>
            Save
          </Button>
        </form>
      </Card>

      {/* Change Password — not shown in dev mode (no real auth) */}
      <Card title="Security — Change Password">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="relative">
            <Input
              label="Current Password"
              type={showCurrentPassword ? 'text' : 'password'}
              {...register('currentPassword')}
              error={errors.currentPassword?.message}
            />
            <button
              type="button"
              onClick={() => setShowCurrentPassword(!showCurrentPassword)}
              className="absolute right-3 top-8 text-gray-400 hover:text-gray-600"
            >
              {showCurrentPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>

          <div className="relative">
            <Input
              label="New Password"
              type={showNewPassword ? 'text' : 'password'}
              {...register('newPassword')}
              error={errors.newPassword?.message}
              helperText={PASSWORD_HINT}
            />
            <button
              type="button"
              onClick={() => setShowNewPassword(!showNewPassword)}
              className="absolute right-3 top-8 text-gray-400 hover:text-gray-600"
            >
              {showNewPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>

          <div className="relative">
            <Input
              label="Confirm New Password"
              type={showConfirmPassword ? 'text' : 'password'}
              {...register('confirmPassword')}
              error={errors.confirmPassword?.message}
            />
            <button
              type="button"
              onClick={() => setShowConfirmPassword(!showConfirmPassword)}
              className="absolute right-3 top-8 text-gray-400 hover:text-gray-600"
            >
              {showConfirmPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>
          </div>

          <Button type="submit" isLoading={isSubmitting}>
            <Key className="w-4 h-4 mr-2" />
            Change Password
          </Button>
        </form>
      </Card>
    </div>
  );
}

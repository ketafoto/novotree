import { useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff, TreeDeciduous } from 'lucide-react';
import { authApi } from '../../api/auth';
import { useAuth } from '../../contexts/AuthContext';
import { Input } from '../../components/common/Input';
import { Button } from '../../components/common/Button';
import toast from 'react-hot-toast';

const schema = z
  .object({
    editor_id: z
      .string()
      .min(3, 'Username must be at least 3 characters')
      .max(32, 'Username must be 32 characters or fewer')
      .regex(/^[a-zA-Z0-9_-]+$/, 'Only letters, numbers, _ and - allowed'),
    display_name: z.string().min(1, 'Display name is required'),
    email: z.string().email('Invalid email').optional().or(z.literal('')),
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirm_password: z.string().min(1, 'Please confirm your password'),
  })
  .refine((d) => d.password === d.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });

type FormData = z.infer<typeof schema>;

export function SetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { refresh } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const token = searchParams.get('token') ?? '';

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  if (!token) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="w-full max-w-sm text-center">
          <p className="text-red-600 font-medium">Invalid or missing invitation link.</p>
          <Link to="/login" className="text-emerald-600 hover:underline text-sm mt-4 block">
            Go to login
          </Link>
        </div>
      </div>
    );
  }

  const onSubmit = async (data: FormData) => {
    try {
      await authApi.setPassword({
        token,
        editor_id: data.editor_id,
        display_name: data.display_name,
        email: data.email || undefined,
        password: data.password,
      });
      // Cookies are now set — pull fresh editor state
      await refresh();
      toast.success('Account created! Welcome.');
      navigate('/');
    } catch {
      toast.error('Failed to set password — link may have expired');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-emerald-600 rounded-xl mb-4">
            <TreeDeciduous className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Genealogy DB</h1>
          <p className="text-gray-500 mt-1 text-sm">Set up your contributor account</p>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <Input
              label="Display Name"
              autoComplete="name"
              autoFocus
              {...register('display_name')}
              error={errors.display_name?.message}
            />

            <Input
              label="Username"
              autoComplete="username"
              {...register('editor_id')}
              error={errors.editor_id?.message}
              helperText="Letters, numbers, _ and - only"
            />

            <Input
              label="Email (optional)"
              type="email"
              autoComplete="email"
              {...register('email')}
              error={errors.email?.message}
            />

            <div className="relative">
              <Input
                label="Password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                {...register('password')}
                error={errors.password?.message}
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

            <Button type="submit" className="w-full" isLoading={isSubmitting}>
              Activate account
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}

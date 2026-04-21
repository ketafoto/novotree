import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff, TreeDeciduous, Mail } from 'lucide-react';
import { authApi } from '../../api/auth';
import { Input } from '../../components/common/Input';
import { Button } from '../../components/common/Button';
import { passwordSchema, PASSWORD_HINT } from '../../utils/passwordValidation';
import { usePublicConfig } from '../../hooks/usePublicConfig';
import toast from 'react-hot-toast';

const signupSchema = z
  .object({
    display_name: z.string().optional(),
    email: z.string().email('Invalid email'),
    password: passwordSchema,
    confirm_password: z.string().min(1, 'Please confirm your password'),
  })
  .refine((d) => d.password === d.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });

type SignupData = z.infer<typeof signupSchema>;

export function OwnerSignupPage() {
  const [submittedEmail, setSubmittedEmail] = useState<string | null>(null);
  const [resending, setResending] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const { adminEmail, signupEnabled, loading: configLoading } = usePublicConfig();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<SignupData>({ resolver: zodResolver(signupSchema), mode: 'onChange' });

  const onSubmit = async (data: SignupData) => {
    try {
      await authApi.ownerSignup({
        display_name: data.display_name || undefined,
        email: data.email,
        password: data.password,
      });
      setSubmittedEmail(data.email);
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? 'Signup failed';
      toast.error(msg);
    }
  };

  const handleResend = async () => {
    if (!submittedEmail) return;
    setResending(true);
    try {
      await authApi.resendOwnerVerification(submittedEmail);
      toast.success('Verification email resent');
    } catch {
      toast.error('Failed to resend — please try again');
    } finally {
      setResending(false);
    }
  };

  if (submittedEmail) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="w-full max-w-sm text-center">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-emerald-600 rounded-xl mb-6">
            <Mail className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Check your email</h1>
          <p className="text-gray-600 mb-1">We sent a verification link to</p>
          <p className="font-medium text-gray-900 mb-4">{submittedEmail}</p>
          <p className="text-sm text-gray-500 mb-6">
            Click the link in the email to complete account creation.
            The link expires in 1 hour.
          </p>
          <Button variant="secondary" onClick={handleResend} isLoading={resending} className="w-full mb-4">
            Resend verification email
          </Button>
          {adminEmail && (
            <p className="text-xs text-gray-400 mt-2">
              Having trouble?{' '}
              <a href={`mailto:${adminEmail}`} className="text-emerald-600 hover:underline">
                Contact the administrator
              </a>
            </p>
          )}
          <p className="text-sm text-gray-400 mt-4">
            Already have an account?{' '}
            <Link to="/login" className="text-emerald-600 hover:underline">Sign in</Link>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-emerald-600 rounded-xl mb-4">
            <TreeDeciduous className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Genealogy DB</h1>
          <p className="text-gray-500 mt-1 text-sm">Create tree owner account</p>
        </div>

        {!configLoading && !signupEnabled ? (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center space-y-3">
            <p className="text-gray-700 font-medium">Account registration is currently unavailable.</p>
            {adminEmail ? (
              <p className="text-sm text-gray-500">
                Please{' '}
                <a href={`mailto:${adminEmail}`} className="text-emerald-600 hover:underline">
                  contact the administrator
                </a>{' '}
                to request an account.
              </p>
            ) : (
              <p className="text-sm text-gray-500">Please contact the site administrator.</p>
            )}
          </div>
        ) : (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <Input
              label="Display Name"
              autoComplete="name"
              autoFocus
              {...register('display_name')}
              error={errors.display_name?.message}
              helperText="Optional — your name as shown in the app"
            />

            <Input
              label="Email"
              type="email"
              autoComplete="email"
              required
              {...register('email')}
              error={errors.email?.message}
              helperText="Used to log in and for password reset"
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

            <Button type="submit" className="w-full" isLoading={isSubmitting}>
              Create account
            </Button>
          </form>
        </div>
        )}

        <p className="text-center text-sm text-gray-500 mt-6">
          Already have an account?{' '}
          <Link to="/login" className="text-emerald-600 hover:underline font-medium">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

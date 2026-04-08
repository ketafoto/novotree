import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff, TreeDeciduous } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { Input } from '../../components/common/Input';
import { Button } from '../../components/common/Button';
import toast from 'react-hot-toast';

const step1Schema = z.object({
  editor_id: z.string().min(1, 'Username is required'),
  password: z.string().min(1, 'Password is required'),
});
type Step1Data = z.infer<typeof step1Schema>;

export function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [showPassword, setShowPassword] = useState(false);

  // Step 2: multi-tree contributor selection
  const [step, setStep] = useState<1 | 2>(1);
  const [savedCreds, setSavedCreds] = useState<Step1Data | null>(null);
  const [availableTrees, setAvailableTrees] = useState<string[]>([]);

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Step1Data>({
    resolver: zodResolver(step1Schema),
  });

  const onStep1 = async (data: Step1Data) => {
    try {
      await login(data.editor_id, data.password);
      navigate('/');
    } catch (err: unknown) {
      // HTTP 300 → contributor with multiple trees
      const status = (err as { response?: { status?: number; data?: { detail?: { trees?: string[] } } } })
        ?.response?.status;
      const trees = (err as { response?: { data?: { detail?: { trees?: string[] } } } })
        ?.response?.data?.detail?.trees;

      if (status === 300 && Array.isArray(trees)) {
        setSavedCreds(data);
        setAvailableTrees(trees);
        setStep(2);
      } else {
        toast.error('Invalid username or password');
      }
    }
  };

  const onSelectTree = async (owner_id: string) => {
    if (!savedCreds) return;
    try {
      await login(savedCreds.editor_id, savedCreds.password, owner_id);
      navigate('/');
    } catch {
      toast.error('Login failed — please try again');
      setStep(1);
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
          <p className="text-gray-500 mt-1 text-sm">Sign in to your account</p>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
          {step === 1 ? (
            <form onSubmit={handleSubmit(onStep1)} className="space-y-4">
              <Input
                label="Username"
                autoComplete="username"
                autoFocus
                {...register('editor_id')}
                error={errors.editor_id?.message}
              />

              <div className="relative">
                <Input
                  label="Password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
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

              <Button type="submit" className="w-full" isLoading={isSubmitting}>
                Sign in
              </Button>
            </form>
          ) : (
            <div className="space-y-4">
              <div>
                <p className="text-sm font-medium text-gray-700 mb-1">Select a tree to open:</p>
                <p className="text-xs text-gray-500 mb-3">
                  You have access to multiple trees. Choose one to continue.
                </p>
              </div>
              <div className="space-y-2">
                {availableTrees.map((owner_id) => (
                  <button
                    key={owner_id}
                    onClick={() => void onSelectTree(owner_id)}
                    className="w-full text-left px-4 py-3 rounded-lg border border-gray-200 hover:border-emerald-500 hover:bg-emerald-50 transition-colors"
                  >
                    <span className="font-medium text-gray-800">{owner_id}</span>
                    <span className="text-xs text-gray-400 ml-2">tree</span>
                  </button>
                ))}
              </div>
              <button
                onClick={() => setStep(1)}
                className="text-xs text-gray-400 hover:text-gray-600 underline"
              >
                ← Back
              </button>
            </div>
          )}
        </div>

        <p className="text-center text-sm text-gray-500 mt-6">
          Owner?{' '}
          <Link to="/signup" className="text-emerald-600 hover:underline font-medium">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}

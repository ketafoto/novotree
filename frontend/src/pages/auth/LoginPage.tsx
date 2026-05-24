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
  editor_id: z.string().min(1, 'Email or username is required'),
  password: z.string().min(1, 'Password is required'),
});
type Step1Data = z.infer<typeof step1Schema>;

type TreeOption = { owner_id: string; display_name: string; role: string };

const ROLE_BADGE: Record<string, string> = {
  owner: 'bg-emerald-100 text-emerald-700',
  contributor: 'bg-blue-100 text-blue-700',
};

export function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [showPassword, setShowPassword] = useState(false);

  // Step 2: multi-tree selection
  const [step, setStep] = useState<1 | 2>(1);
  const [savedCreds, setSavedCreds] = useState<Step1Data | null>(null);
  const [availableTrees, setAvailableTrees] = useState<TreeOption[]>([]);

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Step1Data>({
    resolver: zodResolver(step1Schema),
  });

  const onStep1 = async (data: Step1Data) => {
    try {
      await login(data.editor_id, data.password);
      navigate('/');
    } catch (err: unknown) {
      // HTTP 300 → multiple trees available
      const status = (err as { response?: { status?: number } })?.response?.status;
      const trees = (err as { response?: { data?: { detail?: { trees?: TreeOption[] } } } })
        ?.response?.data?.detail?.trees;

      if (status === 300 && Array.isArray(trees)) {
        setSavedCreds(data);
        setAvailableTrees(trees);
        setStep(2);
      } else if (status === 403) {
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? '';
        if (detail.includes('suspended') || detail.includes('frozen')) {
          toast.error('Your access has been suspended — contact the tree owner');
        } else if (detail.includes('approval')) {
          toast.error('Your account is awaiting owner approval');
        } else {
          toast.error(detail || 'Access denied');
        }
      } else {
        toast.error('Invalid email or password');
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
    <div className="min-h-full bg-gray-50 flex items-center justify-center p-4">
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
                label="Email"
                type="email"
                autoComplete="email"
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
                {availableTrees.map((tree) => (
                  <button
                    key={tree.owner_id}
                    onClick={() => void onSelectTree(tree.owner_id)}
                    className="w-full text-left px-4 py-3 rounded-lg border border-gray-200 hover:border-emerald-500 hover:bg-emerald-50 transition-colors flex items-center justify-between"
                  >
                    <span className="font-medium text-gray-800">{tree.display_name}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ROLE_BADGE[tree.role] ?? 'bg-gray-100 text-gray-600'}`}>
                      {tree.role}
                    </span>
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
          Wanna build your own tree?{' '}
          <Link to="/owner-signup" className="text-emerald-600 hover:underline font-medium">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}

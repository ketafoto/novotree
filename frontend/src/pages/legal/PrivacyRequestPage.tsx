import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { TreeDeciduous, Info, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';

import { Button } from '../../components/common/Button';
import { Input } from '../../components/common/Input';
import { usePrivacyConfig } from '../../hooks/usePrivacyConfig';
import { privacyApi } from '../../api/privacy';
import type { PrivacyRequestType } from '../../api/privacy_requests';
import { useAuth } from '../../contexts/AuthContext';

// Three request kinds — radio options shown on the form (Tier 1 §2.7 of
// docs/legal/PRIVACY_DESIGN.md). User copy is plain language; the legal text
// (GDPR Art. 15-17) lives in the privacy policy, not here. The same labels
// are used in PRIVACY_ANALYSIS.md §9.8 — keep in sync if either side changes.
const REQUEST_TYPE_OPTIONS: ReadonlyArray<{
  value: PrivacyRequestType;
  label: string;
}> = [
  { value: 'removal', label: 'Remove my data from this family tree.' },
  { value: 'access', label: 'Send me a copy of the data this tree holds about me.' },
  { value: 'correction', label: 'Correct something this tree gets wrong about me.' },
];

// Field length bounds mirror backend/api/privacy_requests.py — keep in sync.
const schema = z.object({
  tree_owner_id: z.string().min(1, 'Required').max(64),
  individual_id: z.string().max(64).optional(),
  request_type: z.enum(['removal', 'access', 'correction'], {
    error: () => ({ message: 'Pick what you want the tree owner to do' }),
  }),
  requester_name: z.string().min(1, 'Required').max(200),
  requester_email: z.string().email('Enter a valid email').max(320),
  requester_phone: z.string().max(40).optional(),
  message: z.string().min(10, 'Please describe your request (10+ characters)').max(4000),
});
type FormData = z.infer<typeof schema>;

type PrefillSource = 'url' | 'share-token' | 'authenticated-self' | 'none';

interface OwnerContext {
  prefillValue: string;
  source: PrefillSource;
}

function resolveOwnerContext(
  viewerOwnerId: string | null,
  authenticatedOwnerId: string | null,
): OwnerContext {
  // Precedence:
  //  1. ?owner= in the URL — explicit, set by the global PrivacyLinks footer
  //     and by Tree page links once a share-token session knows the owner.
  //  2. share-token session in this tab.
  //  3. authenticated session — but the field is NOT prefilled with the
  //     signed-in user's own owner_id (filing a privacy request against
  //     yourself is the wrong affordance; the banner steers them to Settings
  //     instead).
  //  4. nothing — the field stays empty and the banner explains that an
  //     off-platform requester needs to type the username.
  const params = new URLSearchParams(window.location.search);
  const fromUrl = params.get('owner');
  if (fromUrl) return { prefillValue: fromUrl, source: 'url' };
  if (viewerOwnerId) return { prefillValue: viewerOwnerId, source: 'share-token' };
  if (authenticatedOwnerId) return { prefillValue: '', source: 'authenticated-self' };
  return { prefillValue: '', source: 'none' };
}

interface OwnerBannerProps {
  context: OwnerContext;
  authenticatedOwnerId: string | null;
}

function OwnerBanner({ context, authenticatedOwnerId }: OwnerBannerProps) {
  // The banner exists so a tester (or any visitor) can tell at a glance
  // whether the empty/filled "Tree owner" field reflects what the page
  // knows. Each branch says exactly which context the page is in.
  if (context.source === 'url' || context.source === 'share-token') {
    return (
      <div className="flex items-start gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
        <CheckCircle2 className="w-4 h-4 mt-0.5 flex-shrink-0 text-emerald-600" />
        <span>
          You arrived from <span className="font-mono font-semibold">{context.prefillValue}</span>'s
          tree. This request will be filed against that tree. If you meant a different one, edit
          the field below.
        </span>
      </div>
    );
  }
  if (context.source === 'authenticated-self') {
    return (
      <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
        <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0 text-amber-600" />
        <span>
          You are signed in as <span className="font-mono font-semibold">{authenticatedOwnerId}</span>.
          This form is for <em>other people</em> to ask the tree owner about their data —
          filing it against your own tree usually isn't what you want. To delete or change
          your own data, use{' '}
          <Link to="/settings" className="underline hover:text-amber-700">
            Settings
          </Link>{' '}
          instead. Otherwise, type the username of the tree the request concerns.
        </span>
      </div>
    );
  }
  return (
    <div className="flex items-start gap-2 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-900">
      <Info className="w-4 h-4 mt-0.5 flex-shrink-0 text-blue-600" />
      <span>
        We don't know which tree this request is about. If you were given a share link, the tree
        owner's username is the part after <span className="font-mono">?owner=</span> in the URL;
        otherwise ask the person who told you about the tree, or describe it in the message field.
      </span>
    </div>
  );
}

export function PrivacyRequestPage() {
  const { config, loading } = usePrivacyConfig();
  const { editor, viewerOwnerId } = useAuth();
  const [submitted, setSubmitted] = useState(false);

  const authenticatedOwnerId = editor?.owner_id ?? null;
  const ownerContext = resolveOwnerContext(viewerOwnerId, authenticatedOwnerId);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      tree_owner_id: ownerContext.prefillValue,
      // request_type intentionally has no default — the user must pick.
    },
  });

  const onSubmit = async (data: FormData) => {
    try {
      await privacyApi.submitPrivacyRequest({
        tree_owner_id: data.tree_owner_id,
        individual_id: data.individual_id || undefined,
        request_type: data.request_type,
        requester_name: data.requester_name,
        requester_email: data.requester_email,
        requester_phone: data.requester_phone || undefined,
        message: data.message,
      });
      setSubmitted(true);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 429) {
        toast.error('Too many submissions from your address. Please try again later.');
      } else {
        toast.error('Could not submit your request. Please try again or email us directly.');
      }
    }
  };

  const navigate = useNavigate();
  const slaDays = config?.privacy_request_sla_days ?? 30;
  const contact = config?.privacy_contact_email ?? '';
  const retentionMonths = config?.privacy_request_retention_months ?? 12;

  if (submitted) {
    return (
      <div className="flex-1 bg-gray-50 flex items-center justify-center p-4">
        <div className="max-w-xl w-full bg-white rounded-lg shadow p-8 space-y-4">
          <div className="flex items-center gap-3">
            <TreeDeciduous className="text-emerald-600" size={32} />
            <h1 className="text-2xl font-semibold">Request received</h1>
          </div>
          <p className="text-gray-700">
            We have recorded your request and forwarded it to the Tree Owner. If they
            do not respond within {slaDays} days, NovoTree will act on your behalf.
          </p>
          <p className="text-sm text-gray-500">
            We will store this request only as long as needed to act on it
            (max {retentionMonths} months).
          </p>
          {contact && (
            <p className="text-sm text-gray-500">
              Questions or follow-up: <a className="text-emerald-700 underline" href={`mailto:${contact}`}>{contact}</a>
            </p>
          )}
          <button
            onClick={() => navigate(-1)}
            className="text-sm text-emerald-700 underline hover:text-emerald-800"
          >
            ← Back
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 bg-gray-50 flex items-center justify-center p-4">
      <div className="max-w-xl w-full bg-white rounded-lg shadow p-8 space-y-6">
        <div className="flex items-center gap-3">
          <TreeDeciduous className="text-emerald-600 flex-shrink-0" size={32} />
          <div>
            <h1 className="text-2xl font-semibold leading-tight">Privacy request</h1>
            <p className="text-sm text-gray-600 mt-0.5">
              remove, access, or correct your data
            </p>
          </div>
        </div>

        <div className="text-gray-700 space-y-2 text-sm">
          <p>
            Use this form to ask the owner of this family tree to remove, send you a copy of,
            or correct information they hold about you. Pick one and describe your request
            below. We will email the owner; you should hear back within {slaDays} days.
          </p>
          <p className="text-gray-500">
            We may contact you to verify your identity before acting on this request.
          </p>
          <p className="text-gray-500">
            See our{' '}
            <Link to="/legal/privacy" className="text-emerald-700 underline hover:text-emerald-800">
              Privacy Policy
            </Link>{' '}
            for how we handle this request.
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <OwnerBanner context={ownerContext} authenticatedOwnerId={authenticatedOwnerId} />

          <fieldset className="space-y-2">
            <legend className="block text-sm font-medium text-gray-700">
              What would you like the tree owner to do?
              <span className="text-red-500 ml-1">*</span>
            </legend>
            <div className="space-y-2">
              {REQUEST_TYPE_OPTIONS.map((opt) => (
                <label key={opt.value} className="flex items-start gap-2 text-sm text-gray-700 cursor-pointer">
                  <input
                    type="radio"
                    value={opt.value}
                    className="mt-1"
                    {...register('request_type')}
                  />
                  <span>{opt.label}</span>
                </label>
              ))}
            </div>
            {errors.request_type?.message && (
              <p className="text-sm text-red-600">{errors.request_type.message}</p>
            )}
          </fieldset>

          <Input
            label="Tree owner (username) or tree URL"
            required
            placeholder="e.g. johndoe — visible in the tree's URL"
            error={errors.tree_owner_id?.message}
            {...register('tree_owner_id')}
          />

          <Input
            label="Your name as it appears on the tree"
            required
            error={errors.requester_name?.message}
            {...register('requester_name')}
          />

          <Input
            label="Your email"
            type="email"
            required
            helperText="So we can confirm receipt and ask follow-up questions."
            error={errors.requester_email?.message}
            {...register('requester_email')}
          />

          <Input
            label="Your phone (optional)"
            helperText="Helps confirm your identity if needed."
            error={errors.requester_phone?.message}
            {...register('requester_phone')}
          />

          <Input
            label="Individual ID (optional, if you know it)"
            helperText="Visible in the URL when viewing a person on the tree."
            error={errors.individual_id?.message}
            {...register('individual_id')}
          />

          <div className="space-y-1">
            <label htmlFor="message" className="block text-sm font-medium text-gray-700">
              Describe your request
              <span className="text-red-500 ml-1">*</span>
            </label>
            <textarea
              id="message"
              rows={6}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-emerald-500"
              {...register('message')}
            />
            {errors.message?.message && (
              <p className="text-sm text-red-600">{errors.message.message}</p>
            )}
          </div>

          <Button type="submit" isLoading={isSubmitting || loading} className="w-full">
            Submit request
          </Button>

          <p className="text-xs text-gray-500">
            We will store this request only as long as needed to act on it
            (max {retentionMonths} months).
          </p>
        </form>
      </div>
    </div>
  );
}

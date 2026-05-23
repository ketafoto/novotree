import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { TreeDeciduous } from 'lucide-react';
import toast from 'react-hot-toast';

import { Button } from '../../components/common/Button';
import { Input } from '../../components/common/Input';
import { usePrivacyConfig } from '../../hooks/usePrivacyConfig';
import { privacyApi } from '../../api/privacy';

// Field length bounds mirror backend/api/privacy.py — keep in sync.
const schema = z.object({
  tree_owner_id: z.string().min(1, 'Required').max(64),
  individual_id: z.string().max(64).optional(),
  requester_name: z.string().min(1, 'Required').max(200),
  requester_email: z.string().email('Enter a valid email').max(320),
  requester_phone: z.string().max(40).optional(),
  message: z.string().min(10, 'Please describe what should be removed (10+ characters)').max(4000),
});
type FormData = z.infer<typeof schema>;

function readPrefillOwnerId(): string {
  // Order of precedence: explicit ?owner= in the URL → resolved share-token
  // owner stored in sessionStorage by the share-link viewer flow → empty
  // (the form will require the user to type it).
  const params = new URLSearchParams(window.location.search);
  return params.get('owner') ?? sessionStorage.getItem('share_owner_id') ?? '';
}

export function TakedownPage() {
  const { config, loading } = usePrivacyConfig();
  const [submitted, setSubmitted] = useState(false);

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      tree_owner_id: readPrefillOwnerId(),
    },
  });

  const onSubmit = async (data: FormData) => {
    try {
      await privacyApi.submitTakedown({
        tree_owner_id: data.tree_owner_id,
        individual_id: data.individual_id || undefined,
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

  const slaDays = config?.takedown_sla_days ?? 30;
  const contact = config?.privacy_contact_email ?? '';
  const retentionMonths = config?.takedown_request_retention_months ?? 12;

  if (submitted) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="max-w-xl w-full bg-white rounded-lg shadow p-8 space-y-4">
          <div className="flex items-center gap-3">
            <TreeDeciduous className="text-emerald-600" size={32} />
            <h1 className="text-2xl font-semibold">Request received</h1>
          </div>
          <p className="text-gray-700">
            We have recorded your request and forwarded it to the Tree Owner. If they
            do not respond within {slaDays} days, NovoTree will hide the records on
            your behalf.
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
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="max-w-xl w-full bg-white rounded-lg shadow p-8 space-y-6">
        <div className="flex items-center gap-3">
          <TreeDeciduous className="text-emerald-600" size={32} />
          <h1 className="text-2xl font-semibold">Privacy — remove me from a tree</h1>
        </div>

        <div className="text-gray-700 space-y-2 text-sm">
          <p>
            If your information appears on NovoTree and you want it removed, fill in
            the form below. We will forward your request to the Tree Owner; if they
            do not respond within {slaDays} days, NovoTree will hide the records on
            your behalf.
          </p>
          <p className="text-gray-500">
            We may contact you to verify your identity before acting on this request.
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
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
              Describe what should be removed
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

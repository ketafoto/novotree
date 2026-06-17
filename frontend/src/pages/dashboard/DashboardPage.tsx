import { shareUrl } from '../../utils/shareUrl';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { User, Heart, Calendar, Image, ArrowRight, Plus, Share2, Copy, Trash2, Users, Shield, AlertTriangle, Check } from 'lucide-react';
import { individualsApi } from '../../api/individuals';
import { familiesApi } from '../../api/families';
import { eventsApi } from '../../api/events';
import { mediaApi } from '../../api/media';
import { usersApi } from '../../api/auth';
import { privacyRequestsApi } from '../../api/privacy_requests';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Spinner } from '../../components/common/Spinner';
import { ShareSensitiveBadge } from '../../components/common/ShareSensitiveBadge';
import { formatIndividualName, getLatestName } from '../../utils/nameUtils';
import { useAuth } from '../../contexts/AuthContext';
import { isLocalApp } from '../../config/appMode';
import toast from 'react-hot-toast';
import { apiErrorMessage } from '../../utils/apiError';

interface StatCardProps {
  title: string;
  value: number;
  icon: React.ReactNode;
  linkTo: string;
  color: string;
}

function StatCard({ title, value, icon, linkTo, color }: StatCardProps) {
  return (
    <Link to={linkTo}>
      <div className="bg-white rounded-lg border border-gray-200 p-6 hover:shadow-md transition-shadow">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-600">{title}</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">{value}</p>
          </div>
          <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${color}`}>
            {icon}
          </div>
        </div>
      </div>
    </Link>
  );
}

function ShareLinksWidget() {
  const qc = useQueryClient();
  const { data: tokens = [], isLoading } = useQuery({
    queryKey: ['share-tokens'],
    queryFn: usersApi.listShareTokens,
  });

  const activeTokens = tokens.filter(t => t.is_active);

  // Creating share links lives on the User Manager page (/users), where the
  // Owner can set a label and the expose-sensitive flag. This widget is a
  // read-only summary with copy/revoke; it deliberately does not create links
  // (a label-less one-click create was confusing — see commit history).

  const copy = (token: string) => {
    const url = shareUrl(token);
    navigator.clipboard.writeText(url).then(() => toast.success('Link copied!'));
  };

  const revoke = async (id: number) => {
    try {
      await usersApi.revokeShareToken(id);
      qc.invalidateQueries({ queryKey: ['share-tokens'] });
    } catch (err) {
      toast.error(apiErrorMessage(err, 'Failed to revoke'));
    }
  };

  return (
    <Card
      title="Share Links"
      actions={
        <Link to="/users">
          <Button variant="ghost" size="sm">
            Manage
            <ArrowRight className="w-4 h-4 ml-1" />
          </Button>
        </Link>
      }
    >
      {isLoading ? (
        <div className="py-4 flex justify-center"><Spinner /></div>
      ) : activeTokens.length === 0 ? (
        <div className="text-center py-4">
          <Share2 className="w-8 h-8 mx-auto mb-2 text-gray-300" />
          <p className="text-sm text-gray-500 mb-3">No share links yet.</p>
          <Link to="/users">
            <Button size="sm" variant="secondary">
              <Plus className="w-3.5 h-3.5 mr-1" />
              Create a link
            </Button>
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {activeTokens.map(t => (
            <div key={t.id} className="flex items-center gap-3 py-2">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-700 truncate">{t.label || 'Unnamed link'}</p>
                <p className="text-xs text-gray-400 font-mono truncate">
                  {shareUrl(t.token)}
                </p>
                {t.created_at && (
                  <p className="text-xs text-gray-400" title="Your confirmation that you had the right to share this tree was recorded when the link was created.">
                    <Check className="inline w-3 h-3 text-emerald-500 mr-0.5" aria-hidden /> Acknowledged on {new Date(t.created_at).toLocaleDateString()}
                  </p>
                )}
                <div className="mt-1">
                  <ShareSensitiveBadge exposeSensitive={t.expose_sensitive} />
                </div>
              </div>
              <button onClick={() => copy(t.token)} className="p-1.5 hover:bg-gray-100 rounded" title="Copy link">
                <Copy className="w-4 h-4 text-gray-500" />
              </button>
              <button onClick={() => revoke(t.id)} className="p-1.5 hover:bg-red-50 rounded" title="Revoke">
                <Trash2 className="w-4 h-4 text-red-400" />
              </button>
            </div>
          ))}
          <Link to="/users" className="text-xs text-blue-600 hover:underline">
            + New link
          </Link>
        </div>
      )}
    </Card>
  );
}

/**
 * Always-visible summary of the Owner's privacy-requests queue.
 *
 * Renders even at zero so the Owner remembers the feature exists (per
 * docs/legal/PRIVACY_DESIGN.md §2.2 + §2.7). Severity is conditional:
 *   - any escalated row → red (SLA missed, immediate attention)
 *   - else any open row → amber (within SLA, action needed)
 *   - empty            → neutral grey
 *
 * Shares the query key `['privacy-requests', false]` with PrivacyRequestsPage
 * so navigating between dashboard and queue is a cache hit, no extra fetch.
 */
function PrivacyRequestsSummaryCard() {
  const { data, isLoading } = useQuery({
    queryKey: ['privacy-requests', false],
    queryFn: () => privacyRequestsApi.list(false),
  });

  const rows = data ?? [];
  const escalatedCount = rows.filter((r) => r.status === 'escalated').length;
  const openCount = rows.filter((r) => r.status === 'open').length;
  const total = openCount + escalatedCount;

  const severity = escalatedCount > 0 ? 'red' : openCount > 0 ? 'amber' : 'neutral';
  const tone = {
    red: { border: 'border-red-300', iconBg: 'bg-red-100', iconFg: 'text-red-600' },
    amber: { border: 'border-amber-300', iconBg: 'bg-amber-100', iconFg: 'text-amber-600' },
    neutral: { border: 'border-gray-200', iconBg: 'bg-gray-100', iconFg: 'text-gray-500' },
  }[severity];

  return (
    <Link to="/legal/privacy-requests" className="block">
      <div className={`bg-white rounded-lg border ${tone.border} p-6 hover:shadow-md transition-shadow`}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-600 flex items-center gap-2">
              Privacy requests
              {escalatedCount > 0 && (
                <AlertTriangle className="w-4 h-4 text-red-600" aria-label="SLA exceeded" />
              )}
            </p>
            <p className="text-3xl font-bold text-gray-900 mt-1">
              {isLoading ? '—' : total}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              {isLoading
                ? 'Loading…'
                : total === 0
                ? 'No requests awaiting action'
                : escalatedCount > 0
                ? `${escalatedCount} escalated, ${openCount} open`
                : `${openCount} open, within SLA`}
            </p>
          </div>
          <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${tone.iconBg}`}>
            <Shield className={`w-6 h-6 ${tone.iconFg}`} />
          </div>
        </div>
      </div>
    </Link>
  );
}

export function DashboardPage() {
  const { isOwner } = useAuth();
  const { data: individuals, isLoading: loadingIndividuals } = useQuery({
    queryKey: ['individuals'],
    queryFn: () => individualsApi.list(),
  });

  const { data: families, isLoading: loadingFamilies } = useQuery({
    queryKey: ['families'],
    queryFn: () => familiesApi.list(),
  });

  const { data: events, isLoading: loadingEvents } = useQuery({
    queryKey: ['events'],
    queryFn: () => eventsApi.list(),
  });

  const { data: media, isLoading: loadingMedia } = useQuery({
    queryKey: ['media'],
    queryFn: () => mediaApi.list(),
  });

  const isLoading = loadingIndividuals || loadingFamilies || loadingEvents || loadingMedia;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Spinner size="lg" />
      </div>
    );
  }

  const stats = {
    individuals: individuals?.length || 0,
    families: families?.length || 0,
    events: events?.length || 0,
    media: media?.length || 0,
  };

  // Get recent individuals (last 5)
  const recentIndividuals = (individuals || []).slice(0, 5);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600 mt-1">Overview of your genealogy database</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Individuals"
          value={stats.individuals}
          icon={<User className="w-6 h-6 text-white" />}
          linkTo="/individuals"
          color="bg-emerald-600"
        />
        <StatCard
          title="Families"
          value={stats.families}
          icon={<Heart className="w-6 h-6 text-white" />}
          linkTo="/families"
          color="bg-rose-500"
        />
        <StatCard
          title="Events"
          value={stats.events}
          icon={<Calendar className="w-6 h-6 text-white" />}
          linkTo="/individuals"
          color="bg-blue-500"
        />
        <StatCard
          title="Media"
          value={stats.media}
          icon={<Image className="w-6 h-6 text-white" />}
          linkTo="/individuals"
          color="bg-amber-500"
        />
      </div>

      {/* Privacy-requests queue summary — Owner-only, hidden in local mode
          (no public privacy-request surface there, so the card would always
          be a confusing zero). */}
      {isOwner && !isLocalApp && <PrivacyRequestsSummaryCard />}

      {/* Quick Actions */}
      <Card title="Quick Actions">
        <div className="flex flex-wrap gap-3">
          <Link to="/individuals/new">
            <Button>
              <Plus className="w-4 h-4 mr-2" />
              Add Individual
            </Button>
          </Link>
          <Link to="/families/new">
            <Button variant="secondary">
              <Plus className="w-4 h-4 mr-2" />
              Add Family
            </Button>
          </Link>
          <Link to="/export">
            <Button variant="secondary">
              Export GEDCOM
            </Button>
          </Link>
          {isOwner && (
            <Link to="/users">
              <Button variant="secondary">
                <Users className="w-4 h-4 mr-2" />
                User Manager
              </Button>
            </Link>
          )}
        </div>
      </Card>

      {/* Share Links — owners only */}
      {isOwner && <ShareLinksWidget />}

      {/* Recent Individuals */}
      <Card
        title="Recent Individuals"
        actions={
          <Link to="/individuals">
            <Button variant="ghost" size="sm">
              View All
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </Link>
        }
      >
        {recentIndividuals.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <User className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p>No individuals yet</p>
            <Link to="/individuals/new" className="text-emerald-600 hover:underline text-sm">
              Add your first individual
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {recentIndividuals.map((individual) => {
              const latestName = getLatestName(individual.names);
              const displayName = formatIndividualName(latestName);

              return (
                <Link
                  key={individual.id}
                  to={`/individuals/${individual.id}`}
                  className="flex items-center justify-between py-3 hover:bg-gray-50 -mx-6 px-6 transition-colors"
                >
                  <div>
                    <p className="font-medium text-gray-900">{displayName}</p>
                    <p className="text-sm text-gray-500">
                      {individual.birth_date || 'Birth unknown'}
                      {individual.death_date && ` – ${individual.death_date}`}
                    </p>
                  </div>
                  <span className="text-sm text-gray-400">{individual.gedcom_id}</span>
                </Link>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}


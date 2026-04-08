// Domain model types matching backend schemas

// ==================== Individual Names ====================
export interface IndividualName {
  id: number;
  name_type?: string;
  given_name?: string;
  family_name?: string;
  prefix?: string;
  suffix?: string;
  name_order?: number;
}

export interface IndividualNameCreate {
  name_type?: string;
  given_name?: string;
  family_name?: string;
  prefix?: string;
  suffix?: string;
  name_order?: number;
}

// ==================== Individuals ====================
export interface Individual {
  id: number;
  gedcom_id?: string;
  sex_code?: string;
  birth_date?: string;
  birth_date_approx?: string;
  birth_place?: string;
  death_date?: string;
  death_date_approx?: string;
  death_place?: string;
  notes?: string;
  names: IndividualName[];
  created_by?: string;
  created_at?: string;
}

export interface IndividualCreate {
  gedcom_id?: string;
  sex_code?: string;
  birth_date?: string;
  birth_date_approx?: string;
  birth_place?: string;
  death_date?: string;
  death_date_approx?: string;
  death_place?: string;
  notes?: string;
  names: IndividualNameCreate[];
}

export interface IndividualUpdate extends Partial<IndividualCreate> {}

// ==================== Family Members ====================
export interface FamilyMember {
  family_id: number;
  individual_id: number;
  role?: string;
}

export interface FamilyMemberCreate {
  individual_id: number;
  role?: string;
}

// ==================== Family Children ====================
export interface FamilyChild {
  family_id: number;
  child_id: number;
}

export interface FamilyChildCreate {
  child_id: number;
}

// ==================== Families ====================
export interface Family {
  id: number;
  gedcom_id?: string;
  marriage_date?: string;
  marriage_date_approx?: string;
  marriage_place?: string;
  divorce_date?: string;
  divorce_date_approx?: string;
  family_type?: string;
  notes?: string;
  members: FamilyMember[];
  children: FamilyChild[];
  created_by?: string;
  created_at?: string;
}

export interface FamilyCreate {
  gedcom_id?: string;
  marriage_date?: string;
  marriage_date_approx?: string;
  marriage_place?: string;
  divorce_date?: string;
  divorce_date_approx?: string;
  family_type?: string;
  notes?: string;
  members: FamilyMemberCreate[];
  children: FamilyChildCreate[];
}

export interface FamilyUpdate extends Partial<FamilyCreate> {}

// ==================== Events ====================
export interface Event {
  id: number;
  individual_id?: number;
  family_id?: number;
  event_type_code: string;
  event_date?: string;
  event_date_approx?: string;
  event_place?: string;
  description?: string;
}

export interface EventCreate {
  individual_id?: number;
  family_id?: number;
  event_type_code: string;
  event_date?: string;
  event_date_approx?: string;
  event_place?: string;
  description?: string;
}

export interface EventUpdate extends Partial<EventCreate> {}

// ==================== Media ====================
export interface Media {
  id: number;
  individual_id?: number;
  family_id?: number;
  file_path?: string;
  media_type_code?: string;
  media_date?: string;
  media_date_approx?: string;
  description?: string;
  is_default?: boolean;
  age_on_photo?: number;
}

export interface MediaCreate {
  individual_id?: number;
  family_id?: number;
  file_path?: string;
  media_type_code?: string;
  media_date?: string;
  media_date_approx?: string;
  description?: string;
  is_default?: boolean;
  age_on_photo?: number;
}

export interface MediaUpdate extends Partial<MediaCreate> {}

// ==================== Lookup Types ====================
export interface LookupType {
  code: string;
  description: string;
}

// ==================== Auth / Editor Types ====================
// editor: any authenticated user (owner or contributor)
// viewer: anonymous read-only access via share token

export type EditorRole = 'owner' | 'contributor';

export interface Editor {
  editor_id: string;
  display_name: string;
  email?: string;
  role: EditorRole;
  owner_id: string;       // which tree is active for this session
  is_active: boolean;
  created_at?: string;
  last_login_at?: string;
}

export interface LoginRequest {
  editor_id: string;
  password: string;
  owner_id?: string;      // required when contributor has multiple trees
}

export interface SignupRequest {
  editor_id: string;
  display_name: string;
  password: string;
  email?: string;
}

export interface SetPasswordRequest {
  token: string;
  editor_id: string;
  display_name: string;
  password: string;
  email?: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface AuthResponse {
  editor: Editor;
}

// ==================== Share Tokens ====================
export interface ShareToken {
  id: number;
  owner_id: string;
  token: string;
  label?: string;
  is_active: boolean;
  created_at?: string;
  last_used_at?: string;
  expires_after_days: number;
}

export interface ShareTokenCreate {
  label?: string;
  description?: string;  // alias accepted by backend
  expires_after_days?: number;
}

// ==================== Contributors / Invitations ====================
export interface Contributor {
  editor_id: string;
  display_name: string;
  email?: string;
  is_active: boolean;
  created_at: string;
  last_login_at?: string;
  approved_at?: string;
}

export interface Invitation {
  id: number;
  owner_id: string;
  display_name: string;
  email?: string;
  message?: string;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
  processed_at?: string;
}

export interface ContributeRequest {
  owner_id: string;
  display_name: string;
  email?: string;
  message?: string;
}

// ==================== Tree Visualization ====================
export interface TreeNodeName {
  name_type?: string;
  formatted: string;
}

export interface TreeNodeEvent {
  event_type: string;
  event_date?: string;
  event_date_approx?: string;
  event_place?: string;
  description?: string;
}

export interface TreeNodePhoto {
  url: string;
  age?: number;
  is_default: boolean;
}

export interface TreeNode {
  id: number;
  gedcom_id?: string;
  sex_code?: string;
  display_name: string;
  names?: TreeNodeName[];
  birth_date?: string;
  birth_date_approx?: string;
  birth_place?: string;
  death_date?: string;
  death_date_approx?: string;
  death_place?: string;
  notes?: string;
  photo_url?: string;
  photos: TreeNodePhoto[];
  generation: number;
  events: TreeNodeEvent[];
}

export interface TreeEdge {
  parent_id: number;
  child_id: number;
  family_id: number;
  relationship: 'biological' | 'non-biological';
}

export interface TreeCouple {
  family_id: number;
  partner_ids: number[];
  marriage_date?: string;
  marriage_date_approx?: string;
  divorce_date?: string;
  family_type?: string;
}

export interface TreeData {
  focus_id: number | null;
  max_ancestor_depth: number;
  max_descendant_depth: number;
  nodes: TreeNode[];
  edges: TreeEdge[];
  couples: TreeCouple[];
}

// ==================== Statistics ====================
export interface DatabaseStats {
  individuals_count: number;
  families_count: number;
  events_count: number;
  media_count: number;
}


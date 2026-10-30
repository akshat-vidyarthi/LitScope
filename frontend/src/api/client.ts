export interface User {
  id: number;
  email: string;
  full_name?: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface Project {
  id: number;
  name: string;
  description?: string;
  research_question?: string;
  scope?: string;
  inclusion_criteria?: string;
  exclusion_criteria?: string;
  owner_id?: number;
  member_count?: number;
  created_at: string;
}

export interface ProjectMember {
  membership_id: number;
  project_id: number;
  user_id: number;
  email: string;
  full_name?: string;
  role: string;
  created_at: string;
}

export interface PaperVersion {
  id: number;
  paper_id: number;
  file_path: string;
  file_checksum: string;
  file_size_bytes: number;
  page_count: number;
  extraction_status: 'completed' | 'scanned_image_only' | 'failed' | 'pending';
  error_message?: string;
  created_at: string;
}

export interface PaperPage {
  id: number;
  paper_version_id: number;
  page_number: number;
  content: string;
  character_count: number;
  created_at: string;
}

export interface Paper {
  id: number;
  title: string;
  doi?: string;
  authors?: string;
  year?: number;
  venue?: string;
  abstract?: string;
  access_status: string;
  created_at: string;
  latest_version?: PaperVersion;
}

export interface PaperUploadResponse {
  paper: Paper;
  version: PaperVersion;
  pages_extracted: number;
  is_duplicate: boolean;
  message: string;
}

export interface CuratedPaper {
  link_id: number;
  project_id: number;
  paper_id: number;
  title: string;
  doi?: string;
  year?: number;
  authors?: string;
  inclusion_status: string;
  notes?: string;
  date_added: string;
}

export interface RetrievedChunk {
  chunk_id: number;
  paper_id: number;
  paper_title: string;
  paper_authors?: string;
  paper_year?: number;
  page_number: number;
  content: string;
  score: number;
  citation: string;
}

export interface ProjectQuery {
  id: number;
  project_id: number;
  question: string;
  answer: string;
  citations: string[];
  retrieved_chunks: RetrievedChunk[];
  created_at: string;
}

const API_BASE = '/api/v1';

const getAuthHeaders = (): HeadersInit => {
  const token = localStorage.getItem('litscope_token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
};

const getAuthHeadersNoContentType = (): HeadersInit => {
  const token = localStorage.getItem('litscope_token');
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
};

export const api = {
  // Auth
  register: async (email: string, password: string, fullName?: string): Promise<User> => {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, full_name: fullName }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Registration failed');
    }
    return res.json();
  },

  login: async (email: string, password: string): Promise<{ access_token: string; user: User }> => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Invalid email or password');
    }
    const data = await res.json();
    localStorage.setItem('litscope_token', data.access_token);
    return data;
  },

  getCurrentUser: async (): Promise<User | null> => {
    const token = localStorage.getItem('litscope_token');
    if (!token) return null;
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      localStorage.removeItem('litscope_token');
      return null;
    }
    return res.json();
  },

  logout: () => {
    localStorage.removeItem('litscope_token');
  },

  // Health
  checkHealth: async () => {
    const res = await fetch(`${API_BASE}/health`);
    return res.json();
  },

  // Projects
  getProjects: async (): Promise<Project[]> => {
    const res = await fetch(`${API_BASE}/projects`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch projects');
    return res.json();
  },

  getProject: async (id: number): Promise<Project> => {
    const res = await fetch(`${API_BASE}/projects/${id}`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch project');
    return res.json();
  },

  createProject: async (data: Partial<Project>): Promise<Project> => {
    const res = await fetch(`${API_BASE}/projects`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to create project');
    return res.json();
  },

  // Project Members & Collaborator Invitations
  getProjectMembers: async (projectId: number): Promise<ProjectMember[]> => {
    const res = await fetch(`${API_BASE}/projects/${projectId}/members`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch members');
    return res.json();
  },

  addProjectMember: async (projectId: number, email: string, role: string): Promise<ProjectMember> => {
    const res = await fetch(`${API_BASE}/projects/${projectId}/members`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ email, role }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to add member');
    }
    return res.json();
  },

  removeProjectMember: async (projectId: number, userId: number): Promise<void> => {
    const res = await fetch(`${API_BASE}/projects/${projectId}/members/${userId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Failed to remove member');
  },

  updateProjectMemberRole: async (projectId: number, userId: number, role: string): Promise<ProjectMember> => {
    const res = await fetch(`${API_BASE}/projects/${projectId}/members/${userId}`, {
      method: 'PATCH',
      headers: getAuthHeaders(),
      body: JSON.stringify({ role }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to update member role');
    }
    return res.json();
  },

  // Project Curation
  getCuratedPapers: async (projectId: number): Promise<CuratedPaper[]> => {
    const res = await fetch(`${API_BASE}/projects/${projectId}/papers`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch curated papers');
    return res.json();
  },

  curatePaper: async (
    projectId: number,
    paperId: number,
    status: string,
    notes?: string
  ): Promise<any> => {
    const res = await fetch(`${API_BASE}/projects/${projectId}/papers`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        paper_id: paperId,
        inclusion_status: status,
        notes: notes || '',
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to curate paper');
    }
    return res.json();
  },

  removeCuratedPaper: async (projectId: number, paperId: number): Promise<void> => {
    const res = await fetch(`${API_BASE}/projects/${projectId}/papers/${paperId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to remove paper from project');
    }
  },

  // Master Library Papers
  getPapers: async (search?: string, year?: number): Promise<Paper[]> => {
    const params = new URLSearchParams();
    if (search) params.append('search', search);
    if (year) params.append('year', year.toString());
    const res = await fetch(`${API_BASE}/papers?${params.toString()}`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch papers');
    return res.json();
  },

  createPaper: async (data: Partial<Paper>): Promise<Paper> => {
    const res = await fetch(`${API_BASE}/papers`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to add paper');
    }
    return res.json();
  },

  uploadPdf: async (formData: FormData): Promise<PaperUploadResponse> => {
    const res = await fetch(`${API_BASE}/papers/upload`, {
      method: 'POST',
      headers: getAuthHeadersNoContentType(),
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to upload PDF');
    }
    return res.json();
  },

  getPaperPages: async (paperId: number, versionId?: number): Promise<PaperPage[]> => {
    const url = versionId
      ? `${API_BASE}/papers/${paperId}/pages?version_id=${versionId}`
      : `${API_BASE}/papers/${paperId}/pages`;
    const res = await fetch(url, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch paper pages');
    return res.json();
  },

  downloadPaperPdfBlob: async (paperId: number, versionId?: number): Promise<Blob> => {
    const url = versionId
      ? `${API_BASE}/papers/${paperId}/pdf?version_id=${versionId}`
      : `${API_BASE}/papers/${paperId}/pdf`;
    const res = await fetch(url, {
      headers: getAuthHeadersNoContentType(),
    });
    if (!res.ok) throw new Error('Failed to download PDF');
    return res.blob();
  },

  retryExtraction: async (paperId: number): Promise<PaperVersion> => {
    const res = await fetch(`${API_BASE}/papers/${paperId}/retry`, {
      method: 'POST',
      headers: getAuthHeaders(),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to retry extraction');
    }
    return res.json();
  },

  updatePaper: async (
    paperId: number,
    data: { title?: string; authors?: string; year?: number; venue?: string; abstract?: string }
  ): Promise<Paper> => {
    const res = await fetch(`${API_BASE}/papers/${paperId}`, {
      method: 'PATCH',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to update paper');
    }
    return res.json();
  },

  // Project RAG & Grounded Synthesis
  retrieveProjectEvidence: async (
    projectId: number,
    query: string,
    limit: number = 5
  ): Promise<RetrievedChunk[]> => {
    const res = await fetch(`${API_BASE}/projects/${projectId}/retrieve`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ query, limit }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to retrieve project evidence');
    }
    return res.json();
  },

  askProjectQuestion: async (
    projectId: number,
    question: string,
    limit: number = 5
  ): Promise<ProjectQuery> => {
    const res = await fetch(`${API_BASE}/projects/${projectId}/ask`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ question, limit }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to synthesize answer');
    }
    return res.json();
  },

  getProjectQueries: async (projectId: number): Promise<ProjectQuery[]> => {
    const res = await fetch(`${API_BASE}/projects/${projectId}/queries`, {
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Failed to fetch project queries');
    return res.json();
  },

  deleteProjectQuery: async (projectId: number, queryId: number): Promise<void> => {
    const res = await fetch(`${API_BASE}/projects/${projectId}/queries/${queryId}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    if (!res.ok) throw new Error('Failed to delete query');
  },
};

export interface Project {
  id: number;
  name: string;
  description?: string;
  research_question?: string;
  scope?: string;
  inclusion_criteria?: string;
  exclusion_criteria?: string;
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

const API_BASE = '/api/v1';

export const api = {
  // Health
  checkHealth: async () => {
    const res = await fetch(`${API_BASE}/health`);
    return res.json();
  },

  // Projects
  getProjects: async (): Promise<Project[]> => {
    const res = await fetch(`${API_BASE}/projects`);
    if (!res.ok) throw new Error('Failed to fetch projects');
    return res.json();
  },

  getProject: async (id: number): Promise<Project> => {
    const res = await fetch(`${API_BASE}/projects/${id}`);
    if (!res.ok) throw new Error('Failed to fetch project');
    return res.json();
  },

  createProject: async (data: Partial<Project>): Promise<Project> => {
    const res = await fetch(`${API_BASE}/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to create project');
    return res.json();
  },

  // Project Curation
  getCuratedPapers: async (projectId: number): Promise<CuratedPaper[]> => {
    const res = await fetch(`${API_BASE}/projects/${projectId}/papers`);
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
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        paper_id: paperId,
        inclusion_status: status,
        notes: notes || '',
      }),
    });
    if (!res.ok) throw new Error('Failed to curate paper');
    return res.json();
  },

  // Master Library Papers
  getPapers: async (search?: string, year?: number): Promise<Paper[]> => {
    const params = new URLSearchParams();
    if (search) params.append('search', search);
    if (year) params.append('year', year.toString());
    const res = await fetch(`${API_BASE}/papers?${params.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch papers');
    return res.json();
  },

  createPaper: async (data: Partial<Paper>): Promise<Paper> => {
    const res = await fetch(`${API_BASE}/papers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to add paper');
    }
    return res.json();
  },
};

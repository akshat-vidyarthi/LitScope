import React, { useState, useEffect } from 'react';
import {
  Plus,
  Folder,
  ArrowRight,
  Users,
  Trash2,
  Shield,
  UserPlus,
  Upload,
  BookOpen,
  Search,
  Sparkles,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Info,
  ArrowUp,
  ArrowDown,
  X,
  Calendar,
  Check,
  AlertCircle,
  Table,
  Compass,
  FileText,
  Edit3,
} from 'lucide-react';
import { api, Project, CuratedPaper, ProjectMember, User, Paper } from '../api/client';
import { UploadPdfModal } from './UploadPdfModal';
import { PaperReaderModal } from './PaperReaderModal';
import { SearchLibraryModal } from './SearchLibraryModal';
import { ProjectQAWorkspace } from './ProjectQAWorkspace';
import { ComparisonMatrixView } from './ComparisonMatrixView';
import { ResearchGapsView } from './ResearchGapsView';
import { LiteratureReviewView } from './LiteratureReviewView';
import { toast } from './Toast';
import { ConfirmModal } from './ConfirmModal';

interface ProjectsViewProps {
  currentUser: User | null;
  onOpenAuth: () => void;
}

export const ProjectsView: React.FC<ProjectsViewProps> = ({ currentUser, onOpenAuth }) => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [curatedPapers, setCuratedPapers] = useState<CuratedPaper[]>([]);
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showMembersModal, setShowMembersModal] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showSearchLibraryModal, setShowSearchLibraryModal] = useState(false);
  const [paperToRemove, setPaperToRemove] = useState<{ id: number; title: string } | null>(null);
  const [memberToRemove, setMemberToRemove] = useState<{ userId: number; username: string } | null>(null);
  const [readingPaper, setReadingPaper] = useState<Paper | null>(null);
  const [readingPage, setReadingPage] = useState<number | undefined>(undefined);
  const [activeTab, setActiveTab] = useState<'papers' | 'qa' | 'matrix' | 'gaps' | 'review'>(() => {
    const saved = localStorage.getItem('litscope_active_project_tab');
    if (saved === 'papers' || saved === 'qa' || saved === 'matrix' || saved === 'gaps' || saved === 'review') {
      return saved;
    }
    return 'papers';
  });

  const handleTabChange = (tab: 'papers' | 'qa' | 'matrix' | 'gaps' | 'review') => {
    setActiveTab(tab);
    localStorage.setItem('litscope_active_project_tab', tab);
  };

  const handleSelectProject = (project: Project) => {
    setSelectedProject(project);
    localStorage.setItem('litscope_active_project_id', project.id.toString());
  };

  // Project List Search & Sort Filter
  const [projectSearch, setProjectSearch] = useState<string>('');
  const [projectSortField, setProjectSortField] = useState<'recent' | 'alpha' | 'members'>('recent');
  const [projectSortDirection, setProjectSortDirection] = useState<'asc' | 'desc'>('desc');

  // Curated Papers Collapsible State
  const [expandedPaperIds, setExpandedPaperIds] = useState<number[]>([]);

  // Project Scope & Criteria Collapsible Drawer
  const [showProjectCriteria, setShowProjectCriteria] = useState(false);

  // Invite Form & Collaborators State
  const [inviteUsername, setInviteUsername] = useState('');
  const [inviteRole, setInviteRole] = useState('viewer');
  const [inviteSuccess, setInviteSuccess] = useState(false);
  const [inviteWarning, setInviteWarning] = useState<string | null>(null);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [userSuggestions, setUserSuggestions] = useState<{ id: number; username: string; full_name?: string }[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  // Edit Project Settings State
  const [showEditModal, setShowEditModal] = useState(false);
  const [editFormData, setEditFormData] = useState({
    name: '',
    scope: '',
    description: '',
    research_question: '',
    inclusion_criteria: '',
    exclusion_criteria: '',
  });
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const handleOpenEditModal = () => {
    if (!selectedProject) return;
    setEditFormData({
      name: selectedProject.name || '',
      scope: selectedProject.scope || '',
      description: selectedProject.description || '',
      research_question: selectedProject.research_question || '',
      inclusion_criteria: selectedProject.inclusion_criteria || '',
      exclusion_criteria: selectedProject.exclusion_criteria || '',
    });
    setEditError(null);
    setShowEditModal(true);
  };

  const handleSaveProjectEdits = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProject || !editFormData.name.trim()) return;
    setEditSaving(true);
    setEditError(null);
    try {
      const updated = await api.updateProject(selectedProject.id, {
        name: editFormData.name.trim(),
        scope: editFormData.scope.trim() || undefined,
        description: editFormData.description.trim() || undefined,
        research_question: editFormData.research_question.trim() || undefined,
        inclusion_criteria: editFormData.inclusion_criteria.trim() || undefined,
        exclusion_criteria: editFormData.exclusion_criteria.trim() || undefined,
      });
      setSelectedProject(updated);
      setProjects((prev) => prev.map((p) => (p.id === updated.id ? { ...p, ...updated } : p)));
      setShowEditModal(false);
    } catch (err: any) {
      setEditError(err.message || 'Failed to update project settings');
    } finally {
      setEditSaving(false);
    }
  };

  useEffect(() => {
    const query = inviteUsername.trim();
    if (query.length >= 1) {
      const timer = setTimeout(async () => {
        try {
          const results = await api.searchUsers(query);
          setUserSuggestions(results);
          setShowSuggestions(true);
        } catch {
          setUserSuggestions([]);
        }
      }, 200);
      return () => clearTimeout(timer);
    } else {
      setUserSuggestions([]);
      setShowSuggestions(false);
    }
  }, [inviteUsername]);
  const [updatingRoleId, setUpdatingRoleId] = useState<number | null>(null);

  // Form State
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    research_question: '',
    scope: '',
    inclusion_criteria: '',
    exclusion_criteria: '',
  });

  const loadProjects = async () => {
    if (!currentUser) {
      setProjects([]);
      setSelectedProject(null);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const data = await api.getProjects();
      setProjects(data);
      if (data.length > 0) {
        const savedId = localStorage.getItem('litscope_active_project_id');
        const matched = savedId ? data.find((p) => p.id === Number(savedId)) : null;
        setSelectedProject((prev) => {
          const chosen = prev ? data.find((p) => p.id === prev.id) || matched || data[0] : matched || data[0];
          if (chosen) {
            localStorage.setItem('litscope_active_project_id', chosen.id.toString());
          }
          return chosen;
        });
      } else {
        setSelectedProject(null);
        localStorage.removeItem('litscope_active_project_id');
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadProjectDetails = async (projectId: number) => {
    try {
      const [papers, membersList] = await Promise.all([
        api.getCuratedPapers(projectId),
        api.getProjectMembers(projectId),
      ]);
      setCuratedPapers(papers);
      setMembers(membersList);
      // Minimized by default for clean lazy column view
      setExpandedPaperIds([]);
    } catch (err) {
      console.error(err);
    }
  };

  const toggleExpandPaper = (paperId: number) => {
    setExpandedPaperIds((prev) =>
      prev.includes(paperId) ? prev.filter((id) => id !== paperId) : [...prev, paperId]
    );
  };



  // Filter and sort active projects for the left sidebar lazy column
  const filteredProjects = projects
    .filter((proj) => {
      if (!projectSearch.trim()) return true;
      const term = projectSearch.toLowerCase();
      return (
        proj.name.toLowerCase().includes(term) ||
        (proj.research_question && proj.research_question.toLowerCase().includes(term)) ||
        (proj.scope && proj.scope.toLowerCase().includes(term)) ||
        (proj.description && proj.description.toLowerCase().includes(term))
      );
    })
    .sort((a, b) => {
      const multiplier = projectSortDirection === 'asc' ? 1 : -1;
      if (projectSortField === 'recent') {
        const timeA = new Date(a.created_at).getTime() || a.id;
        const timeB = new Date(b.created_at).getTime() || b.id;
        return (timeA - timeB) * multiplier;
      }
      if (projectSortField === 'alpha') {
        return a.name.localeCompare(b.name) * multiplier;
      }
      if (projectSortField === 'members') {
        const countA = a.member_count ?? 1;
        const countB = b.member_count ?? 1;
        return (countA - countB) * multiplier;
      }
      return 0;
    });

  const handleRemovePaperFromStudy = (
    e: React.MouseEvent,
    paperId: number,
    paperTitle: string
  ) => {
    e.stopPropagation();
    if (!selectedProject) return;
    setPaperToRemove({ id: paperId, title: paperTitle });
  };

  const handleConfirmRemovePaper = async () => {
    if (!selectedProject || !paperToRemove) return;
    try {
      await api.removeCuratedPaper(selectedProject.id, paperToRemove.id);
      setCuratedPapers((prev) => prev.filter((p) => p.paper_id !== paperToRemove.id));
      setExpandedPaperIds((prev) => prev.filter((id) => id !== paperToRemove.id));
      toast.success(`Removed "${paperToRemove.title}" from project study.`);
    } catch (err: any) {
      toast.error(err.message || 'Failed to remove paper from study');
    } finally {
      setPaperToRemove(null);
    }
  };

  useEffect(() => {
    loadProjects();
  }, [currentUser]);

  useEffect(() => {
    if (selectedProject) {
      loadProjectDetails(selectedProject.id);
    }
  }, [selectedProject]);

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) return;
    try {
      const created = await api.createProject(formData);
      setProjects([created, ...projects]);
      setSelectedProject(created);
      localStorage.setItem('litscope_active_project_id', created.id.toString());
      toast.success(`Created project "${created.name}"`);
      setShowCreateModal(false);
      setFormData({
        name: '',
        description: '',
        research_question: '',
        scope: '',
        inclusion_criteria: '',
        exclusion_criteria: '',
      });
    } catch (err: any) {
      toast.error(err.message || 'Failed to create project');
    }
  };

  const handleInviteMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProject || !inviteUsername.trim()) return;

    setInviteWarning(null);
    setInviteError(null);

    const targetUsername = inviteUsername.trim().toLowerCase();
    const alreadyMember = members.some((m) => m.username.toLowerCase() === targetUsername);
    if (alreadyMember) {
      setInviteWarning(`@${inviteUsername.trim()} is already a collaborator on this project.`);
      return;
    }

    try {
      const added = await api.addProjectMember(selectedProject.id, inviteUsername.trim(), inviteRole);
      setMembers((prev) => {
        const existingIdx = prev.findIndex((m) => m.user_id === added.user_id);
        if (existingIdx >= 0) {
          const next = [...prev];
          next[existingIdx] = added;
          return next;
        }
        return [...prev, added];
      });
      setInviteUsername('');
      setInviteSuccess(true);
      setTimeout(() => {
        setInviteSuccess(false);
      }, 2500);

      // Automatically update collaborator count in sidebar list without manual refresh
      const newCount = (selectedProject.member_count ?? 1) + 1;
      setProjects((prev) =>
        prev.map((p) => (p.id === selectedProject.id ? { ...p, member_count: newCount } : p))
      );
      setSelectedProject((prev) => (prev ? { ...prev, member_count: newCount } : null));
    } catch (err: any) {
      setInviteError(err.message || 'Failed to invite collaborator');
    }
  };

  const handleUpdateMemberRole = async (userId: number, newRole: string) => {
    if (!selectedProject) return;
    try {
      setUpdatingRoleId(userId);
      setInviteError(null);
      await api.updateProjectMemberRole(selectedProject.id, userId, newRole);
      setMembers((prev) =>
        prev.map((m) => (m.user_id === userId ? { ...m, role: newRole } : m))
      );
    } catch (err: any) {
      setInviteError(err.message || 'Failed to update collaborator role');
    } finally {
      setUpdatingRoleId(null);
    }
  };

  const handleRemoveMember = (userId: number) => {
    if (!selectedProject) return;
    const targetMember = members.find((m) => m.user_id === userId);
    setMemberToRemove({ userId, username: targetMember?.username ? `@${targetMember.username}` : 'this collaborator' });
  };

  const handleConfirmRemoveMember = async () => {
    if (!selectedProject || !memberToRemove) return;
    try {
      await api.removeProjectMember(selectedProject.id, memberToRemove.userId);
      setMembers(members.filter((m) => m.user_id !== memberToRemove.userId));

      const newCount = Math.max(1, (selectedProject.member_count ?? 1) - 1);
      setProjects((prev) =>
        prev.map((p) => (p.id === selectedProject.id ? { ...p, member_count: newCount } : p))
      );
      setSelectedProject((prev) => (prev ? { ...prev, member_count: newCount } : null));
      toast.success('Removed collaborator from project.');
    } catch (err: any) {
      toast.error(err.message || 'Failed to remove member');
    } finally {
      setMemberToRemove(null);
    }
  };

  const handleOpenPaperReader = async (paperId: number, pageNumber?: number) => {
    try {
      const allPapers = await api.getPapers();
      const target = allPapers.find((p) => p.id === paperId);
      if (target) {
        setReadingPaper(target);
        setReadingPage(pageNumber);
      } else {
        toast.error('Paper details not found');
      }
    } catch (err: any) {
      toast.error('Failed to load paper reader: ' + err.message);
    }
  };

  if (!currentUser) {
    return (
      <div className="max-w-md mx-auto my-20 p-8 bg-white border border-slate-200 rounded-2xl shadow-sm text-center space-y-4">
        <div className="w-12 h-12 bg-indigo-50 text-indigo-600 rounded-full flex items-center justify-center mx-auto">
          <Shield className="w-6 h-6" />
        </div>
        <h2 className="text-xl font-bold text-slate-900">Private Research Workspace</h2>
        <p className="text-sm text-slate-500">
          LitScope enforces private-by-default access. Sign in to view and curate your research projects.
        </p>
        <button
          onClick={onOpenAuth}
          className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold shadow-sm transition"
        >
          Sign In / Create Account
        </button>
      </div>
    );
  }

  const currentMember = members.find((m) => m.user_id === currentUser.id);
  const myProjectRole = (
    selectedProject?.owner_id === currentUser.id
      ? 'owner'
      : (currentMember?.role || selectedProject?.current_user_role || 'viewer')
  ).toLowerCase();
  const isOwner = myProjectRole === 'owner';
  const canEdit = isOwner || myProjectRole === 'editor';

  return (
    <div className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-3.5">
      {/* Top Header */}
      <div className="flex justify-between items-center mb-3">
        <div className="flex items-center space-x-3">
          <h1 className="text-xl font-bold text-slate-900">Research Projects</h1>
          <span className="hidden sm:inline-block text-xs text-slate-400">
            • Curated collections & grounded RAG
          </span>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-xs transition"
        >
          <Plus className="w-3.5 h-3.5 mr-1.5" />
          New Project
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">Loading projects...</div>
      ) : projects.length === 0 ? (
        <div className="text-center py-16 bg-white border border-slate-200 rounded-xl p-8 shadow-sm">
          <Folder className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-800">No research projects yet</h3>
          <p className="text-sm text-slate-500 mt-1 mb-4">
            Create your first project to define research questions and curate papers.
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700"
          >
            Create First Project
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
          {/* Left Section: Active Projects Lazy Column */}
          <div className="lg:col-span-1 flex flex-col space-y-3">
            {/* Search and Sort Filter Card */}
            <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs space-y-2.5">
              <div className="flex items-center justify-between">
                <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  Active Projects ({filteredProjects.length})
                </h2>
                <span className="text-[11px] text-slate-400">
                  {projects.length} Total
                </span>
              </div>

              {/* Search Bar */}
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
                <input
                  type="text"
                  placeholder="Search projects..."
                  value={projectSearch}
                  onChange={(e) => setProjectSearch(e.target.value)}
                  className="w-full pl-8 pr-7 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs placeholder:text-slate-400 focus:bg-white focus:ring-2 focus:ring-indigo-500 focus:outline-none transition"
                />
                {projectSearch && (
                  <button
                    onClick={() => setProjectSearch('')}
                    className="absolute right-2 top-2 text-slate-400 hover:text-slate-600"
                    title="Clear search"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>

              {/* Filter / Sort Control with Interactive Up/Down Direction Toggle */}
              <div className="flex items-center space-x-1.5 pt-1 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setProjectSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))}
                  className="p-1 rounded-md hover:bg-slate-100 text-indigo-600 transition flex items-center justify-center cursor-pointer flex-shrink-0"
                  title={`Currently ${projectSortDirection === 'asc' ? 'Ascending' : 'Descending'}. Click to toggle.`}
                  aria-label="Toggle sort direction"
                >
                  {projectSortDirection === 'asc' ? (
                    <ArrowUp className="w-3.5 h-3.5 text-indigo-600" />
                  ) : (
                    <ArrowDown className="w-3.5 h-3.5 text-indigo-600" />
                  )}
                </button>
                <span className="text-[11px] font-medium text-slate-500 flex-shrink-0">Sort:</span>
                <select
                  value={projectSortField}
                  onChange={(e) => setProjectSortField(e.target.value as any)}
                  aria-label="Sort projects"
                  className="w-full text-xs bg-slate-50 border border-slate-200 rounded-md px-2 py-1 text-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-500 cursor-pointer"
                >
                  <option value="recent">Recent</option>
                  <option value="alpha">Alphabetically</option>
                  <option value="members">People (Collaborators)</option>
                </select>
                <span className="text-[10px] text-slate-400 uppercase font-semibold flex-shrink-0">
                  {projectSortDirection}
                </span>
              </div>
            </div>

            {/* Scrollable Lazy Column for Projects */}
            <div className="max-h-[calc(100vh-250px)] overflow-y-auto space-y-2.5 pr-1">
              {filteredProjects.length === 0 ? (
                <div className="p-6 text-center text-xs text-slate-400 bg-white border border-dashed border-slate-200 rounded-xl">
                  No projects match your filter.
                </div>
              ) : (
                filteredProjects.map((proj) => {
                  const isSelected = selectedProject?.id === proj.id;
                  const memberCount = proj.member_count ?? 1;

                  return (
                    <div
                      key={proj.id}
                      onClick={() => handleSelectProject(proj)}
                      className={`p-3.5 rounded-xl border transition-all cursor-pointer select-none ${
                        isSelected
                          ? 'bg-white border-indigo-600 ring-2 ring-indigo-100 shadow-sm'
                          : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/50 shadow-xs'
                      }`}
                    >
                      <div className="flex justify-between items-start gap-2">
                        <h3 className="font-semibold text-slate-900 text-sm leading-snug flex-1">
                          {proj.name}
                        </h3>
                        <ArrowRight
                          className={`w-4 h-4 flex-shrink-0 mt-0.5 transition ${
                            isSelected ? 'text-indigo-600 translate-x-0.5' : 'text-slate-300'
                          }`}
                        />
                      </div>

                      <div className="flex flex-wrap items-center gap-1.5 mt-2">
                        <span className={`inline-flex items-center text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${
                          (proj.owner_id === currentUser.id || proj.current_user_role === 'owner')
                            ? 'bg-indigo-50 text-indigo-700 border-indigo-200'
                            : proj.current_user_role === 'editor'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : 'bg-slate-100 text-slate-600 border-slate-200'
                        }`}>
                          {proj.owner_id === currentUser.id ? 'owner' : (proj.current_user_role || 'viewer')}
                        </span>
                        <span className="inline-flex items-center text-[10px] font-semibold bg-slate-100 text-slate-700 px-2 py-0.5 rounded-full border border-slate-200">
                          <Users className="w-3 h-3 mr-1 text-slate-400" />
                          {memberCount} {memberCount === 1 ? 'member' : 'members'}
                        </span>
                        {proj.scope && (
                          <span
                            className="inline-block text-[10px] bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-full font-medium border border-indigo-100 truncate max-w-[140px]"
                            title={proj.scope}
                          >
                            {proj.scope}
                          </span>
                        )}
                      </div>

                      {proj.research_question && (
                        <p className="mt-2 text-xs text-slate-500 line-clamp-2 italic">
                          "{proj.research_question}"
                        </p>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Right Section: Selected Project Details (Point 3 & 4) */}
          <div className="lg:col-span-3">
            {selectedProject && (
              <div className="bg-white border border-slate-200 rounded-xl p-4 sm:p-5 shadow-sm space-y-3.5">
                {/* Compact Project Header Bar */}
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pb-1">
                  <div className="flex items-center space-x-2.5 min-w-0">
                    <h2 className="text-lg font-bold text-slate-900 truncate" title={selectedProject.name}>
                      {selectedProject.name}
                    </h2>
                    <span className={`text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md border flex-shrink-0 ${
                      myProjectRole === 'owner'
                        ? 'bg-indigo-50 text-indigo-700 border-indigo-200'
                        : myProjectRole === 'editor'
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : 'bg-slate-100 text-slate-600 border-slate-200'
                    }`}>
                      {myProjectRole}
                    </span>
                  </div>

                  <div className="flex items-center space-x-2 flex-shrink-0">
                    <button
                      type="button"
                      onClick={() => setShowProjectCriteria(!showProjectCriteria)}
                      className={`inline-flex items-center px-2.5 py-1 text-xs font-semibold rounded-lg border transition ${
                        showProjectCriteria
                          ? 'bg-indigo-50 border-indigo-200 text-indigo-700'
                          : 'bg-slate-100 border-slate-200 text-slate-600 hover:bg-slate-200'
                      }`}
                      title="View or hide project research question and scope"
                    >
                      <Info className="w-3.5 h-3.5 mr-1" />
                      <span>Scope & Criteria</span>
                      {showProjectCriteria ? (
                        <ChevronUp className="w-3 h-3 ml-1" />
                      ) : (
                        <ChevronDown className="w-3 h-3 ml-1" />
                      )}
                    </button>

                    <button
                      type="button"
                      onClick={() => setShowMembersModal(true)}
                      className="inline-flex items-center px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg border border-slate-200 transition"
                    >
                      <Users className="w-3.5 h-3.5 mr-1.5 text-slate-500" />
                      Collaborators ({members.length})
                    </button>

                    {(myProjectRole === 'owner' || myProjectRole === 'editor') && (
                      <button
                        type="button"
                        onClick={handleOpenEditModal}
                        className="inline-flex items-center px-2.5 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-semibold rounded-lg border border-indigo-200 transition"
                        title="Edit project name, scope, and criteria"
                      >
                        <Edit3 className="w-3.5 h-3.5 mr-1" />
                        <span>Edit Project</span>
                      </button>
                    )}
                  </div>
                </div>

                {selectedProject.description && (
                  <p className="text-xs text-slate-600">{selectedProject.description}</p>
                )}

                {/* Collapsible Scope & Criteria Drawer (No longer taking 120px of fixed vertical space) */}
                {showProjectCriteria && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs animate-in fade-in duration-150">
                    <div>
                      <h4 className="text-[10px] font-bold uppercase text-slate-500 tracking-wider">
                        Research Question
                      </h4>
                      <p className="text-xs text-slate-800 mt-0.5 font-medium">
                        {selectedProject.research_question || 'Not specified'}
                      </p>
                    </div>
                    <div>
                      <h4 className="text-[10px] font-bold uppercase text-slate-500 tracking-wider">
                        Declared Scope
                      </h4>
                      <p className="text-xs text-slate-800 mt-0.5 font-medium">
                        {selectedProject.scope || 'Not specified'}
                      </p>
                    </div>
                    {selectedProject.inclusion_criteria && (
                      <div>
                        <h4 className="text-[10px] font-bold uppercase text-emerald-700 tracking-wider">
                          Inclusion Criteria
                        </h4>
                        <p className="text-xs text-slate-700 mt-0.5">
                          {selectedProject.inclusion_criteria}
                        </p>
                      </div>
                    )}
                    {selectedProject.exclusion_criteria && (
                      <div>
                        <h4 className="text-[10px] font-bold uppercase text-rose-700 tracking-wider">
                          Exclusion Criteria
                        </h4>
                        <p className="text-xs text-slate-700 mt-0.5">
                          {selectedProject.exclusion_criteria}
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {/* Workspace Tabs (Directly below project header) */}
                <div className="flex border-b border-slate-200 space-x-6">
                  <button
                    onClick={() => handleTabChange('papers')}
                    className={`pb-2.5 text-xs sm:text-sm font-semibold border-b-2 flex items-center transition ${
                      activeTab === 'papers'
                        ? 'border-indigo-600 text-indigo-600'
                        : 'border-transparent text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    <BookOpen className="w-4 h-4 mr-2" />
                    Papers Collection ({curatedPapers.length})
                  </button>
                  <button
                    onClick={() => handleTabChange('qa')}
                    className={`pb-2.5 text-xs sm:text-sm font-semibold border-b-2 flex items-center transition ${
                      activeTab === 'qa'
                        ? 'border-indigo-600 text-indigo-600'
                        : 'border-transparent text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    <Sparkles className="w-4 h-4 mr-2" />
                    Research Q&A (RAG)
                  </button>
                  <button
                    onClick={() => handleTabChange('matrix')}
                    className={`pb-2.5 text-xs sm:text-sm font-semibold border-b-2 flex items-center transition ${
                      activeTab === 'matrix'
                        ? 'border-indigo-600 text-indigo-600'
                        : 'border-transparent text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    <Table className="w-4 h-4 mr-2" />
                    Comparison Matrix
                  </button>
                  <button
                    onClick={() => handleTabChange('gaps')}
                    className={`pb-2.5 text-xs sm:text-sm font-semibold border-b-2 flex items-center transition ${
                      activeTab === 'gaps'
                        ? 'border-indigo-600 text-indigo-600'
                        : 'border-transparent text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    <Compass className="w-4 h-4 mr-2" />
                    Research Gaps
                  </button>
                  <button
                    onClick={() => handleTabChange('review')}
                    className={`pb-2.5 text-xs sm:text-sm font-semibold border-b-2 flex items-center transition ${
                      activeTab === 'review'
                        ? 'border-indigo-600 text-indigo-600'
                        : 'border-transparent text-slate-500 hover:text-slate-800'
                    }`}
                  >
                    <FileText className="w-4 h-4 mr-2" />
                    Literature Review
                  </button>
                </div>

                {/* Tab Content */}
                {activeTab === 'papers' ? (
                  <div className="space-y-3">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pb-1">
                      <div className="flex items-center space-x-3">
                        <h3 className="font-semibold text-slate-900 text-sm">
                          Curated Evidence Papers ({curatedPapers.length})
                        </h3>
                      </div>

                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => setShowSearchLibraryModal(true)}
                          className="inline-flex items-center px-2.5 py-1 text-xs font-semibold rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 border border-slate-200 transition"
                        >
                          <Search className="w-3.5 h-3.5 mr-1 text-slate-500" />
                          Search Library
                        </button>
                        <button
                          onClick={() => setShowUploadModal(true)}
                          className="inline-flex items-center px-2.5 py-1 text-xs font-semibold rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 transition"
                        >
                          <Upload className="w-3.5 h-3.5 mr-1 text-indigo-600" />
                          Add PDF
                        </button>
                      </div>
                    </div>

                    {curatedPapers.length === 0 ? (
                      <div className="border border-dashed border-slate-200 rounded-lg p-8 text-center text-slate-400 text-sm">
                        <p>No papers have been added to this project yet.</p>
                      </div>
                    ) : (
                      /* Lazy Column of Collapsible Curated Papers */
                      <div className="max-h-[calc(100vh-320px)] overflow-y-auto space-y-2.5 pr-1">
                        {curatedPapers.map((cp) => {
                          const isExpanded = expandedPaperIds.includes(cp.paper_id);

                          return (
                            <div
                              key={cp.link_id}
                              className="border border-slate-200 rounded-xl bg-white overflow-hidden shadow-xs hover:border-slate-300 transition"
                            >
                              {/* Minimized Header Row: Question/Paper Title Only (Point 3) */}
                              <div
                                onClick={() => toggleExpandPaper(cp.paper_id)}
                                className="p-3.5 bg-slate-50/70 hover:bg-slate-100/70 flex justify-between items-center gap-3 cursor-pointer select-none transition"
                              >
                                <div className="flex items-center space-x-2.5 flex-1 min-w-0">
                                  <div className="text-slate-400 hover:text-slate-600 p-0.5 flex-shrink-0">
                                    {isExpanded ? (
                                      <ChevronDown className="w-4 h-4 text-indigo-600" />
                                    ) : (
                                      <ChevronRight className="w-4 h-4" />
                                    )}
                                  </div>
                                  <div className="min-w-0 flex-1">
                                    <h4
                                      className="font-semibold text-slate-900 text-sm truncate"
                                      title={cp.title}
                                    >
                                      {cp.title}
                                    </h4>
                                    <p className="text-[11px] text-slate-500 truncate mt-0.5">
                                      {cp.authors || 'Unknown authors'} {cp.year ? `(${cp.year})` : ''}
                                    </p>
                                  </div>
                                </div>

                                <div className="flex items-center space-x-1.5 flex-shrink-0">
                                  {canEdit && (
                                    <button
                                      type="button"
                                      onClick={(e) => handleRemovePaperFromStudy(e, cp.paper_id, cp.title)}
                                      className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition"
                                      title="Remove from this study (keeps paper in Master Library)"
                                      aria-label="Remove paper from study"
                                    >
                                      <Trash2 className="w-4 h-4" />
                                    </button>
                                  )}
                                </div>
                              </div>

                              {/* Expanded Details Body */}
                              {isExpanded && (
                                <div className="p-4 border-t border-slate-100 bg-white space-y-3">
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                                      {cp.doi && (
                                        <span className="font-mono bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-200">
                                          DOI: {cp.doi}
                                        </span>
                                      )}
                                      {cp.date_added && (
                                        <span className="flex items-center text-slate-400">
                                          <Calendar className="w-3.5 h-3.5 mr-1 text-slate-400" />
                                          Added {new Date(cp.date_added).toLocaleDateString()}
                                        </span>
                                      )}
                                    </div>

                                    <button
                                      type="button"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleOpenPaperReader(cp.paper_id);
                                      }}
                                      className="inline-flex items-center px-3 py-1.5 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded-lg border border-indigo-200 transition shadow-xs"
                                    >
                                      <BookOpen className="w-3.5 h-3.5 mr-1.5 text-indigo-600" />
                                      Read Document
                                    </button>
                                  </div>

                                  {cp.notes && (
                                    <div className="text-xs bg-slate-50 p-3 rounded-lg border border-slate-100 text-slate-600">
                                      <span className="font-semibold text-slate-800">
                                        Project Notes:{' '}
                                      </span>
                                      {cp.notes}
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                ) : activeTab === 'matrix' ? (
                  <ComparisonMatrixView
                    project={selectedProject}
                    onOpenPaperReader={handleOpenPaperReader}
                    canEdit={canEdit}
                  />
                ) : activeTab === 'gaps' ? (
                  <ResearchGapsView
                    project={selectedProject}
                    canEdit={canEdit}
                    onOpenPaperReader={handleOpenPaperReader}
                  />
                ) : activeTab === 'review' ? (
                  <LiteratureReviewView
                    project={selectedProject}
                    canEdit={canEdit}
                    onOpenPaperReader={handleOpenPaperReader}
                  />
                ) : (
                  <ProjectQAWorkspace
                    project={selectedProject}
                    onOpenPaperReader={handleOpenPaperReader}
                  />
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Collaborators Modal */}
      {showMembersModal && selectedProject && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full p-6 space-y-5">
            <div className="flex justify-between items-baseline border-b border-slate-100 pb-3">
              <div className="flex items-center space-x-2">
                <h3 className="text-lg font-bold text-slate-900">Project Collaborators</h3>
                <span className="text-xs px-2 py-0.5 bg-slate-100 text-slate-600 rounded-full font-medium">
                  {members.length} {members.length === 1 ? 'member' : 'members'}
                </span>
              </div>
              <button
                onClick={() => {
                  setShowMembersModal(false);
                  setInviteWarning(null);
                  setInviteError(null);
                  setInviteSuccess(false);
                }}
                className="text-xs font-semibold text-slate-500 hover:text-slate-800"
              >
                Close
              </button>
            </div>

            {/* Invite New Collaborator Form (Owners Only) */}
            {isOwner && (
              <form onSubmit={handleInviteMember} className="bg-slate-50 p-3.5 rounded-xl border border-slate-200 space-y-2.5">
                <h4 className="text-xs font-bold uppercase text-slate-600 tracking-wider flex items-center">
                  <UserPlus className="w-3.5 h-3.5 mr-1.5 text-indigo-600" />
                  Invite Collaborator
                </h4>
                <div className="flex gap-2 relative">
                  <div className="relative flex-1">
                    <input
                      type="text"
                      pattern="^[a-zA-Z0-9_.-]+$"
                      required
                      autoComplete="off"
                      placeholder="Search by name or username (e.g. alex_rivera)"
                      value={inviteUsername}
                      onChange={(e) => {
                        setInviteUsername(e.target.value);
                        if (inviteWarning) setInviteWarning(null);
                        if (inviteError) setInviteError(null);
                      }}
                      onFocus={() => {
                        if (userSuggestions.length > 0) setShowSuggestions(true);
                      }}
                      className="w-full px-3 py-1.5 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none bg-white"
                    />

                    {/* Autocomplete Recommendations Dropdown */}
                    {showSuggestions && userSuggestions.length > 0 && (
                      <div className="absolute left-0 right-0 top-full mt-1 bg-white border border-slate-200 rounded-lg shadow-lg z-50 max-h-48 overflow-y-auto divide-y divide-slate-100">
                        {userSuggestions.map((u) => {
                          const isAlready = members.some((m) => m.user_id === u.id);
                          return (
                            <button
                              key={u.id}
                              type="button"
                              disabled={isAlready}
                              onClick={() => {
                                setInviteUsername(u.username);
                                setShowSuggestions(false);
                              }}
                              className="w-full text-left px-3 py-2 text-xs flex items-center justify-between hover:bg-indigo-50/50 disabled:opacity-50 disabled:hover:bg-transparent transition cursor-pointer"
                            >
                              <div className="flex items-center space-x-2">
                                <div className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center font-bold text-[10px] shrink-0">
                                  {u.full_name ? u.full_name[0].toUpperCase() : u.username[0].toUpperCase()}
                                </div>
                                <div className="truncate">
                                  <p className="font-semibold text-slate-800 leading-tight truncate">
                                    {u.full_name || `@${u.username}`}
                                  </p>
                                  <p className="text-[10px] text-slate-400 font-mono">@{u.username}</p>
                                </div>
                              </div>
                              {isAlready && (
                                <span className="text-[10px] text-slate-400 font-medium bg-slate-100 px-1.5 py-0.5 rounded shrink-0">
                                  Already Member
                                </span>
                              )}
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                  <select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value)}
                    className="px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs bg-white focus:outline-none cursor-pointer"
                  >
                    <option value="editor">Editor</option>
                    <option value="viewer">Viewer</option>
                  </select>
                  <button
                    type="submit"
                    disabled={inviteSuccess}
                    className={`inline-flex items-center justify-center min-w-[76px] px-3 py-1.5 text-xs font-semibold rounded-lg shadow-xs transition-all duration-200 ${
                      inviteSuccess
                        ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                        : 'bg-indigo-600 hover:bg-indigo-700 text-white'
                    }`}
                  >
                    {inviteSuccess ? (
                      <>
                        <Check className="w-3.5 h-3.5 mr-1 stroke-[2.5]" />
                        Invited!
                      </>
                    ) : (
                      'Invite'
                    )}
                  </button>
                </div>

                {/* Inline warning for already-existing collaborator */}
                {inviteWarning && (
                  <div className="flex items-center gap-1.5 px-3 py-2 bg-amber-50 border border-amber-200 text-amber-800 text-xs rounded-lg animate-in fade-in">
                    <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                    <span>{inviteWarning}</span>
                  </div>
                )}

                {/* Inline error for invitation failure */}
                {inviteError && (
                  <div className="flex items-center gap-1.5 px-3 py-2 bg-rose-50 border border-rose-200 text-rose-800 text-xs rounded-lg animate-in fade-in">
                    <AlertCircle className="w-3.5 h-3.5 text-rose-600 shrink-0" />
                    <span>{inviteError}</span>
                  </div>
                )}
              </form>
            )}

            {/* Current Members List */}
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {members.map((m) => (
                <div
                  key={m.membership_id}
                  className="flex justify-between items-center p-3 rounded-lg border border-slate-100 hover:bg-slate-50 transition"
                >
                  <div>
                    <p className="text-xs font-semibold text-slate-900">
                      {m.full_name || `@${m.username}`}
                    </p>
                    <p className="text-[11px] text-slate-500">@{m.username}</p>
                  </div>
                  <div className="flex items-center space-x-2">
                    {m.role === 'owner' ? (
                      <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full border bg-purple-50 text-purple-700 border-purple-200">
                        OWNER
                      </span>
                    ) : isOwner ? (
                      <select
                        value={m.role}
                        disabled={updatingRoleId === m.user_id}
                        onChange={(e) => handleUpdateMemberRole(m.user_id, e.target.value)}
                        className="text-[10px] font-bold uppercase px-2 py-1 rounded-lg border border-slate-300 bg-white text-slate-700 hover:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-500 cursor-pointer disabled:opacity-50"
                        title="Change collaborator access role"
                      >
                        <option value="editor">EDITOR</option>
                        <option value="viewer">VIEWER</option>
                      </select>
                    ) : (
                      <span
                        className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full border ${
                          m.role === 'editor'
                            ? 'bg-indigo-50 text-indigo-700 border-indigo-200'
                            : 'bg-slate-100 text-slate-600 border-slate-200'
                        }`}
                      >
                        {m.role}
                      </span>
                    )}
                    {isOwner && m.role !== 'owner' && (
                      <button
                        onClick={() => handleRemoveMember(m.user_id)}
                        className="text-slate-400 hover:text-rose-600 transition p-1"
                        title="Remove member"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Create Project Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4">
            <h3 className="text-lg font-bold text-slate-900">Create Research Project</h3>
            <form onSubmit={handleCreateProject} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">
                  Project Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Generative AI in Supply Chain"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">
                  Research Question
                </label>
                <textarea
                  rows={2}
                  placeholder="e.g. How do autonomous scheduling models reduce delivery latency?"
                  value={formData.research_question}
                  onChange={(e) =>
                    setFormData({ ...formData, research_question: e.target.value })
                  }
                  className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">
                  Declared Scope
                </label>
                <input
                  type="text"
                  placeholder="e.g. 2020-2026 empirical studies in manufacturing"
                  value={formData.scope}
                  onChange={(e) => setFormData({ ...formData, scope: e.target.value })}
                  className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase">
                    Inclusion Criteria
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Peer-reviewed"
                    value={formData.inclusion_criteria}
                    onChange={(e) =>
                      setFormData({ ...formData, inclusion_criteria: e.target.value })
                    }
                    className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase">
                    Exclusion Criteria
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Non-English, opinion"
                    value={formData.exclusion_criteria}
                    onChange={(e) =>
                      setFormData({ ...formData, exclusion_criteria: e.target.value })
                    }
                    className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex justify-end space-x-2 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-sm text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700"
                >
                  Save Project
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Project Settings Modal */}
      {showEditModal && selectedProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 my-8">
            <div className="flex justify-between items-center mb-4 pb-2 border-b border-slate-100">
              <div className="flex items-center space-x-2">
                <Edit3 className="w-5 h-5 text-indigo-600" />
                <h3 className="text-lg font-bold text-slate-900">Edit Project Settings</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowEditModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-100 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {editError && (
              <div className="mb-4 p-3 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-lg flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{editError}</span>
              </div>
            )}

            <form onSubmit={handleSaveProjectEdits} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">
                  Project Name <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={editFormData.name}
                  onChange={(e) => setEditFormData({ ...editFormData, name: e.target.value })}
                  className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  placeholder="e.g. Distributed Consensus in Cloud Systems"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">
                  Research Scope
                </label>
                <input
                  type="text"
                  value={editFormData.scope}
                  onChange={(e) => setEditFormData({ ...editFormData, scope: e.target.value })}
                  className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  placeholder="e.g. 2018-2025 Byzantine fault tolerance protocols"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">
                  Description / Overview
                </label>
                <textarea
                  rows={3}
                  value={editFormData.description}
                  onChange={(e) => setEditFormData({ ...editFormData, description: e.target.value })}
                  className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none resize-none"
                  placeholder="Brief summary of research objectives and background..."
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase">
                  Primary Research Question
                </label>
                <input
                  type="text"
                  value={editFormData.research_question}
                  onChange={(e) => setEditFormData({ ...editFormData, research_question: e.target.value })}
                  className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                  placeholder="e.g. What latency tradeoffs exist between Raft and PBFT?"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase">
                    Inclusion Criteria
                  </label>
                  <input
                    type="text"
                    value={editFormData.inclusion_criteria}
                    onChange={(e) => setEditFormData({ ...editFormData, inclusion_criteria: e.target.value })}
                    className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                    placeholder="e.g. Peer-reviewed, empirical"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase">
                    Exclusion Criteria
                  </label>
                  <input
                    type="text"
                    value={editFormData.exclusion_criteria}
                    onChange={(e) => setEditFormData({ ...editFormData, exclusion_criteria: e.target.value })}
                    className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                    placeholder="e.g. Non-English, preprints"
                  />
                </div>
              </div>

              <div className="flex justify-end space-x-2 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  disabled={editSaving}
                  onClick={() => setShowEditModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={editSaving || !editFormData.name.trim()}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition"
                >
                  {editSaving ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {/* Upload PDF Modal */}
      {showUploadModal && selectedProject && (
        <UploadPdfModal
          projects={projects}
          defaultProjectId={selectedProject.id}
          onClose={() => {
            setShowUploadModal(false);
            loadProjectDetails(selectedProject.id);
          }}
          onSuccess={() => {
            loadProjectDetails(selectedProject.id);
          }}
        />
      )}

      {/* Search Master Library Modal */}
      {showSearchLibraryModal && selectedProject && (
        <SearchLibraryModal
          project={selectedProject}
          curatedPapers={curatedPapers}
          onClose={() => setShowSearchLibraryModal(false)}
          onPaperAdded={() => {
            loadProjectDetails(selectedProject.id);
          }}
        />
      )}

      {/* Document Reader Modal */}
      {readingPaper && (
        <PaperReaderModal
          paper={readingPaper}
          initialPage={readingPage}
          onClose={() => {
            setReadingPaper(null);
            setReadingPage(undefined);
          }}
          onPaperUpdated={() => {
            if (selectedProject) loadProjectDetails(selectedProject.id);
          }}
        />
      )}

      {/* Confirm Remove Paper from Study Modal */}
      <ConfirmModal
        isOpen={!!paperToRemove}
        title="Remove Paper from Study"
        message={`Remove "${paperToRemove?.title || ''}" from this project study?\n\nNote: The paper will remain permanently safe in the Master Library.`}
        confirmText="Remove Paper"
        danger={true}
        onConfirm={handleConfirmRemovePaper}
        onCancel={() => setPaperToRemove(null)}
      />

      {/* Confirm Remove Collaborator Modal */}
      <ConfirmModal
        isOpen={!!memberToRemove}
        title="Remove Collaborator"
        message={`Are you sure you want to remove ${memberToRemove?.username || 'this collaborator'} from this project?`}
        confirmText="Remove Collaborator"
        danger={true}
        onConfirm={handleConfirmRemoveMember}
        onCancel={() => setMemberToRemove(null)}
      />
    </div>
  );
};

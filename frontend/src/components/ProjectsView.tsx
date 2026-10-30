import React, { useState, useEffect } from 'react';
import { Plus, Folder, ArrowRight, Users, Trash2, Shield, UserPlus } from 'lucide-react';
import { api, Project, CuratedPaper, ProjectMember, User } from '../api/client';

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

  // Invite Form
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('viewer');

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
        setSelectedProject((prev) => (prev ? data.find((p) => p.id === prev.id) || data[0] : data[0]));
      } else {
        setSelectedProject(null);
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
    } catch (err) {
      console.error(err);
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
      alert(err.message || 'Failed to create project');
    }
  };

  const handleInviteMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProject || !inviteEmail.trim()) return;
    try {
      const added = await api.addProjectMember(selectedProject.id, inviteEmail, inviteRole);
      setMembers([...members, added]);
      setInviteEmail('');
      alert(`Invited ${inviteEmail} as ${inviteRole}!`);
    } catch (err: any) {
      alert(err.message || 'Failed to invite collaborator');
    }
  };

  const handleRemoveMember = async (userId: number) => {
    if (!selectedProject || !confirm('Are you sure you want to remove this collaborator?')) return;
    try {
      await api.removeProjectMember(selectedProject.id, userId);
      setMembers(members.filter((m) => m.user_id !== userId));
    } catch (err: any) {
      alert(err.message || 'Failed to remove member');
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

  const isOwner = selectedProject?.owner_id === currentUser.id || currentUser.role === 'owner';

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Top Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Research Projects</h1>
          <p className="text-sm text-slate-500 mt-1">
            Curated collections with project-specific research questions and role-based collaboration.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg shadow-sm transition"
        >
          <Plus className="w-4 h-4 mr-2" />
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
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Projects Sidebar List */}
          <div className="lg:col-span-1 space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400 px-1">
              Active Projects ({projects.length})
            </h2>
            {projects.map((proj) => (
              <div
                key={proj.id}
                onClick={() => setSelectedProject(proj)}
                className={`p-4 rounded-xl border transition-all cursor-pointer ${
                  selectedProject?.id === proj.id
                    ? 'bg-white border-indigo-600 ring-2 ring-indigo-50 shadow-sm'
                    : 'bg-white border-slate-200 hover:border-slate-300'
                }`}
              >
                <div className="flex justify-between items-start">
                  <h3 className="font-semibold text-slate-900 text-sm">{proj.name}</h3>
                  <ArrowRight
                    className={`w-4 h-4 ${
                      selectedProject?.id === proj.id ? 'text-indigo-600' : 'text-slate-300'
                    }`}
                  />
                </div>
                {proj.scope && (
                  <span className="inline-block mt-2 text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-medium">
                    {proj.scope}
                  </span>
                )}
                {proj.research_question && (
                  <p className="mt-2 text-xs text-slate-500 line-clamp-2 italic">
                    "{proj.research_question}"
                  </p>
                )}
              </div>
            ))}
          </div>

          {/* Selected Project Details */}
          <div className="lg:col-span-2">
            {selectedProject && (
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-6">
                {/* Project Header with Collaborators Action */}
                <div className="border-b border-slate-100 pb-5">
                  <div className="flex justify-between items-baseline">
                    <h2 className="text-xl font-bold text-slate-900">{selectedProject.name}</h2>
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => setShowMembersModal(true)}
                        className="inline-flex items-center px-3 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition"
                      >
                        <Users className="w-3.5 h-3.5 mr-1.5" />
                        Collaborators ({members.length})
                      </button>
                      <span className="text-xs text-slate-400 font-mono">#{selectedProject.id}</span>
                    </div>
                  </div>
                  {selectedProject.description && (
                    <p className="text-sm text-slate-600 mt-1">{selectedProject.description}</p>
                  )}
                </div>

                {/* Research Question & Criteria Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-slate-50 p-4 rounded-lg border border-slate-100">
                  <div>
                    <h4 className="text-xs font-bold uppercase text-slate-500 tracking-wider">
                      Research Question
                    </h4>
                    <p className="text-sm text-slate-800 mt-1 font-medium">
                      {selectedProject.research_question || 'Not specified'}
                    </p>
                  </div>
                  <div>
                    <h4 className="text-xs font-bold uppercase text-slate-500 tracking-wider">
                      Declared Scope
                    </h4>
                    <p className="text-sm text-slate-800 mt-1 font-medium">
                      {selectedProject.scope || 'Not specified'}
                    </p>
                  </div>
                  {selectedProject.inclusion_criteria && (
                    <div>
                      <h4 className="text-xs font-bold uppercase text-emerald-700 tracking-wider">
                        Inclusion Criteria
                      </h4>
                      <p className="text-xs text-slate-700 mt-1">
                        {selectedProject.inclusion_criteria}
                      </p>
                    </div>
                  )}
                  {selectedProject.exclusion_criteria && (
                    <div>
                      <h4 className="text-xs font-bold uppercase text-rose-700 tracking-wider">
                        Exclusion Criteria
                      </h4>
                      <p className="text-xs text-slate-700 mt-1">
                        {selectedProject.exclusion_criteria}
                      </p>
                    </div>
                  )}
                </div>

                {/* Curated Papers List */}
                <div>
                  <div className="flex justify-between items-center mb-3">
                    <h3 className="font-semibold text-slate-900 text-sm">
                      Curated Papers in Collection ({curatedPapers.length})
                    </h3>
                    <span className="text-xs text-slate-400">
                      Curate papers from the Master Library tab
                    </span>
                  </div>

                  {curatedPapers.length === 0 ? (
                    <div className="border border-dashed border-slate-200 rounded-lg p-6 text-center text-slate-400 text-sm">
                      No papers have been curated into this project yet. Go to the{' '}
                      <span className="font-semibold text-indigo-600">Master Library</span> tab to
                      add papers.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {curatedPapers.map((cp) => (
                        <div
                          key={cp.link_id}
                          className="border border-slate-200 rounded-lg p-4 hover:border-slate-300 transition"
                        >
                          <div className="flex justify-between items-start">
                            <div className="space-y-1">
                              <h4 className="font-medium text-slate-900 text-sm">{cp.title}</h4>
                              <p className="text-xs text-slate-500">
                                {cp.authors || 'Unknown authors'} {cp.year ? `(${cp.year})` : ''}
                                {cp.doi && <span className="ml-2 font-mono">DOI: {cp.doi}</span>}
                              </p>
                            </div>
                            <span
                              className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${
                                cp.inclusion_status === 'included'
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  : cp.inclusion_status === 'candidate'
                                  ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                  : 'bg-rose-50 text-rose-700 border border-rose-200'
                              }`}
                            >
                              {cp.inclusion_status}
                            </span>
                          </div>
                          {cp.notes && (
                            <div className="mt-2 text-xs bg-slate-50 p-2 rounded border border-slate-100 text-slate-600">
                              <span className="font-semibold text-slate-700">Notes: </span>
                              {cp.notes}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
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
              <h3 className="text-lg font-bold text-slate-900">Project Collaborators</h3>
              <button
                onClick={() => setShowMembersModal(false)}
                className="text-xs font-semibold text-slate-500 hover:text-slate-800"
              >
                Close
              </button>
            </div>

            {/* Invite New Collaborator Form (Owners Only) */}
            {isOwner && (
              <form onSubmit={handleInviteMember} className="bg-slate-50 p-3.5 rounded-xl border border-slate-200 space-y-3">
                <h4 className="text-xs font-bold uppercase text-slate-600 tracking-wider flex items-center">
                  <UserPlus className="w-3.5 h-3.5 mr-1.5 text-indigo-600" />
                  Invite Collaborator
                </h4>
                <div className="flex gap-2">
                  <input
                    type="email"
                    required
                    placeholder="colleague@university.edu"
                    value={inviteEmail}
                    onChange={(e) => setInviteEmail(e.target.value)}
                    className="flex-1 px-3 py-1.5 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-none bg-white"
                  />
                  <select
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value)}
                    className="px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs bg-white focus:outline-none"
                  >
                    <option value="editor">Editor</option>
                    <option value="viewer">Viewer</option>
                  </select>
                  <button
                    type="submit"
                    className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-sm transition"
                  >
                    Invite
                  </button>
                </div>
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
                      {m.full_name || m.email}
                    </p>
                    <p className="text-[11px] text-slate-500">{m.email}</p>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span
                      className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full border ${
                        m.role === 'owner'
                          ? 'bg-purple-50 text-purple-700 border-purple-200'
                          : m.role === 'editor'
                          ? 'bg-indigo-50 text-indigo-700 border-indigo-200'
                          : 'bg-slate-100 text-slate-600 border-slate-200'
                      }`}
                    >
                      {m.role}
                    </span>
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
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import { Plus, Folder, ArrowRight } from 'lucide-react';
import { api, Project, CuratedPaper } from '../api/client';

export const ProjectsView: React.FC = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [curatedPapers, setCuratedPapers] = useState<CuratedPaper[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);

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
    try {
      setLoading(true);
      const data = await api.getProjects();
      setProjects(data);
      if (data.length > 0 && !selectedProject) {
        setSelectedProject(data[0]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadCuratedPapers = async (projectId: number) => {
    try {
      const papers = await api.getCuratedPapers(projectId);
      setCuratedPapers(papers);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  useEffect(() => {
    if (selectedProject) {
      loadCuratedPapers(selectedProject.id);
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
    } catch (err) {
      alert('Failed to create project');
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Top Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Research Projects</h1>
          <p className="text-sm text-slate-500 mt-1">
            Curated collections with project-specific research questions and scope boundaries.
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

          {/* Selected Project Details and Curated Papers */}
          <div className="lg:col-span-2">
            {selectedProject && (
              <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-6">
                {/* Project Header */}
                <div className="border-b border-slate-100 pb-5">
                  <div className="flex justify-between items-baseline">
                    <h2 className="text-xl font-bold text-slate-900">{selectedProject.name}</h2>
                    <span className="text-xs text-slate-400">ID: #{selectedProject.id}</span>
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

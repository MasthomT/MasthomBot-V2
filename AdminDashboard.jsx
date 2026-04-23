import React, { useState, useEffect } from 'react';
import { Settings, MessageSquare, Shield, Zap, Save, RefreshCw, ExternalLink, Info } from 'lucide-react';

const App = () => {
  const [config, setConfig] = useState({
    settings: {
      discord_link: '',
      youtube_link: '',
      planning: '',
      response_length: 150
    },
    personality: {
      system_prompt: '',
      base_context: '',
      intervention_rate: 20,
      roast_level: 10
    }
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('personality');
  const [status, setStatus] = useState({ type: '', message: '' });

  // Simulation de chargement (à remplacer par ton vrai fetch API)
  useEffect(() => {
    const fetchConfig = async () => {
      try {
        // const response = await fetch('/admin/config');
        // const data = await response.json();
        // setConfig(data);
        
        // Mock data pour la démo
        setTimeout(() => {
          setLoading(false);
        }, 800);
      } catch (error) {
        showStatus('error', "Impossible de charger la configuration.");
      }
    };
    fetchConfig();
  }, []);

  const showStatus = (type, message) => {
    setStatus({ type, message });
    setTimeout(() => setStatus({ type: '', message: '' }), 4000);
  };

  const handleSave = async (section) => {
    setSaving(true);
    try {
      // const endpoint = section === 'settings' ? '/admin/settings' : '/admin/personality';
      // await fetch(endpoint, { method: 'POST', body: JSON.stringify(config[section]) });
      
      setTimeout(() => {
        setSaving(false);
        showStatus('success', `Configuration ${section} enregistrée avec succès !`);
      }, 1000);
    } catch (error) {
      setSaving(false);
      showStatus('error', "Erreur lors de l'enregistrement.");
    }
  };

  const updateField = (section, field, value) => {
    setConfig(prev => ({
      ...prev,
      [section]: { ...prev[section], [field]: value }
    }));
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <RefreshCw className="w-12 h-12 text-indigo-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 p-4 md:p-8 font-sans">
      <div className="max-w-5xl mx-auto">
        
        {/* Header */}
        <header className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
              Félix Control Center
            </h1>
            <p className="text-slate-400 mt-1">Gérez le cerveau et les réglages de votre bot Twitch.</p>
          </div>
          <div className="flex gap-3">
            <button className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 px-4 py-2 rounded-lg transition-all border border-slate-700">
              <RefreshCw className="w-4 h-4" />
              Redémarrer le Bot
            </button>
          </div>
        </header>

        {/* Status Toast */}
        {status.message && (
          <div className={`fixed bottom-8 right-8 px-6 py-3 rounded-xl border shadow-2xl transition-all animate-bounce z-50 flex items-center gap-3 ${
            status.type === 'success' ? 'bg-emerald-900/80 border-emerald-500 text-emerald-200' : 'bg-rose-900/80 border-rose-500 text-rose-200'
          }`}>
            <Info className="w-5 h-5" />
            {status.message}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          
          {/* Sidebar Navigation */}
          <aside className="lg:col-span-1 space-y-2">
            <button 
              onClick={() => setActiveTab('personality')}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${activeTab === 'personality' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20' : 'hover:bg-slate-900 text-slate-400'}`}
            >
              <Zap className="w-5 h-5" />
              Personnalité
            </button>
            <button 
              onClick={() => setActiveTab('settings')}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${activeTab === 'settings' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20' : 'hover:bg-slate-900 text-slate-400'}`}
            >
              <Settings className="w-5 h-5" />
              Configuration
            </button>
            <div className="pt-6 border-t border-slate-800 mt-6">
              <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-800">
                <h4 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">Statut Système</h4>
                <div className="flex items-center gap-2 text-sm text-emerald-400">
                  <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></div>
                  Bot Twitch en ligne
                </div>
                <div className="flex items-center gap-2 text-sm text-slate-500 mt-1">
                  <div className="w-2 h-2 bg-slate-600 rounded-full"></div>
                  Database SQLite OK
                </div>
              </div>
            </div>
          </aside>

          {/* Main Content Area */}
          <main className="lg:col-span-3 space-y-6">
            
            {activeTab === 'personality' && (
              <section className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl animate-in fade-in slide-in-from-bottom-4 duration-500">
                <div className="p-6 border-b border-slate-800 flex justify-between items-center">
                  <div className="flex items-center gap-3">
                    <MessageSquare className="text-indigo-400" />
                    <h2 className="text-xl font-semibold">Cerveau de Félix</h2>
                  </div>
                  <button 
                    onClick={() => handleSave('personality')}
                    disabled={saving}
                    className="bg-indigo-500 hover:bg-indigo-400 disabled:opacity-50 text-white px-6 py-2 rounded-lg font-medium transition-all flex items-center gap-2"
                  >
                    {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                    Sauvegarder
                  </button>
                </div>
                
                <div className="p-6 space-y-6">
                  <div>
                    <label className="block text-sm font-medium text-slate-400 mb-2 uppercase tracking-wide">System Prompt (Le caractère de Félix)</label>
                    <textarea 
                      rows="4"
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl p-4 focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all resize-none outline-none"
                      placeholder="Ex: Tu es Félix, un chat noir sarcastique..."
                      value={config.personality.system_prompt}
                      onChange={(e) => updateField('personality', 'system_prompt', e.target.value)}
                    ></textarea>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label className="flex justify-between text-sm font-medium text-slate-400 mb-2">
                        Taux d'intervention <span>{config.personality.intervention_rate}%</span>
                      </label>
                      <input 
                        type="range" 
                        className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                        min="0" max="100"
                        value={config.personality.intervention_rate}
                        onChange={(e) => updateField('personality', 'intervention_rate', e.target.value)}
                      />
                      <p className="text-[10px] text-slate-500 mt-2 italic">Fréquence à laquelle le bot répond sans être mentionné.</p>
                    </div>
                    <div>
                      <label className="flex justify-between text-sm font-medium text-slate-400 mb-2">
                        Intensité du Roast <span>{config.personality.roast_level}/20</span>
                      </label>
                      <input 
                        type="range" 
                        className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-purple-500"
                        min="0" max="20"
                        value={config.personality.roast_level}
                        onChange={(e) => updateField('personality', 'roast_level', e.target.value)}
                      />
                      <p className="text-[10px] text-slate-500 mt-2 italic">Définit si Félix est juste taquin ou s'il détruit ses cibles.</p>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-400 mb-2 uppercase tracking-wide">Contexte de base</label>
                    <input 
                      type="text"
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 focus:ring-2 focus:ring-indigo-500 outline-none"
                      placeholder="Ex: Chat de Masthom, ambiance chill et gaming."
                      value={config.personality.base_context}
                      onChange={(e) => updateField('personality', 'base_context', e.target.value)}
                    />
                  </div>
                </div>
              </section>
            )}

            {activeTab === 'settings' && (
              <section className="bg-slate-900 border border-slate-800 rounded-2xl shadow-xl animate-in fade-in slide-in-from-bottom-4 duration-500">
                <div className="p-6 border-b border-slate-800 flex justify-between items-center">
                  <div className="flex items-center gap-3">
                    <Shield className="text-purple-400" />
                    <h2 className="text-xl font-semibold">Réglages Bot</h2>
                  </div>
                  <button 
                    onClick={() => handleSave('settings')}
                    disabled={saving}
                    className="bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white px-6 py-2 rounded-lg font-medium transition-all flex items-center gap-2"
                  >
                    {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                    Sauvegarder
                  </button>
                </div>
                
                <div className="p-6 space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label className="block text-sm font-medium text-slate-400 mb-2">Lien Discord</label>
                      <div className="relative">
                        <ExternalLink className="absolute left-3 top-3.5 w-4 h-4 text-slate-600" />
                        <input 
                          type="text"
                          className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 pl-10 focus:ring-2 focus:ring-purple-500 outline-none"
                          value={config.settings.discord_link}
                          onChange={(e) => updateField('settings', 'discord_link', e.target.value)}
                        />
                      </div>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-400 mb-2">Lien YouTube</label>
                      <div className="relative">
                        <ExternalLink className="absolute left-3 top-3.5 w-4 h-4 text-slate-600" />
                        <input 
                          type="text"
                          className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 pl-10 focus:ring-2 focus:ring-purple-500 outline-none"
                          value={config.settings.youtube_link}
                          onChange={(e) => updateField('settings', 'youtube_link', e.target.value)}
                        />
                      </div>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-400 mb-2">Planning des Streams</label>
                    <input 
                      type="text"
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 focus:ring-2 focus:ring-purple-500 outline-none"
                      placeholder="Lundi, Mercredi, Vendredi à 21h"
                      value={config.settings.planning}
                      onChange={(e) => updateField('settings', 'planning', e.target.value)}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-slate-400 mb-2">Longueur max des réponses IA</label>
                    <select 
                      className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 focus:ring-2 focus:ring-purple-500 outline-none appearance-none"
                      value={config.settings.response_length}
                      onChange={(e) => updateField('settings', 'response_length', e.target.value)}
                    >
                      <option value="100">Court (100 caractères)</option>
                      <option value="200">Standard (200 caractères)</option>
                      <option value="350">Long (350 caractères)</option>
                      <option value="500">Bavard (500 caractères)</option>
                    </select>
                  </div>
                </div>
              </section>
            )}

          </main>
        </div>
      </div>
    </div>
  );
};

export default App;

import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Flag, ChevronDown, ChevronUp, CheckCircle, Circle, ArrowLeft } from 'lucide-react';
import { Button } from '../components/ui/button';
import DashboardLayout from '../components/DashboardLayout';
import { useNavigate } from 'react-router-dom';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TAG_LABELS = {
  wrong_answer: '❌ Wrong answer',
  missed_info: '🔍 Missed relevant info',
  file_error: '📄 File read error',
  format_issue: '🌀 Format issue',
};

const STATUS_COLORS = {
  open: 'bg-red-500/20 text-red-400 border-red-500/30',
  resolved: 'bg-green-500/20 text-green-400 border-green-500/30',
  ignored: 'bg-muted text-muted-foreground border-border',
};

const ReportRow = ({ report, onStatusChange }) => {
  const [expanded, setExpanded] = useState(false);
  const [updating, setUpdating] = useState(false);

  const setStatus = async (status) => {
    setUpdating(true);
    try {
      await axios.patch(`${API}/admin/reports/${report.id}`, { status });
      onStatusChange(report.id, status);
      toast.success(`Marked as ${status}`);
    } catch {
      toast.error('Failed to update');
    } finally {
      setUpdating(false);
    }
  };

  return (
    <div className="border border-border rounded-lg overflow-hidden bg-card">
      <div
        className="flex items-start gap-3 p-4 cursor-pointer hover:bg-secondary/30 transition-colors"
        onClick={() => setExpanded(prev => !prev)}
      >
        <Flag className="h-4 w-4 text-red-400 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            {report.tags.map(tag => (
              <span key={tag} className="px-2 py-0.5 rounded-full text-xs bg-secondary border border-border text-muted-foreground">
                {TAG_LABELS[tag] || tag}
              </span>
            ))}
            <span className={`px-2 py-0.5 rounded-full text-xs border ${STATUS_COLORS[report.status] || STATUS_COLORS.open}`}>
              {report.status}
            </span>
          </div>
          <p className="text-sm text-foreground line-clamp-2 mb-1">
            <span className="text-muted-foreground text-xs mr-2">Q:</span>
            {report.userQuestion || '—'}
          </p>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span>{report.userEmail}</span>
            <span>{new Date(report.createdAt).toLocaleString()}</span>
            {report.agentType && <span className="px-1.5 py-0.5 rounded bg-secondary">{report.agentType}</span>}
          </div>
        </div>
        {expanded ? <ChevronUp className="h-4 w-4 text-muted-foreground flex-shrink-0" /> : <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />}
      </div>

      {expanded && (
        <div className="border-t border-border p-4 space-y-3 bg-secondary/20">
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1">User question</p>
            <p className="text-sm bg-secondary rounded-lg p-3">{report.userQuestion || '—'}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1">AI response (reported)</p>
            <p className="text-sm bg-secondary rounded-lg p-3 whitespace-pre-wrap max-h-48 overflow-y-auto">{report.messageContent}</p>
          </div>
          {report.comment && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">User comment</p>
              <p className="text-sm bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 text-amber-300">{report.comment}</p>
            </div>
          )}
          {report.activeSources?.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Active sources</p>
              <div className="flex flex-wrap gap-1.5">
                {report.activeSources.map((s, i) => (
                  <span key={i} className="px-2 py-0.5 rounded text-xs bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">{s}</span>
                ))}
              </div>
            </div>
          )}
          {report.chatHistory?.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">Chat context (last 6 messages)</p>
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {report.chatHistory.map((m, i) => (
                  <div key={i} className={`text-xs px-3 py-2 rounded-lg ${m.role === 'user' ? 'bg-primary/10 text-foreground ml-6' : 'bg-secondary text-muted-foreground mr-6'}`}>
                    <span className="font-medium mr-2">{m.role === 'user' ? '👤' : '🤖'}</span>
                    {m.content}
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="flex gap-2 pt-1">
            <Button size="sm" variant="outline" disabled={updating || report.status === 'resolved'}
              className="text-green-400 border-green-500/30 hover:bg-green-500/20"
              onClick={() => setStatus('resolved')}>
              <CheckCircle className="h-3.5 w-3.5 mr-1" /> Resolve
            </Button>
            <Button size="sm" variant="outline" disabled={updating || report.status === 'ignored'}
              className="text-muted-foreground hover:bg-secondary"
              onClick={() => setStatus('ignored')}>
              <Circle className="h-3.5 w-3.5 mr-1" /> Ignore
            </Button>
            {report.status !== 'open' && (
              <Button size="sm" variant="outline" disabled={updating}
                onClick={() => setStatus('open')}>
                Reopen
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const AdminReportsPage = () => {
  const [reports, setReports] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('open');
  const navigate = useNavigate();

  const fetchReports = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (statusFilter !== 'all') params.status = statusFilter;
      const res = await axios.get(`${API}/admin/reports`, { params });
      setReports(res.data.items || []);
      setTotal(res.data.total || 0);
    } catch {
      toast.error('Failed to load reports');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { fetchReports(); }, [fetchReports]);

  const handleStatusChange = (id, newStatus) => {
    setReports(prev => prev.map(r => r.id === id ? { ...r, status: newStatus } : r));
  };

  return (
    <DashboardLayout>
      <div className="p-6 max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Flag className="h-6 w-6 text-red-400" /> Reports
            </h1>
            <p className="text-sm text-muted-foreground">{total} total</p>
          </div>
        </div>

        <div className="flex gap-2 mb-5">
          {['open', 'resolved', 'ignored', 'all'].map(s => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors capitalize ${
                statusFilter === s
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'bg-secondary border-border text-muted-foreground hover:border-primary/50'
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="text-center py-12 text-muted-foreground">Loading...</div>
        ) : reports.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <Flag className="h-8 w-8 mx-auto mb-3 opacity-30" />
            <p>No reports found</p>
          </div>
        ) : (
          <div className="space-y-3">
            {reports.map(report => (
              <ReportRow key={report.id} report={report} onStatusChange={handleStatusChange} />
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
};

export default AdminReportsPage;

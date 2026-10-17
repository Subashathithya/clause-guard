import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ClipboardList, Eraser, FileUp } from 'lucide-react';
import { api } from '../../api';
import { useTicker } from '../../hooks';
import type { AnalysisResult } from '../../types';
import { Alert, Button } from '../ui/primitives';
import { FileUploader, SecureNote } from '../ui/data';
import { useToast } from '../ui/overlays';

const MIN_TEXT_CHARS = 50;

const STAGES = [
  { label: 'Reading your document', hint: 'Opening the text you provided.' },
  { label: 'Identifying the important sections', hint: 'Finding renewals, fees, liability and the rest.' },
  { label: 'Understanding each key clause', hint: 'Translating the wording into plain English.' },
  { label: 'Checking related sections', hint: 'Connecting clauses that talk to each other.' },
  { label: 'Preparing your summary', hint: 'Putting everything together for you.' },
];

export function AnalyzeExperience({
  mode,
  initialSource = 'paste',
}: {
  mode: 'contract' | 'terms';
  initialSource?: 'paste' | 'upload';
}) {
  const navigate = useNavigate();
  const toast = useToast();

  const [source, setSource] = useState<'paste' | 'upload'>(initialSource);
  const [documentName, setDocumentName] = useState('');
  const [documentText, setDocumentText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [fileLabel, setFileLabel] = useState<string>('');
  const [running, setRunning] = useState(false);
  const [validationError, setValidationError] = useState('');
  const [pipelineError, setPipelineError] = useState('');
  const [noClauses, setNoClauses] = useState(false);
  const [startedAt, setStartedAt] = useState(0);

  const tick = useTicker(running, 5000);
  const elapsedSec = running ? Math.floor((Date.now() - startedAt) / 1000) : 0;
  const stageIndex = Math.min(STAGES.length - 1, Math.floor(tick));

  const charCount = useMemo(() => documentText.length, [documentText]);
  const trimmed = documentText.trim();

  const startAnalysis = async (textBody: string, name: string, useFile = false) => {
    setPipelineError('');
    if (useFile) {
      if (!file) {
        setValidationError('Choose a file to analyse first.');
        return;
      }
    } else if (textBody.trim().length < MIN_TEXT_CHARS) {
      setValidationError(
        `That's ${textBody.trim().length} characters — please provide at least ${MIN_TEXT_CHARS} characters of text.`
      );
      return;
    }
    setValidationError('');
    setRunning(true);
    setNoClauses(false);
    setStartedAt(Date.now());
    try {
      const result: AnalysisResult = useFile
        ? await api.upload(file as File, name || (file as File).name)
        : await api.analyze(textBody, name || defaultName(mode));

      if (!result.document_id) {
        setNoClauses(true);
        setRunning(false);
        return;
      }
      navigate(`/contracts/${result.document_id}`);
    } catch (err) {
      setRunning(false);
      const msg = err instanceof Error ? err.message : 'Analysis failed. Please try again.';
      setPipelineError(msg);
      if (msg.includes('monthly') || msg.includes('quota')) {
        toast.push('You’ve used your free analyses for this month.', 'info');
      }
    }
  };

  const onPaste = () => startAnalysis(documentText, documentName);
  const onUpload = () => startAnalysis('', documentName, true);

  const reset = () => {
    setDocumentName('');
    setDocumentText('');
    setFile(null);
    setFileLabel('');
    setValidationError('');
    setPipelineError('');
    setNoClauses(false);
  };

  return (
    <div className="analyze-screen">
      {running ? (
        <RunningView stage={STAGES[stageIndex]} secs={elapsedSec} />
      ) : (
        <>
          <div className="tabs" role="tablist" aria-label="How to add your document">
            <button
              role="tab"
              aria-selected={source === 'paste'}
              className={['tab', source === 'paste' ? 'tab-active' : ''].filter(Boolean).join(' ')}
              onClick={() => setSource('paste')}
            >
              <ClipboardList size={15} /> Paste text
            </button>
            <button
              role="tab"
              aria-selected={source === 'upload'}
              className={['tab', source === 'upload' ? 'tab-active' : ''].filter(Boolean).join(' ')}
              onClick={() => setSource('upload')}
            >
              <FileUp size={15} /> Upload a file
            </button>
          </div>

          <input
            className="input mb-3"
            placeholder={mode === 'terms' ? 'e.g., ShopNow Terms & Conditions' : 'e.g., Gym membership agreement'}
            aria-label="Document name"
            value={documentName}
            onChange={(e) => setDocumentName(e.target.value)}
          />

          {source === 'paste' ? (
            <div className="card card-pad">
              <textarea
                className="textarea"
                rows={12}
                placeholder={
                  mode === 'terms'
                    ? 'Paste the terms & conditions here…'
                    : 'Paste the contract text here… (the whole document, or the sections you want checked)'
                }
                value={documentText}
                onChange={(e) => {
                  setDocumentText(e.target.value);
                  if (validationError) setValidationError('');
                }}
                aria-label="Contract text"
              />
              <div className="row-spread text-sm mt-2">
                <span className="faint">
                  {charCount.toLocaleString()} characters
                  {trimmed && trimmed.length < MIN_TEXT_CHARS
                    ? ` · need at least ${MIN_TEXT_CHARS}`
                    : trimmed
                      ? ' · ready'
                      : ''}
                </span>
                <button type="button" className="btn btn-ghost btn-sm" onClick={reset} disabled={!documentText}>
                  <Eraser size={14} /> Clear
                </button>
              </div>
              <Button className="mt-4" size="lg" loading={running} onClick={onPaste} disabled={!trimmed}>
                Analyze text
              </Button>
            </div>
          ) : (
            <div className="card card-pad">
              <FileUploader
                onFile={(f) => {
                  setFile(f);
                  setFileLabel(f.name);
                  if (validationError) setValidationError('');
                }}
                fileLabel={
                  fileLabel ? (
                    <p className="text-sm mt-3 mb-0" style={{ fontWeight: 600 }}>
                      Selected: {fileLabel}
                    </p>
                  ) : undefined
                }
              />
              <div className="mt-4 row">
                <Button size="lg" loading={running} onClick={onUpload} disabled={!file}>
                  Analyze file
                </Button>
              </div>
            </div>
          )}

          {validationError && (
            <div className="mt-3">
              <Alert tone="danger" title="A little more text, please">{validationError}</Alert>
            </div>
          )}
          {pipelineError && (
            <div className="mt-3">
              <Alert tone="danger" title="We couldn't finish that analysis">
                {pipelineError}. It usually means the analysis service is busy — please try again in a
                minute.
              </Alert>
            </div>
          )}
          {noClauses && (
            <div className="mt-3">
              <Alert tone="warning" title="No clear sections found">
                We couldn’t identify readable clauses from this text. It may be a table, a scanned page,
                or very short. Try pasting the sections as regular text and analysing again.
              </Alert>
            </div>
          )}

          <div className="mt-4">
            <SecureNote />
          </div>
        </>
      )}
    </div>
  );
}

function defaultName(mode: 'contract' | 'terms'): string {
  return mode === 'terms' ? 'Terms & Conditions' : 'My Contract';
}

function RunningView({ stage, secs }: { stage: { label: string; hint: string }; secs: number }) {
  return (
    <div className="analyze-running" role="status">
      <div className="ar-card card card-pad">
        <div className="ar-spinner" aria-hidden="true">
          <span className="spinner" />
        </div>
        <h3>{stage.label}…</h3>
        <p className="muted">{stage.hint}</p>
        <div className="ar-bar" aria-hidden="true">
          <div className="ar-bar-fill" />
        </div>
        <p className="text-xs faint">
          {secs < 60 ? `About ${secs}s so far` : `About ${Math.floor(secs / 60)}m ${secs % 60}s so far`} —
          most documents take under a minute.
        </p>
        <p className="text-xs faint">
          Your document is being read right now. Stay on this page and we’ll take you to the summary
          when it’s ready.
        </p>
      </div>
    </div>
  );
}
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ClipboardList, Eraser, FileUp } from 'lucide-react';
import { api } from '../../api';
import { useTicker } from '../../hooks';
import type { AnalysisResult } from '../../types';
import { Alert, Button, Field, Input } from '../ui/primitives';
import { FileUploader, SecureNote, Tabs } from '../ui/data';
import { useToast } from '../ui/overlays';
import { useI18n } from '../../i18n/I18nProvider';

const MIN_TEXT_CHARS = 50;

const STAGES = [
  { label: 'analyze.stage1Label', hint: 'analyze.stage1Hint' },
  { label: 'analyze.stage2Label', hint: 'analyze.stage2Hint' },
  { label: 'analyze.stage3Label', hint: 'analyze.stage3Hint' },
  { label: 'analyze.stage4Label', hint: 'analyze.stage4Hint' },
  { label: 'analyze.stage5Label', hint: 'analyze.stage5Hint' },
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
  const { t } = useI18n();

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
        setValidationError(t('analyze.chooseFile'));
        return;
      }
    } else if (textBody.trim().length < MIN_TEXT_CHARS) {
      setValidationError(
        t('analyze.tooShort', { count: textBody.trim().length, min: MIN_TEXT_CHARS })
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
        : await api.analyze(textBody, name || defaultName(mode, t));

      if (!result.document_id) {
        setNoClauses(true);
        setRunning(false);
        return;
      }
      navigate(`/contracts/${result.document_id}`);
    } catch (err) {
      setRunning(false);
      const msg = err instanceof Error ? err.message : t('analyze.failed');
      setPipelineError(msg);
      if (msg.includes('monthly') || msg.includes('quota')) {
        toast.push(t('analyze.quotaUsed'), 'info');
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
        <RunningView stage={{ label: t(STAGES[stageIndex].label), hint: t(STAGES[stageIndex].hint) }} secs={elapsedSec} />
      ) : (
        <>
          <Tabs
            label={t('analyze.howToAdd')}
            value={source}
            onChange={(id) => setSource(id as 'paste' | 'upload')}
            tabs={[
              { id: 'paste', label: (<><ClipboardList size={15} /> {t('analyze.pasteText')}</>) },
              { id: 'upload', label: (<><FileUp size={15} /> {t('analyze.uploadFile')}</>) },
            ]}
          />

          <Field label={t('analyze.documentName')} htmlFor="analyze-name" helper={t('analyze.documentNameHint')}>
            <Input
              id="analyze-name"
              placeholder={
                mode === 'terms'
                  ? t('analyze.namePlaceholderTerms')
                  : t('analyze.namePlaceholderContract')
              }
              value={documentName}
              onChange={(e) => setDocumentName(e.target.value)}
            />
          </Field>

          {source === 'paste' ? (
            <div className="card card-pad">
              <textarea
                className="textarea"
                rows={12}
                placeholder={
                  mode === 'terms'
                    ? t('analyze.pastePlaceholderTerms')
                    : t('analyze.pastePlaceholderContract')
                }
                value={documentText}
                onChange={(e) => {
                  setDocumentText(e.target.value);
                  if (validationError) setValidationError('');
                }}
                aria-label={t('analyze.contractText')}
              />
              <div className="row-spread text-sm mt-2">
                <span className="faint">
                  {t('contract.characters', { count: charCount.toLocaleString() })}
                  {trimmed && trimmed.length < MIN_TEXT_CHARS
                    ? t('analyze.needMore', { min: MIN_TEXT_CHARS })
                    : trimmed
                      ? t('analyze.ready')
                      : ''}
                </span>
                <button type="button" className="btn btn-ghost btn-sm" onClick={reset} disabled={!documentText}>
                  <Eraser size={14} /> {t('analyze.clear')}
                </button>
              </div>
              <Button className="mt-4" size="lg" loading={running} onClick={onPaste} disabled={!trimmed}>
                {t('analyze.analyzeText')}
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
                      {t('analyze.selected', { name: fileLabel })}
                    </p>
                  ) : undefined
                }
              />
              <div className="mt-4 row">
                <Button size="lg" loading={running} onClick={onUpload} disabled={!file}>
                  {t('analyze.analyzeFile')}
                </Button>
              </div>
            </div>
          )}

          {validationError && (
            <div className="mt-3">
              <Alert tone="danger" title={t('analyze.moreTextNeeded')}>{validationError}</Alert>
            </div>
          )}
          {pipelineError && (
            <div className="mt-3">
              <Alert tone="danger" title={t('analyze.couldNotFinish')}>
                {pipelineError}. {t('analyze.busyNote')}
              </Alert>
            </div>
          )}
          {noClauses && (
            <div className="mt-3">
              <Alert tone="warning" title={t('analyze.noSectionsFound')}>
                {t('analyze.noClausesBody')}
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

function defaultName(mode: 'contract' | 'terms', t: (key: string) => string): string {
  return mode === 'terms' ? t('analyze.defaultNameTerms') : t('analyze.defaultNameContract');
}

function RunningView({ stage, secs }: { stage: { label: string; hint: string }; secs: number }) {
  const { t } = useI18n();
  return (
    <div className="analyze-running" role="status">
      <div className="ar-card card card-pad">
        <div className="ar-spinner" aria-hidden="true">
          <span className="spinner" />
        </div>
        <h2>{stage.label}…</h2>
        <p className="muted">{stage.hint}</p>
        <div className="ar-bar" aria-hidden="true">
          <div className="ar-bar-fill" />
        </div>
        <p className="text-xs faint">
          {secs < 60
            ? t('analyze.elapsedShort', { secs })
            : t('analyze.elapsedLong', { minutes: Math.floor(secs / 60), secs: secs % 60 })}{' '}
          — {t('analyze.mostUnderMinute')}
        </p>
        <p className="text-xs faint">{t('analyze.runningNote')}</p>
      </div>
    </div>
  );
}
import { useEffect, useRef, useState } from 'react';
import { SendHorizonal, Sparkles } from 'lucide-react';
import type { ChatMessage, ChatResponse } from '../../types';
import { Button } from '../ui/primitives';
import { useI18n } from '../../i18n/I18nProvider';

const SUGGESTED = [
  'chat.suggest1',
  'chat.suggest2',
  'chat.suggest3',
  'chat.suggest4',
  'chat.suggest5',
];

export function ChatThread({
  getAnswer,
  contextLabel,
}: {
  getAnswer: (question: string, history: ChatMessage[]) => Promise<ChatResponse>;
  contextLabel: string;
}) {
  const { t } = useI18n();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, busy]);

  const send = async (question: string) => {
    const q = question.trim();
    if (!q || busy) return;
    setError(null);
    const history = messages.slice(-10);
    setMessages((prev) => [...prev, { role: 'user', content: q }]);
    setInput('');
    setBusy(true);
    try {
      const res = await getAnswer(q, history);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: res.answer, sources: res.sources },
      ]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : t('common.somethingWentWrong');
      setError(msg);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: t('chat.couldNotAnswer', { msg }) },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="chat-thread">
      <div className="ct-hint" aria-hidden="true">
        <Sparkles size={14} />
        {t('chat.basedOn', { context: contextLabel })}
      </div>

      <div className="ct-messages" role="log" aria-live="polite">
        {messages.length === 0 && (
          <div className="ct-welcome">
            <p>{t('chat.intro')}</p>
            <div className="ct-suggest">
              {SUGGESTED.map((key) => (
                <button key={key} type="button" className="suggest-chip" onClick={() => send(t(key))} disabled={busy}>
                  {t(key)}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`ct-msg msg-${m.role}`}>
            {m.role === 'assistant' && m.sources && m.sources.length > 0 && (
              <div className="ct-cites">
                {m.sources.slice(0, 3).map((s, si) => (
                  <span key={si} className="cite-chip" title={t('chat.source')}>
                    {s.document_name}
                  </span>
                ))}
              </div>
            )}
            <div className="ct-bubble">
              {m.content.split('\n').map((line, li) => (
                <p key={li} className="ct-p">
                  {line}
                </p>
              ))}
            </div>
          </div>
        ))}

        {busy && (
          <div className="ct-msg msg-assistant">
            <div className="ct-bubble ct-thinking">
              {t('chat.reading')} <span className="spinner" />
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="ct-input-row">
        <input
          className="input"
          type="text"
          placeholder={t('chat.inputPlaceholder')}
          value={input}
          aria-label={t('chat.placeholder')}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              send(input);
            }
          }}
          disabled={busy}
        />
        <Button onClick={() => send(input)} disabled={busy || !input.trim()} aria-label={t('chat.send')}>
          <SendHorizonal size={16} />
        </Button>
      </div>
      {error && <p className="text-xs text-center" style={{ color: 'var(--danger-text)' }}>{error}</p>}
    </div>
  );
}
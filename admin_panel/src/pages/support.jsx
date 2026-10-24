import { useEffect, useRef, useState } from 'react';
import { Headphones, Send } from 'lucide-react';
import toast from 'react-hot-toast';
import AdminLayout from '@/components/layout/AdminLayout';
import { getMediaUrl } from '@/lib/utils';
import { sendSupportTyping, startSupportSocket, stopSupportSocket } from '@/lib/supportSocket';
import {
  useGetSupportInboxQuery,
  useGetSupportThreadQuery,
  useMarkSupportReadMutation,
  useReplySupportMutation,
  supportApi,
} from '@/store/api/supportApi';
import { useDispatch } from 'react-redux';

function when(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

export default function SupportPage() {
  const dispatch = useDispatch();
  const [selected, setSelected] = useState(null);
  const [draft, setDraft] = useState('');
  const [customerTyping, setCustomerTyping] = useState(false);
  const selectedRef = useRef(null);
  const endRef = useRef(null);
  const typingTimer = useRef(null);
  const refetchRef = useRef(() => {});
  const markReadRef = useRef(() => {});
  const { data: inbox, refetch } = useGetSupportInboxQuery();
  const { data: thread } = useGetSupportThreadQuery(selected, { skip: !selected });
  const [markRead] = useMarkSupportReadMutation();
  const [reply, { isLoading: sending }] = useReplySupportMutation();

  useEffect(() => {
    selectedRef.current = selected;
    setCustomerTyping(false);
  }, [selected]);

  useEffect(() => {
    refetchRef.current = refetch;
    markReadRef.current = markRead;
  }, [refetch, markRead]);

  useEffect(() => {
    startSupportSocket({
      onMessage: (message) => {
        refetchRef.current();
        const openId = selectedRef.current;
        if (!openId || message.conversation_id !== openId) return;
        dispatch(supportApi.util.updateQueryData('getSupportThread', openId, (draftThread) => {
          if (!draftThread.messages.some((row) => row.id === message.id)) {
            draftThread.messages.push(message);
          }
        }));
        if (message.author === 'customer') markReadRef.current(openId);
        dispatch(supportApi.util.invalidateTags([{ type: 'SupportThread', id: openId }]));
        setCustomerTyping(false);
      },
      onRead: (event) => {
        const openId = selectedRef.current;
        if (!openId || event.conversation_id !== openId) return;
        dispatch(supportApi.util.updateQueryData('getSupportThread', openId, (draftThread) => {
          draftThread.messages.forEach((row) => {
            if (row.author === event.author && !row.read_at) row.read_at = event.read_at;
          });
        }));
      },
      onTyping: (event) => {
        if (event.author !== 'customer' || event.conversation_id !== selectedRef.current) return;
        setCustomerTyping(Boolean(event.active));
      },
    });
    return () => {
      clearTimeout(typingTimer.current);
      stopSupportSocket();
    };
  }, [dispatch]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
  }, [thread?.messages?.length, customerTyping]);

  const conversations = inbox?.results || [];
  const messages = thread?.messages || [];

  const send = async () => {
    const body = draft.trim();
    if (!selected || !body || sending) return;
    setDraft('');
    sendSupportTyping(selected, false);
    try {
      await reply({ id: selected, body }).unwrap();
    } catch {
      setDraft(body);
      toast.error('The reply could not be sent.');
    }
  };

  const onDraft = (value) => {
    setDraft(value);
    if (!selected) return;
    sendSupportTyping(selected, value.trim().length > 0);
    clearTimeout(typingTimer.current);
    typingTimer.current = setTimeout(() => sendSupportTyping(selected, false), 2000);
  };

  return (
    <AdminLayout title="Support">
      <div className="grid h-[calc(100vh-8.5rem)] grid-cols-1 overflow-hidden rounded-2xl border border-slate-200 bg-white lg:grid-cols-[320px_1fr]">
        <aside className="overflow-y-auto border-b border-slate-200 lg:border-b-0 lg:border-r">
          <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-4">
            <Headphones className="h-5 w-5 text-primary-500" />
            <h2 className="text-sm font-semibold text-slate-900">Conversations</h2>
          </div>
          {conversations.length === 0 ? (
            <p className="px-4 py-8 text-sm text-slate-500">No support chats yet.</p>
          ) : (
            <ul>
              {conversations.map((row) => {
                const active = row.id === selected;
                return (
                  <li key={row.id}>
                    <button
                      type="button"
                      onClick={() => setSelected(row.id)}
                      className={`flex w-full items-start gap-3 px-4 py-3 text-left ${active ? 'bg-primary-50' : 'hover:bg-slate-50'}`}
                    >
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center justify-between gap-2">
                          <span className="truncate text-sm font-semibold text-slate-900">{row.customer_name}</span>
                          {row.staff_unread > 0 && (
                            <span className="rounded-full bg-primary-500 px-2 py-0.5 text-[11px] font-semibold text-white">
                              {row.staff_unread}
                            </span>
                          )}
                        </span>
                        <span className="mt-0.5 block truncate text-xs text-slate-500">
                          {row.topic_label || row.preview || 'New conversation'}
                        </span>
                        <span className="mt-1 block text-[11px] text-slate-400">{when(row.last_message_at)}</span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </aside>

        <section className="flex min-h-[420px] flex-col">
          {!selected || !thread ? (
            <div className="flex flex-1 items-center justify-center px-6 text-center text-sm text-slate-500">
              Choose a conversation to read it and reply.
            </div>
          ) : (
            <>
              <header className="border-b border-slate-100 px-5 py-4">
                <h2 className="text-base font-semibold text-slate-900">{thread.customer_name}</h2>
                <p className="text-xs text-slate-500">{thread.customer_email}</p>
              </header>
              <div className="flex-1 space-y-3 overflow-y-auto bg-slate-50 px-5 py-4">
                {messages.map((message) => (
                  <Message key={message.id} message={message} />
                ))}
                {customerTyping && <p className="text-xs text-slate-500">Customer is typing…</p>}
                <div ref={endRef} />
              </div>
              <form
                className="flex items-end gap-2 border-t border-slate-100 p-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  send();
                }}
              >
                <textarea
                  value={draft}
                  onChange={(event) => onDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault();
                      send();
                    }
                  }}
                  rows={2}
                  placeholder="Write a reply"
                  className="min-h-[44px] flex-1 resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-primary-400"
                />
                <button
                  type="submit"
                  disabled={sending || !draft.trim()}
                  className="inline-flex h-11 items-center gap-2 rounded-xl bg-primary-500 px-4 text-sm font-semibold text-white disabled:opacity-50"
                >
                  <Send className="h-4 w-4" />
                  Send
                </button>
              </form>
            </>
          )}
        </section>
      </div>
    </AdminLayout>
  );
}

function Message({ message }) {
  const mine = message.author === 'agent';
  const image = getMediaUrl(message.image);
  const text = message.topic_label || message.body;
  return (
    <div className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[80%] ${mine ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
        {(text || image) && (
          <div className={`rounded-2xl px-3 py-2 text-sm ${mine ? 'bg-primary-500 text-white' : 'border border-slate-200 bg-white text-slate-800'}`}>
            {image && <img src={image} alt="Attachment" className="mb-2 max-h-40 rounded-lg" />}
            {text}
          </div>
        )}
        {message.order && <OrderCard order={message.order} />}
        <span className="text-[11px] text-slate-400">
          {when(message.created_at)}
          {mine && message.read_at ? ' · Read' : ''}
        </span>
      </div>
    </div>
  );
}

function OrderCard({ order }) {
  const image = getMediaUrl(order.product_image);
  return (
    <div className="w-64 rounded-2xl border border-slate-200 bg-white p-3 text-sm text-slate-800">
      <div className="flex gap-3">
        {image && <img src={image} alt={order.product_name || 'Product'} className="h-12 w-12 rounded-lg object-cover" />}
        <div className="min-w-0">
          <p className="font-semibold">Order {order.display_number}</p>
          <p className="truncate text-slate-500">{order.product_name}</p>
        </div>
      </div>
      <p className="mt-2 text-xs font-semibold text-primary-600">{order.status_label}</p>
      {order.expected_delivery && (
        <p className="mt-1 text-xs text-slate-500">Expected delivery {order.expected_delivery}</p>
      )}
    </div>
  );
}

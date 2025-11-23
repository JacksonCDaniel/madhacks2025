import { useState, useEffect, useRef } from "react";
import io from "socket.io-client";
import { Editor } from "@monaco-editor/react";
import { MessageSquare } from "lucide-react";
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from "motion/react";

const API_BASE = 'http://127.0.0.1:5067';

export default function InterviewOverlay({ company, voice, details, onEnd }) {
    const [chatOpen, setChatOpen] = useState(true);
    const [code, setCode] = useState("");
    const editorRef = useRef(null);
    const [showConfirm, setShowConfirm] = useState(false);
    
    // Chat state
    const [messages, setMessages] = useState([]);
    const [conversationId, setConversationId] = useState(null);
    const [messageInput, setMessageInput] = useState("");
    const [isTyping, setIsTyping] = useState(false);
    const [isSending, setIsSending] = useState(false);
    const socketRef = useRef(null);
    const messagesListRef = useRef(null);

    // Auto-scroll to bottom. Use the messages list element so we can
    // scroll to the container's scrollHeight after layout changes.
    const scrollToBottom = (behavior = "smooth") => {
        const el = messagesListRef.current;
        if (!el) return;
        // Ensure layout has updated before scrolling
        requestAnimationFrame(() => {
            el.scrollTo({ top: el.scrollHeight, behavior });
        });
    };

    useEffect(() => {
        const lastMsg = messages[messages.length - 1];
        // If the assistant message is streaming, use `auto` to avoid
        // smooth animation cutting off the live-updating content.
        const behavior = lastMsg && lastMsg.isStreaming ? "auto" : "smooth";
        scrollToBottom(behavior);
    }, [messages, isTyping]);

    // Initialize WebSocket connection
    useEffect(() => {
        socketRef.current = io(API_BASE);
        
        socketRef.current.on('connect', () => {
            console.log('Connected to WebSocket');
        });

        socketRef.current.on('llm_response', (chunk) => {
            setMessages(prev => {
                const lastMsg = prev[prev.length - 1];
                if (lastMsg && lastMsg.role === 'assistant' && lastMsg.isStreaming) {
                    return [
                        ...prev.slice(0, -1),
                        { ...lastMsg, content: lastMsg.content + chunk }
                    ];
                }
                return prev;
            });
        });

        return () => {
            if (socketRef.current) {
                socketRef.current.disconnect();
            }
        };
    }, []);

    // Create conversation on mount
    useEffect(() => {
        const createConversation = async () => {
            try {
                const response = await fetch(`${API_BASE}/conversations`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: 'web-user',
                        problem_title: details.title || 'Interview Problem',
                        problem_desc: details.description || ''
                    })
                });

                if (!response.ok) throw new Error('Failed to create conversation');

                const data = await response.json();
                setConversationId(data.conversation_id);
                
                // Add initial greeting message
                setMessages([{
                    id: 'greeting',
                    role: 'assistant',
                    content: `Hello! My name is ${voice} and welcome to your interview with ${company}.`,
                    created_at: new Date().toISOString()
                }]);
            } catch (error) {
                console.error('Error creating conversation:', error);
            }
        };

        createConversation();
    }, [company, voice, details]);

    const sendMessage = async () => {
        if (!messageInput.trim() || !conversationId || isSending) return;

        const content = messageInput.trim();
        setMessageInput("");
        setIsSending(true);

        // Add user message
        const userMsg = {
            id: 'temp-user-' + Date.now(),
            role: 'user',
            content: content,
            created_at: new Date().toISOString()
        };
        setMessages(prev => [...prev, userMsg]);

        // Show typing indicator
        setIsTyping(true);

        // Create placeholder for streaming assistant response
        const assistantMsg = {
            id: 'temp-assistant-' + Date.now(),
            role: 'assistant',
            content: '',
            created_at: new Date().toISOString(),
            isStreaming: true
        };
        setMessages(prev => [...prev, assistantMsg]);

        try {
            const response = await fetch(`${API_BASE}/conversations/${conversationId}/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    role: 'user',
                    code: code,
                    sid: socketRef.current?.id,
                    content: content
                })
            });

            if (!response.ok) throw new Error('Failed to send message');

            const data = await response.json();
            const assistantMsgId = data['assistant_message_id'];

            // Update assistant message ID
            if (assistantMsgId) {
                setMessages(prev => prev.map(msg => 
                    msg.id === assistantMsg.id ? { ...msg, id: assistantMsgId } : msg
                ));
            }

            setIsTyping(false);
        } catch (error) {
            console.error('Error sending message:', error);
            setIsTyping(false);
            // Remove placeholder message on error
            setMessages(prev => prev.filter(msg => msg.id !== assistantMsg.id));
        } finally {
            setIsSending(false);
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    // useEffect(() => {
    //     const fetchProblem = async () => {
    //         try {
    //             const res = await fetch("/api/generate-problem", {
    //                 method: "POST",
    //                 headers: { "Content-Type": "application/json" },
    //                 body: JSON.stringify({ company, topic })
    //             });

    //             if (!res.ok) {
    //                 console.error("Server error:", res.status);
    //                 return;
    //             }
                
    //             const text = await res.text();
    //             console.log("Raw response:", text);

    //             const data = text ? JSON.parse(text) : {};
    //             setProblem(data.description || "");
    //             setCode(data.description || "");
    //         } catch (err) {
    //             console.error("Failed to fetch", err);
    //         }
    //     };
    //     fetchProblem();
    // }, [company, topic]);

    return (
        <motion.div 
            className="overlay"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }} 
            transition={{ duration: 0.5 }}   
        >
            <div className="overlay-header">
                {/* <select
                    value={selectedLanguage}
                    onChange={(e) => setSelectedLanguage(e.target.value)}
                >
                    {languages.map((lang) => (
                        <option key={lang} value={lang}>
                            {lang}
                        </option>
                    ))}
                </select> */}
                <button onClick={() => setShowConfirm(true)} style={{ backgroundColor: "red", color: "white" }}>End Interview</button>
            </div>

            <div className="main-container">
                <div className="problem-container">
                    <h2>{details.title}</h2>
                    <div className="desc-container" dangerouslySetInnerHTML={{__html: details.description}}/>
                </div>

                <div className="right-side">
                    <div className="ide-wrapper">
                        <div className="ide-container">
                            <Editor
                                height="700px"
                                language="python"
                                value={details.starterCode}
                                onChange={setCode}
                                theme="vs-dark"
                                options={{
                                    lineNumbers: "on",
                                    minimap: { enabled: false },
                                    fontSize: 19, 
                                }}
                                onMount={(editor) => (editorRef.current = editor)}
                            />
                        </div>
                    </div>
            
                    <motion.div 
                        className="chat-panel"
                        initial={false}
                        animate={{ width: chatOpen ? 350 : 300}}
                        transition={{ duration: 0.25 }}
                        >
                        <div className="chat-header">
                            {chatOpen && <h2 className="chat-title">Interviewer Chatlog</h2>}
                            <button
                                onClick={() => setChatOpen(!chatOpen)}>
                                {chatOpen ? "X" : <MessageSquare />}
                            </button>
                        </div>

                        {chatOpen && (
                            <div className="chat-container">
                                <div className="messages-list" ref={messagesListRef}>
                                    {messages.map(msg => (
                                        <div 
                                            key={msg.id} 
                                            className={msg.role === 'user' ? 'user-container' : 'ai-container'}
                                        >
                                            <div className="message-avatar">
                                                {msg.role === 'user' ? 'U' : 'AI'}
                                            </div>
                                            <div className="message-content">
                                                {msg.content || '...'}
                                            </div>
                                        </div>
                                    ))}
                                    
                                    {isTyping && (
                                        <div className="ai-container">
                                            <div className="message-avatar">AI</div>
                                            <div className="message-content">
                                                <div className="typing-indicator">
                                                    <span></span>
                                                    <span></span>
                                                    <span></span>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                    
                                    {/* spacer element removed: we scroll the container directly */}
                                </div>

                                <div className="input-container">
                                    <textarea
                                        value={messageInput}
                                        onChange={(e) => setMessageInput(e.target.value)}
                                        onKeyDown={handleKeyDown}
                                        placeholder="Type your message..."
                                        disabled={isSending}
                                        rows={2}
                                    />
                                    <button 
                                        onClick={sendMessage}
                                        disabled={isSending || !messageInput.trim()}
                                        className="send-btn"
                                    >
                                        Send
                                    </button>
                                </div>
                            </div>
                        )}
                    </motion.div>
                </div>
            </div>

            <AnimatePresence>
                {showConfirm && (
                    <motion.div
                        key="confirm-modal"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="confirm-modal"
                    >
                        <motion.div
                            initial={{ scale: 0.8, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.8, opacity: 0 }}
                            transition={{ duration: 0.25 }}
                            className="confirm-container"
                        >
                            <h2 style={{ marginBottom: "12px" }}>End the Interview?</h2>
                            <p style={{ marginBottom: "24px", opacity: 0.8 }}>
                                The interview session will finish. You can review a summary after.
                            </p>
                            <div className="buttons-container">
                                <button
                                    onClick={() => setShowConfirm(false)}
                                    className="cancel-btn"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={onEnd}
                                    className="end-btn"
                                >
                                    End Interview
                                </button>
                            </div>
                        </motion.div>
                    </motion.div>
                        
                )}
            </AnimatePresence>
        </motion.div>
    )
}
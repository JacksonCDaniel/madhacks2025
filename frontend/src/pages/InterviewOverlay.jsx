import { useState, useEffect, useRef } from "react";
import { Editor } from "@monaco-editor/react";
import { MessageSquare } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { io } from "socket.io-client";

const API_BASE = "http://127.0.0.1:5000";

export default function InterviewOverlay({ company, voice, topic, details, onEnd }) {
  //   const languages = [
  //     "Java",
  //     "Python",
  //     "C",
  //     "C++",
  //     "JavaScript",
  //     "SQL",
  //     "Rust",
  //   ];

  //   const languageMap = {
  //     Java: "java",
  //     Python: "python",
  //     C: "c",
  //     "C++": "cpp",
  //     JavaScript: "javascript",
  //     SQL: "sql",
  //     Rust: "rust",
  //   };

  const [selectedLanguage, setSelectedLanguage] = useState("Java");
  const [chatOpen, setChatOpen] = useState(true);
  const [code, setCode] = useState("");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [isTyping, setIsTyping] = useState(false);

  const editorRef = useRef(null);

  useEffect(() => {
    if (editorRef.current) editorRef.current.layout();
  }, [chatOpen]);
  const [problem, setProblem] = useState("");

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

  const messagesEndRef = useRef(null);
  const socketRef = useRef(null);

  // Scroll to bottom
  const scrollToBottom = () => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  useEffect(() => {
    // Initialize Socket.IO connection
    if (!socketRef.current) {
      socketRef.current = io(API_BASE);

      socketRef.current.on("connect", () => {
        console.log("Socket.IO connected:", socketRef.current.id);
      });

      socketRef.current.on("llm_response", (chunk) => {
        console.log("Received chunk:", chunk);
        appendToLatestAssistantMessage(chunk);
      });

      socketRef.current.on("connect_error", (err) => {
        console.error("Socket.IO connection error:", err);
      });
    }

    // Initialize conversation
    const saved = localStorage.getItem("conversationId");
    if (saved) {
      setConversationId(saved);
      loadMessages(saved);
    } else {
      createConversation();
    }

    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
    };
  }, []);

  const createConversation = async () => {
    try {
      const res = await fetch(`${API_BASE}/conversations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: "web-user" }),
      });
      if (!res.ok) throw new Error("Failed to create conversation");
      const data = await res.json();
      setConversationId(data.conversation_id);
      localStorage.setItem("conversationId", data.conversation_id);
      setMessages([]);
      console.log("New conversation created:", data.conversation_id);
    } catch (err) {
      console.error("Error creating conversation:", err);
    }
  };

  const loadMessages = async (convId) => {
    try {
      const res = await fetch(
        `${API_BASE}/conversations/${convId}/messages?limit=1000`
      );
      if (!res.ok) {
        console.log("Conversation not found, creating new.");
        createConversation();
        return;
      }
      const data = await res.json();
      setMessages(data.messages);
      console.log("Loaded messages:", data.messages.length);
    } catch (err) {
      console.error("Error loading messages:", err);
      createConversation();
    }
  };

  const appendToLatestAssistantMessage = (chunk) => {
    setMessages((prev) => {
      const copy = [...prev];
      for (let i = copy.length - 1; i >= 0; i--) {
        if (copy[i].role === "assistant" && copy[i].isStreaming) {
          copy[i].content += chunk;
          break;
        }
      }
      return copy;
    });
  };

  const sendMessage = async () => {
    const text = input.trim();
    if (!text) {
      console.log("Empty input, ignoring.");
      return;
    }
    if (!conversationId) {
      console.log("No active conversation. Creating one...");
      await createConversation();
      return;
    }
    if (!socketRef.current || !socketRef.current.id) {
      console.error("Socket not connected");
      return;
    }

    console.log("Sending message:", text);

    // Add user message locally
    const userMsg = {
      id: "local-user-" + Date.now(),
      role: "user",
      content: text,
    };
    const assistantPlaceholder = {
      id: "local-assistant-" + Date.now(),
      role: "assistant",
      content: "",
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantPlaceholder]);
    setInput("");
    setIsTyping(true);

    try {
      const res = await fetch(
        `${API_BASE}/conversations/${conversationId}/messages`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            role: "user",
            content: text,
            sid: socketRef.current.id,
          }),
        }
      );

      if (!res.ok) {
        console.error("Send message failed:", res.status, res.statusText);
        setIsTyping(false);
        return;
      }

      const data = await res.json();
      const assistantId = data.assistant_message_id;

      console.log("Assistant message created:", assistantId);

      // Update placeholder ID and attach audio
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantPlaceholder.id
            ? {
                ...m,
                id: assistantId,
                isStreaming: false,
                audioUrl: `${API_BASE}/conversations/${conversationId}/messages/${assistantId}/tts_stream`,
              }
            : m
        )
      );
    } catch (err) {
      console.error("Error sending message:", err);
    } finally {
      setIsTyping(false);
    }
  };

  const newConversation = () => {
    localStorage.removeItem("conversationId");
    setConversationId(null);
    setMessages([]);
    createConversation();
  };

  return (
    <motion.div
      className="overlay"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.5 }}
    >
      <div className="overlay-header">
        {/*<select
          value={selectedLanguage}
          onChange={(e) => setSelectedLanguage(e.target.value)}
        >
          {languages.map((lang) => (
            <option key={lang} value={lang}>
              {lang}
            </option>
          ))}
        </select>*/}
        <button
          onClick={() => setShowConfirm(true)}
          style={{ backgroundColor: "red", color: "white" }}
        >
          End Interview
        </button>
      </div>

      <div className="main-container">
        {/* <div className="ide-container">
          <Editor
            height="700px"
            language={languageMap[selectedLanguage]}
            value={code}
            onChange={(value) => setCode(value)}
            theme="vs-dark"
            options={{
              lineNumbers: "on",
              minimap: { enabled: false },
              fontSize: 19,
            }}
          />
        </div> */}

        <div className="problem-container">
          <h2>{details.title}</h2>
          <div
            className="desc-container"
            dangerouslySetInnerHTML={{ __html: details.description }}
          />
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
            <button onClick={() => setChatOpen(!chatOpen)}>
              {chatOpen ? "X" : <MessageSquare />}
            </button>
          </div>

          {chatOpen && (
            <div
              className="chat-container"
              style={{ overflowY: "auto", height: "100%", padding: "10px" }}
            >
              {messages.length === 0 && (
                <div className="ai-container">
                  Hello! My name is {voice} and welcome to your interview with{" "}
                  {company}.
                </div>
              )}
              {messages.map((msg) => (
                <div key={msg.id} className={`message ${msg.role}`}>
                  <div className="message-avatar">
                    {msg.role === "user" ? "U" : "AI"}
                  </div>
                  <div className="message-content">
                    <div>{msg.content || "..."}</div>
                    {msg.audioUrl && (
                      <audio controls autoPlay src={msg.audioUrl}></audio>
                    )}
                  </div>
                </div>
              ))}
              {isTyping && (
                <div className="message assistant">
                  <div className="message-avatar">AI</div>
                  <div className="message-content">
                    <div style={{ display: "flex", gap: "4px" }}>
                      <span
                        className="typing-dot"
                        style={{
                          width: 8,
                          height: 8,
                          background: "#999",
                          borderRadius: "50%",
                          animation: "typing 1.4s infinite",
                        }}
                      ></span>
                      <span
                        className="typing-dot"
                        style={{
                          width: 8,
                          height: 8,
                          background: "#999",
                          borderRadius: "50%",
                          animation: "typing 1.4s infinite 0.2s",
                        }}
                      ></span>
                      <span
                        className="typing-dot"
                        style={{
                          width: 8,
                          height: 8,
                          background: "#999",
                          borderRadius: "50%",
                          animation: "typing 1.4s infinite 0.4s",
                        }}
                      ></span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}

          {chatOpen && (
            <div
              className="input-wrapper"
              style={{ padding: "10px", display: "flex", gap: "10px" }}
            >
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type your answer..."
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                  }
                }}
                style={{
                  flex: 1,
                  padding: "10px",
                  borderRadius: "8px",
                  border: "1px solid #ccc",
                  fontFamily: "inherit",
                  fontSize: "14px",
                  height: "50px",
                  resize: "none",
                }}
              />
              <button
                onClick={sendMessage}
                style={{
                  padding: "10px 16px",
                  borderRadius: "8px",
                  background:
                    "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                  color: "white",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                Send
              </button>
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
                The interview session will finish. You can review a summary
                after.
              </p>
              <div className="buttons-container">
                <button
                  onClick={() => setShowConfirm(false)}
                  className="cancel-btn"
                >
                  Cancel
                </button>
                <button onClick={onEnd} className="end-btn">
                  End Interview
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <style>{`
        @keyframes typing {
          0%, 60%, 100% { transform: translateY(0); }
          30% { transform: translateY(-8px); }
        }
      `}</style>
    </motion.div>
  );
}
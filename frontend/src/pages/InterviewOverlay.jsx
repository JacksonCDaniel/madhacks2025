import { useState } from "react";

import { Editor } from "@monaco-editor/react";
import { MessageSquare } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";

export default function InterviewOverlay({ company, voice, topic, onEnd }) {
    const languages = [
        "Java",
        "Python",
        "C",
        "C++",
        "JavaScript",
        "SQL",
        "Rust"
    ]

    const languageMap = {
        Java: "java",
        Python: "python",
        C: "c",
        "C++": "cpp",
        JavaScript: "javascript",
        SQL: "sql",
        Rust: "rust"
    }

    const [selectedLanguage, setSelectedLanguage] = useState("Java");
    const [chatOpen, setChatOpen] = useState(true);
    const [code, setCode] = useState("");

    const [showConfirm, setShowConfirm] = useState(false);

    return (
        <motion.div 
            className="overlay"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }} 
            transition={{ duration: 0.5 }}   
        >
            <div className="overlay-header">
                <select
                    value={selectedLanguage}
                    onChange={(e) => setSelectedLanguage(e.target.value)}
                >
                    {languages.map((lang) => (
                        <option key={lang} value={lang}>
                            {lang}
                        </option>
                    ))}
                </select>
                <button onClick={() => setShowConfirm(true)} style={{ backgroundColor: "red", color: "white" }}>End Interview</button>
            </div>

            <div className="main-container">
                <div className="ide-container">
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
                </div>
            
                <motion.div 
                    className="chat-panel"
                    initial={false}
                    animate={{ x: chatOpen ? 0 : 220}}
                    style={{
                        position: "absolute",
                        top: 0,
                        right: 0,
                        height: "100%",
                        width: "300px",
                        borderLeft: "3px solid #ccc",
                        zIndex: 100
                    }}
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
                            <div className="ai-container">
                                Hello! My name is {voice} and welcome to your interview with {company}.
                            </div>
                            <div className="user-container">
                                Working on it...
                            </div>
                        </div>
                    )}
                </motion.div>
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
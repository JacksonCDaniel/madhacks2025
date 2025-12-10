import { useState } from "react";

export default function Summary({ data, onClose }) {
    const [loading, setLoading] = useState(false);
    const [summary, setSummary] = useState("");
    const [showSummary, setShowSummary] = useState(false);

    const handleGenerate = () => {
        setLoading(true);

        const generatedSummary = `Interview Summary for session:\n\n${JSON.stringify(data, null, 2)}`;

        setSummary(generatedSummary);
        setShowSummary(true);
        setLoading(false);
    };

    const handleDownload = () => {
        const blob = new Blob([summary], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "summary.txt";
        link.click();
        URL.revokeObjectURL(url);
    };

    if (showSummary) {
        return (
            <div className="summary-modal">
                <div className="summary-container">
                    <h1>Interview Summary</h1>
                    <pre className="summary-text">{summary}</pre>
                    <div className="summary-btn-container">
                        <button onClick={onClose} className="skip-btn">Close</button>
                        <button onClick={handleDownload} className="generate-btn">Download</button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="summary-container">
            <h1>Review Your Interview</h1>
            <p style={{fontSize: "22px"}}>
                Do you want to generate a summary of this interview session? You will be provided
                with feedback based on your performance.
            </p>
            <div className="summary-btn-container">
                <button
                    onClick={handleGenerate}
                    disabled={loading}
                    className="generate-btn"
                >
                    Yes, generate summary
                </button>

                <button
                    onClick={onClose}
                    className="skip-btn"
                >
                    No, skip
                </button>
            </div>
        </div>
    )
}
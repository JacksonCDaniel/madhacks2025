import { useState } from "react";

export default function Summary({ data, onClose }) {
    const [loading, setLoading] = useState(false);

    const handleGenerate = () => {
        setLoading(true);
        onGenerate();
    };

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
                    {loading ? "Generating..." : "Yes, generate summary"}
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
export default function VoiceSelection({ voice, setVoice }) {    
    const voices = [
        "Grace (Stern, professional)",
        "Jackson (Friendly, fast)",
        "Thomas (Calm, encouraging)",
        "Valerie (Bored, monotone)"
    ]
    return (
        <div className="interviewer-container">
            <h2>Choose your interviewer</h2>
            <select
                value={voice}
                onChange={(e) => setVoice(e.target.value)}
            >
                <option value="">Select a voice...</option>
                {voices.map((v, i) => (
                    <option key={i} value={v}>{v}</option>
                ))}
            </select>
        </div>
    
    )
}
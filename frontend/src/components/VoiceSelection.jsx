export default function VoiceSelection({ voice, setVoice }) {    
    const voices = [
        { name: "Grace", adjectives: "Stern, professional"},
        { name: "Jackson", adjectives: "Friendly, fast"},
        { name: "Thomas", adjectives: "Calm, encouraging"},
        { name: "Valerie", adjectives: "Bored, monotone"}
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
                    <option key={i} value={v.name}>{v.name} ({v.adjectives})</option>
                ))}
            </select>
        </div>
    
    )
}
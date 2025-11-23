export default function VoiceSelection({ voice, setVoice }) {
    const voices = [
        { name: "Alice", adjectives: "Friendly voice" },
        { name: "Bob", adjectives: "Energetic voice" }
    ];
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
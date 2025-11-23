export default function TopicSelection({ topic, setTopic }) {
    const topics = [
        "Random",
        "Strings",
        "Binary Search",
        "Dynamic Programming",
        "Matrices",
        "Graphs",
        "Two Pointer"
    ]

    return (
        <div className="interviewer-container">
            <h2>Choose your topic</h2>
            <select
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
            >
                <option value="">Select a topic...</option>
                {topics.map((v, i) => (
                    <option key={i} value={v}>{v}</option>
                ))}
            </select>
        </div>
    
    )
}
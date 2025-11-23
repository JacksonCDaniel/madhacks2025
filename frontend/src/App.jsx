import { useState } from 'react'
import './App.css'
import Settings from './pages/Settings'
import InterviewOverlay from './pages/InterviewOverlay'
import Summary from './pages/Summary'

function App() {

	const [currentPage, setCurrentPage] = useState("settings");
	const [interviewData, setInterviewData] = useState({ company: "", voice: "", topic: "" });

	return (
		<>
			{currentPage === "settings" && (
				<Settings
					onStart={(data) => {
						setInterviewData(data);
						setCurrentPage("interview")
					}}
				/>
			)}

			{currentPage === "interview" && (
				<InterviewOverlay
					{...interviewData}
					onEnd={() => setCurrentPage("summary")}
				/>
			)}

			{currentPage === "summary" && (
				<Summary
					data={interviewData}
					onClose={() => setCurrentPage("settings")}
				/>
			)}
		</>
	)
}

export default App

import { useState } from "react";
import VoiceSelection from "../components/VoiceSelection";
import CompanySelection from "../components/CompanySelection";
import TopicSelection from "../components/TopicSelection";
import InterviewOverlay from "./InterviewOverlay";

export default function Settings({ onStart }) {
    const [voice, setVoice] = useState("");
    const [company, setCompany] = useState("");
    const [topic, setTopic] = useState("");

    const isFormValid = company !== "" && voice !== "" && topic !== "" ;
    return (
        <div className="home-page">
            
            <div className="settings-container">
                <h1>Coding Studio</h1>

                <VoiceSelection voice={voice} setVoice={setVoice}/>
                <CompanySelection company={company} setCompany={setCompany}/>
                <TopicSelection topic={topic} setTopic={setTopic}/>
                
                <button 
                    disabled={!isFormValid} 
                    onClick={() => onStart({ company, voice, topic })}>Start Interview</button>
            </div>
            
        </div>
    );
}
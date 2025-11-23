export default function CompanySelection({ company, setCompany }) {
    return (
        <div className="company-container">
            <h2>What company do you want to practice with?</h2>
            <input  
                type="text"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
            />
        </div>
    
    )
}
// Level 2: Better Dynamic Classification - Page Content Checking
const suspiciousKeywords = ["exam answers", "solution manual", "cheat sheet", "test bank"];

// Check for student name on every page load if not already set
async function checkStudentName() {
    const data = await chrome.storage.local.get(["studentName"]);
    if (!data.studentName) {
        // Delay slightly to ensure page is loaded and prompt doesn't interfere
        setTimeout(() => {
            const name = prompt("ATTENTION: Enter Student Name for SmartClass Monitoring:");
            if (name && name.trim().length > 0) {
                chrome.storage.local.set({ studentName: name.trim() });
                console.log("SmartClass: Student name set to", name);
            }
        }, 1000); // 1 second delay
    }
}

checkStudentName();

function checkContent() {
    const pageText = document.body.innerText.toLowerCase();
    for(let kw of suspiciousKeywords) {
        if (pageText.includes(kw)) {
             chrome.runtime.sendMessage({
                action: "violation",
                reason: "Suspicious keyword in page: " + kw,
                url: window.location.href
            });
            return;
        }
    }
}
setTimeout(checkContent, 2000);

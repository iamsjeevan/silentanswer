// Get references to the UI elements
const questionInput = document.getElementById('questionInput');
const additionalInfoTextarea = document.getElementById('additionalInfo');
const sendButton = document.getElementById('sendButton');
const statusDiv = document.getElementById('status');

// --- Send data to backend when button is clicked ---
sendButton.addEventListener('click', () => {
    const questionText = questionInput.value.trim();
    const additionalInfo = additionalInfoTextarea.value.trim();

    if (!questionText) {
        statusDiv.textContent = "Error: Please enter a question.";
        statusDiv.style.color = 'red';
        questionInput.focus();
        return;
    }

    console.log("Popup Window: Sending to backend...");
    console.log("Popup Window: Question:", questionText);
    if (additionalInfo) {
        console.log("Popup Window: Additional info:", additionalInfo);
    }
    statusDiv.textContent = 'Sending to server...';
    statusDiv.style.color = '#333'; // Reset color
    sendButton.disabled = true;

    const serverUrl = "http://localhost:5000/process";
    const payload = {
        question: questionText
    };
    if (additionalInfo) {
        payload.additional_info = additionalInfo;
    }

    fetch(serverUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    .then(response => {
        if (!response.ok) {
             return response.json().then(errData => {
                 throw new Error(errData.message || `HTTP error! Status: ${response.status}`);
             }).catch(() => {
                 throw new Error(`HTTP error! Status: ${response.status}`);
             });
        }
        return response.json();
    })
    .then(data => {
      console.log("Popup Window: Server response:", data);
      if (data.status === "success") {
        statusDiv.textContent = 'Success! Code copied to clipboard.';
        statusDiv.style.color = 'green';
        // You might want to clear fields or keep them
        // questionInput.value = '';
        // additionalInfoTextarea.value = '';
      } else {
         statusDiv.textContent = `Server Error: ${data.message || 'Unknown error'}`;
         statusDiv.style.color = 'red';
         console.error("Popup Window: Server reported an error:", data.message);
      }
    })
    .catch(error => {
      statusDiv.textContent = `Network Error: ${error.message}`;
      statusDiv.style.color = 'red';
      console.error("Popup Window: Error sending request:", error);
    })
    .finally(() => {
        sendButton.disabled = false; // Re-enable the button
    });
});

// --- Initialize ---
document.addEventListener('DOMContentLoaded', () => {
    questionInput.focus(); // Focus the main input field when the window opens
});